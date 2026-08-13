from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import (
    SUB_AGENTS_ROOT,
    read_json,
    resolve_specialist,
    update_registry_specialist,
    write_json_atomic,
)


TOOLS_DIR = Path(__file__).resolve().parent
ORCHESTRATION_CONFIG = SUB_AGENTS_ROOT / "shared" / "orchestration_config.json"
REVIEW_PENDING = SUB_AGENTS_ROOT / "human-review" / "pending"
STAGE_ORDER = ("smoke", "screening")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SpecialistLock:
    def __init__(self, specialist: Path):
        self.path = specialist / ".orchestrator.lock"
        self.handle: int | None = None

    def __enter__(self):
        try:
            self.handle = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            detail = self.path.read_text(encoding="utf-8", errors="replace") if self.path.is_file() else ""
            raise ValueError(f"specialist is locked by another orchestrator: {detail.strip()}") from exc
        os.write(self.handle, json.dumps({"pid": os.getpid(), "started_at": utc_now()}).encode("utf-8"))
        os.close(self.handle)
        self.handle = None
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self.handle is not None:
            os.close(self.handle)
        self.path.unlink(missing_ok=True)


def active_context(specialist: Path):
    status = read_json(specialist / "status.json")
    active = status.get("active_experiment")
    if not active:
        raise ValueError(f"{specialist.name} has no active experiment")
    directory = specialist / "experiments" / active
    return status, directory, read_json(directory / "experiment.json")


def run_command(command: list[str], log_path: Path, timeout_seconds: int) -> int:
    started = utc_now()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        returncode = 124
        timed_out = True
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "COMMAND: " + subprocess.list2cmdline(command) +
        f"\nSTARTED: {started}\nFINISHED: {utc_now()}\nTIMED_OUT: {timed_out}" +
        f"\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}",
        encoding="utf-8",
    )
    return returncode


def update_orchestration(experiment_dir: Path, **changes: Any) -> dict[str, Any]:
    experiment = read_json(experiment_dir / "experiment.json")
    orchestration = experiment.setdefault("orchestration", {})
    orchestration.update(changes)
    orchestration["updated_at"] = utc_now()
    experiment["updated_at"] = utc_now()
    write_json_atomic(experiment_dir / "experiment.json", experiment)
    return experiment


def reject_active(specialist: Path, reason: str, log_path: Path) -> int:
    command = [
        sys.executable,
        str(TOOLS_DIR / "run_experiment.py"),
        "decide", "--specialist", specialist.name, "--reject", "--reason", reason,
    ]
    return run_command(command, log_path, 120)


def screening_regressed(result: dict[str, Any], config: dict[str, Any]) -> tuple[bool, str]:
    policy = config["screening"]
    win_rate = float(result["win_rate"])
    if win_rate < float(policy["reject_below_win_rate"]):
        return True, f"screening win rate {win_rate:.1%} is below {policy['reject_below_win_rate']:.1%}"
    p_value = result.get("p_value")
    if (
        policy.get("reject_significant_loss", True)
        and win_rate < 0.5
        and p_value is not None
        and float(p_value) < float(policy["significance_alpha"])
    ):
        return True, f"screening is a significant loss (win rate {win_rate:.1%}, p={p_value:.4g})"
    return False, ""


def unified_agent_diff(baseline: Path, candidate: Path, limit: int = 500) -> tuple[str, bool]:
    before = baseline.read_text(encoding="utf-8").splitlines()
    after = candidate.read_text(encoding="utf-8").splitlines()
    lines = list(difflib.unified_diff(before, after, fromfile="baseline/main.py", tofile="candidate/main.py", lineterm=""))
    truncated = len(lines) > limit
    if truncated:
        lines = lines[:limit] + [f"... diff truncated after {limit} lines ..."]
    return "\n".join(lines), truncated


def ensure_decision_trace(specialist: Path, experiment_dir: Path, stage: str) -> dict[str, Any]:
    experiment = read_json(experiment_dir / "experiment.json")
    existing = next(
        (item for item in experiment.get("decision_traces", []) if item.get("stage") == stage),
        None,
    )
    if existing:
        return read_json(experiment_dir / existing["result"])
    policy = read_json((specialist / read_json(specialist / "config.json")["benchmark_policy"]).resolve())
    trace_policy = policy["decision_trace"]
    result_path = experiment_dir / "results" / f"decision-trace-{stage}.json"
    log_path = experiment_dir / "orchestration-logs" / f"decision-trace-{stage}.log"
    stage_result = experiment[f"{stage}_result"]
    seed = int(stage_result.get("seed_set") or 20260813) + 100_000
    command = [
        sys.executable,
        str(TOOLS_DIR / "decision_trace.py"),
        "--candidate", str(experiment_dir / "candidate" / "main.py"),
        "--baseline", str(specialist / experiment["baseline_path"] / "main.py"),
        "--deck", str(experiment_dir / "candidate" / "deck.csv"),
        "--specialist", specialist.name,
        "--candidate-version", experiment["candidate_version"],
        "--baseline-version", experiment["baseline_version"],
        "--games", str(trace_policy["games"]),
        "--max-steps", str(policy["max_steps_per_game"]),
        "--max-records", str(trace_policy["max_records"]),
        "--max-options", str(trace_policy["max_options_per_record"]),
        "--seed", str(seed),
        "--output", str(result_path),
    ]
    code = run_command(command, log_path, int(trace_policy["timeout_seconds"]))
    if code != 0 or not result_path.is_file():
        raise ValueError(f"decision trace failed with exit {code}; see {log_path}")
    trace = read_json(result_path)
    if trace.get("errors"):
        raise ValueError(f"decision trace contains execution errors; see {result_path}")
    experiment = read_json(experiment_dir / "experiment.json")
    experiment.setdefault("decision_traces", []).append(
        {
            "stage": stage,
            "result": str(result_path.relative_to(experiment_dir)).replace("\\", "/"),
            "log": str(log_path.relative_to(experiment_dir)).replace("\\", "/"),
            "games": trace["games"],
            "total_differences": trace["summary"]["total_differences"],
            "difference_rate": trace["summary"]["difference_rate"],
        }
    )
    experiment["updated_at"] = utc_now()
    write_json_atomic(experiment_dir / "experiment.json", experiment)
    return trace


def trace_markdown(trace: dict[str, Any]) -> str:
    summary = trace["summary"]
    context_rows = "\n".join(
        f"| {context} | {count} |" for context, count in summary.get("contexts", {}).items()
    ) or "| none | 0 |"
    examples = []
    for record in trace.get("records", [])[:5]:
        candidate = ", ".join(item.get("type", "?") for item in record["candidate_selected"]) or "none"
        baseline = ", ".join(item.get("type", "?") for item in record["baseline_selected"]) or "none"
        examples.append(
            f"| {record['game']} | {record['step']} | {record['select_type']}/{record['context']} | "
            f"{candidate} | {baseline} |"
        )
    example_rows = "\n".join(examples) or "| - | - | no differences retained | - | - |"
    return f"""- Trace games: `{trace['games']}`
- Candidate decisions observed: `{summary['candidate_decisions']}`
- Different choices: `{summary['total_differences']}` ({summary['difference_rate']:.1%})
- Games containing a difference: `{summary['games_with_difference']}`
- Retained records: `{summary['records_retained']}`; truncated: `{summary['records_truncated']}`

| Selection context | Differences |
|---|---:|
{context_rows}

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
{example_rows}"""


def create_review_pack(specialist: Path, experiment_dir: Path, stage: str) -> tuple[Path, Path]:
    status = read_json(specialist / "status.json")
    experiment = read_json(experiment_dir / "experiment.json")
    result = experiment.get(f"{stage}_result")
    if result is None:
        raise ValueError(f"cannot create review pack without {stage} result")
    baseline = specialist / experiment["baseline_path"] / "main.py"
    candidate = experiment_dir / "candidate" / "main.py"
    diff, truncated = unified_agent_diff(baseline, candidate)
    trace = ensure_decision_trace(specialist, experiment_dir, stage)
    experiment = read_json(experiment_dir / "experiment.json")
    trace_text = trace_markdown(trace)
    latest_worker = next((run for run in reversed(experiment.get("worker_runs", [])) if not run.get("dry_run")), None)
    checks = [
        "Does the diff implement only the stated mechanism?",
        "Does the observed result justify more evaluation rather than acceptance?",
        "Could the change affect unrelated selection contexts or deck archetypes?",
        "Is representative decision-trace evidence required before the next benchmark?",
    ]
    if "attack_readiness_attachment" in experiment["mechanisms"]:
        checks.extend([
            "Is the Energy attachment choice legal and sensible in representative board states?",
            "Does it preserve Active preference when readiness is tied?",
            "Could it starve an evolution line or over-invest in a low-quality attacker?",
        ])
    checks_markdown = "\n".join(f"- {check}" for check in checks)
    pack_name = f"{specialist.name}-{experiment['id']}"
    json_path = REVIEW_PENDING / f"{pack_name}.json"
    markdown_path = REVIEW_PENDING / f"{pack_name}.md"
    review = {
        "schema_version": 1,
        "specialist": specialist.name,
        "experiment": experiment["id"],
        "stage": stage,
        "created_at": utc_now(),
        "hypothesis": experiment["hypothesis"],
        "expected_effect": experiment.get("expected_effect", ""),
        "mechanisms": experiment["mechanisms"],
        "baseline_version": experiment["baseline_version"],
        "candidate_version": experiment["candidate_version"],
        "provider_run": latest_worker,
        "benchmark": result,
        "cross_deck_results": experiment.get("cross_deck_results", []),
        "decision_trace": {
            "result": next(item["result"] for item in experiment["decision_traces"] if item["stage"] == stage),
            "summary": trace["summary"],
        },
        "diff_truncated": truncated,
        "decision": "pending",
        "reviewer_reason": "",
    }
    write_json_atomic(json_path, review)
    markdown_path.write_text(
        f"""# Human Review: {specialist.name} {experiment['id']}

## Hypothesis

{experiment['hypothesis']}

Expected effect: {experiment.get('expected_effect') or 'Not specified.'}

Mechanisms: {', '.join(experiment['mechanisms'])}

## Evidence

- Stage: `{stage}`
- Candidate: `{result['wins']}/{result['games']}` wins ({result['win_rate']:.1%})
- 95% interval: `{result['confidence_interval'][0]:.1%} - {result['confidence_interval'][1]:.1%}`
- Head-to-head null test: `z={result['z_score']}`, `p={result['p_value']}`
- Draws/timeouts/illegal actions/crashes: `{result['draws']}/{result['timeouts']}/{result['illegal_actions']}/{result['crashes']}`
- Mean/max decision time: `{result['average_decision_time_ms']:.2f} ms / {result['max_decision_time_ms']:.2f} ms`

## Cross-Deck Evidence

{json.dumps(experiment.get('cross_deck_results', []), indent=2, ensure_ascii=True)}

## Decision-Difference Trace

{trace_text}

## Required Human Checks

{checks_markdown}

## Agent Diff

```diff
{diff}
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.
""",
        encoding="utf-8",
    )
    status.update({"state": "REVIEW_REQUIRED", "review_state": "REVIEW_REQUIRED", "updated_at": utc_now()})
    write_json_atomic(specialist / "status.json", status)
    experiment["status"] = "REVIEW_REQUIRED"
    experiment["updated_at"] = utc_now()
    experiment.setdefault("reviews", []).append({
        "stage": stage,
        "status": "pending",
        "created_at": utc_now(),
        "json": str(json_path.relative_to(SUB_AGENTS_ROOT)).replace("\\", "/"),
        "markdown": str(markdown_path.relative_to(SUB_AGENTS_ROOT)).replace("\\", "/"),
    })
    write_json_atomic(experiment_dir / "experiment.json", experiment)
    update_registry_specialist(specialist.name, state=status["state"], active_experiment=experiment["id"])
    return markdown_path, json_path


def execute_cycle(args, resume: bool) -> int:
    specialist = resolve_specialist(args.specialist)
    config = read_json(ORCHESTRATION_CONFIG)
    with SpecialistLock(specialist):
        if not resume:
            status = read_json(specialist / "status.json")
            if status.get("active_experiment"):
                raise ValueError(f"active experiment already exists: {status['active_experiment']}")
            command = [
                sys.executable, str(TOOLS_DIR / "run_experiment.py"), "start",
                "--specialist", specialist.name,
                "--hypothesis", args.hypothesis,
                "--mechanism", args.mechanism,
                "--expected-effect", args.expected_effect,
                "--worker", args.provider,
            ]
            bootstrap_log = specialist / "benchmarks" / f"orchestrator-start-{utc_now().replace(':', '')}.log"
            if run_command(command, bootstrap_log, 120) != 0:
                raise ValueError(f"could not start experiment; see {bootstrap_log}")

        status, experiment_dir, experiment = active_context(specialist)
        logs = experiment_dir / "orchestration-logs"
        orchestration = experiment.get("orchestration", {})
        update_orchestration(
            experiment_dir,
            state="RUNNING",
            provider=args.provider,
            through_stage=args.through,
            started_at=orchestration.get("started_at", utc_now()),
        )

        actual_worker_runs = [run for run in experiment.get("worker_runs", []) if not run.get("dry_run")]
        if not actual_worker_runs:
            worker_command = [
                sys.executable, str(TOOLS_DIR / "run_worker.py"), "run",
                "--specialist", specialist.name, "--provider", args.provider,
                "--timeout-seconds", str(args.worker_timeout),
            ]
            if args.model:
                worker_command.extend(["--model", args.model])
            worker_code = run_command(
                worker_command,
                logs / "01-provider.log",
                args.worker_timeout + int(config["command_grace_seconds"]),
            )
            if worker_code != 0:
                reason = f"automatic rejection: provider stage failed with exit {worker_code}"
                update_orchestration(experiment_dir, state="FAILED_PROVIDER", failure_reason=reason)
                reject_active(specialist, reason, logs / "99-reject.log")
                return 1

        experiment = read_json(experiment_dir / "experiment.json")
        for index, stage in enumerate(STAGE_ORDER, 2):
            if STAGE_ORDER.index(stage) > STAGE_ORDER.index(args.through):
                break
            if experiment.get(f"{stage}_result") is not None:
                continue
            stage_command = [
                sys.executable, str(TOOLS_DIR / "run_experiment.py"), "run",
                "--specialist", specialist.name, "--stage", stage,
                "--seed", str(args.seed + index),
            ]
            code = run_command(stage_command, logs / f"{index:02d}-{stage}.log", 2000)
            if code != 0:
                reason = f"automatic rejection: {stage} stage failed with exit {code}"
                update_orchestration(experiment_dir, state=f"FAILED_{stage.upper()}", failure_reason=reason)
                reject_active(specialist, reason, logs / "99-reject.log")
                return 1
            experiment = read_json(experiment_dir / "experiment.json")
            result = experiment[f"{stage}_result"]
            if result["crashes"] or result["illegal_actions"] or result["timeouts"]:
                reason = (
                    f"automatic rejection: {stage} produced {result['crashes']} crashes, "
                    f"{result['illegal_actions']} illegal actions, and {result['timeouts']} timeouts"
                )
                update_orchestration(experiment_dir, state=f"FAILED_{stage.upper()}", failure_reason=reason)
                reject_active(specialist, reason, logs / "99-reject.log")
                return 1
            if stage == "screening":
                regressed, reason = screening_regressed(result, config)
                if regressed:
                    reason = "automatic rejection: " + reason
                    update_orchestration(experiment_dir, state="FAILED_SCREENING", failure_reason=reason)
                    reject_active(specialist, reason, logs / "99-reject.log")
                    return 1

        markdown, _ = create_review_pack(specialist, experiment_dir, args.through)
        update_orchestration(
            experiment_dir,
            state="REVIEW_REQUIRED",
            review_pack=str(markdown.relative_to(SUB_AGENTS_ROOT)).replace("\\", "/"),
        )
        print(f"Review required: {markdown}")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one bounded Plan_2 coding-worker cycle.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Start and execute a new experiment through screening")
    run.add_argument("--specialist", required=True)
    run.add_argument("--provider", choices=("codex", "claude", "antigravity"), required=True)
    run.add_argument("--hypothesis", required=True)
    run.add_argument("--mechanism", required=True)
    run.add_argument("--expected-effect", required=True)
    run.add_argument("--through", choices=STAGE_ORDER, default="screening")
    run.add_argument("--model")
    run.add_argument("--worker-timeout", type=int, default=900)
    run.add_argument("--seed", type=int, default=20260812)
    run.set_defaults(handler=lambda args: execute_cycle(args, False))
    resume = subparsers.add_parser("resume", help="Resume the active experiment through screening")
    resume.add_argument("--specialist", required=True)
    resume.add_argument("--provider", choices=("codex", "claude", "antigravity"), required=True)
    resume.add_argument("--through", choices=STAGE_ORDER, default="screening")
    resume.add_argument("--model")
    resume.add_argument("--worker-timeout", type=int, default=900)
    resume.add_argument("--seed", type=int, default=20260812)
    resume.set_defaults(handler=lambda args: execute_cycle(args, True))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
