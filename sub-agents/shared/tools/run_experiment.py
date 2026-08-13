from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import (
    REPO_ROOT,
    copy_file_atomic,
    copy_pair,
    next_experiment_id,
    next_version,
    read_json,
    resolve_specialist,
    sha256_file,
    update_registry_specialist,
    validate_deck,
    validate_python_syntax,
    write_json_atomic,
)


STAGES = ("smoke", "screening", "main", "confirmation")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def experiment_path(specialist: Path, experiment_id: str) -> Path:
    path = (specialist / "experiments" / experiment_id).resolve()
    try:
        path.relative_to((specialist / "experiments").resolve())
    except ValueError as exc:
        raise ValueError(f"invalid experiment ID: {experiment_id}") from exc
    if not path.is_dir():
        raise ValueError(f"experiment does not exist: {experiment_id}")
    return path


def active_context(specialist: Path):
    status = read_json(specialist / "status.json")
    active = status.get("active_experiment")
    if not active:
        raise ValueError(f"{specialist.name} has no active experiment")
    directory = experiment_path(specialist, active)
    experiment = read_json(directory / "experiment.json")
    return status, directory, experiment


def append_progress(specialist: Path, text: str) -> None:
    with (specialist / "PROGRESS.md").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n" + text.rstrip() + "\n")


def create_snapshot(specialist: Path, version: str) -> Path:
    snapshot = specialist / "snapshots" / version
    if snapshot.exists():
        expected = {filename: sha256_file(specialist / filename) for filename in ("main.py", "deck.csv")}
        actual = {
            filename: sha256_file(snapshot / filename) if (snapshot / filename).is_file() else None
            for filename in ("main.py", "deck.csv")
        }
        if expected != actual:
            raise ValueError(f"existing snapshot does not match accepted {version}")
        return snapshot
    copy_pair(specialist, snapshot)
    write_json_atomic(snapshot / "manifest.json", {
        "version": version,
        "created_at": utc_now(),
        "agent_sha256": sha256_file(snapshot / "main.py"),
        "deck_sha256": sha256_file(snapshot / "deck.csv"),
    })
    return snapshot


def start(args) -> int:
    specialist = resolve_specialist(args.specialist)
    config = read_json(specialist / "config.json")
    status = read_json(specialist / "status.json")
    if status.get("active_experiment"):
        raise ValueError(f"active experiment already exists: {status['active_experiment']}")

    experiment_id = next_experiment_id(specialist)
    directory = specialist / "experiments" / experiment_id
    directory.mkdir(parents=True)
    try:
        baseline = create_snapshot(specialist, status["current_version"])
        candidate = directory / "candidate"
        copy_pair(specialist, candidate)
        (directory / "results").mkdir()
        (directory / "logs").mkdir()
        experiment = {
            "id": experiment_id,
            "specialist": specialist.name,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "worker": args.worker or config.get("provider", "unknown"),
            "hypothesis": args.hypothesis,
            "expected_effect": args.expected_effect or "",
            "mechanisms": args.mechanism,
            "files_changed": [],
            "baseline_version": status["current_version"],
            "candidate_version": next_version(status["current_version"]),
            "accepted_version": None,
            "baseline_path": str(baseline.relative_to(specialist)).replace("\\", "/"),
            "candidate_path": str(candidate.relative_to(specialist)).replace("\\", "/"),
            "status": "PROPOSED",
            "smoke_result": None,
            "screening_result": None,
            "main_result": None,
            "confirmation_result": None,
            "cross_deck_results": [],
            "decision_traces": [],
            "runs": [],
            "worker_runs": [],
            "orchestration": {},
            "reviews": [],
            "review_history": [],
            "decision": "pending",
            "reason": "",
            "limitations": [],
        }
        write_json_atomic(directory / "experiment.json", experiment)
        status.update({
            "state": "EXPERIMENT_ACTIVE",
            "review_state": "AUTOMATIC",
            "active_experiment": experiment_id,
            "updated_at": utc_now(),
        })
        write_json_atomic(specialist / "status.json", status)
        update_registry_specialist(specialist.name, state=status["state"], active_experiment=experiment_id)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise

    print(f"Started {specialist.name}/{experiment_id}")
    print(f"Edit only: {directory / 'candidate' / 'main.py'}")
    return 0


def validate_candidate(candidate: Path) -> list[str]:
    errors = []
    for report in (validate_deck(candidate / "deck.csv"), validate_python_syntax(candidate / "main.py")):
        errors.extend(report.errors)
    return errors


def run_stage(args) -> int:
    specialist = resolve_specialist(args.specialist)
    config = read_json(specialist / "config.json")
    status, directory, experiment = active_context(specialist)
    candidate = directory / experiment["candidate_path"].split("/")[-1]
    baseline = specialist / experiment["baseline_path"]
    errors = validate_candidate(candidate)
    if errors:
        raise ValueError("candidate validation failed: " + "; ".join(errors))
    changed = []
    for filename in ("main.py", "deck.csv"):
        if sha256_file(candidate / filename) != sha256_file(baseline / filename):
            changed.append(filename)
    experiment["files_changed"] = changed

    policy_path = (specialist / config["benchmark_policy"]).resolve()
    policy = read_json(policy_path)
    prerequisites = {
        "screening": "smoke_result",
        "main": "screening_result",
        "confirmation": "main_result",
    }
    prerequisite = prerequisites.get(args.stage)
    if prerequisite and experiment.get(prerequisite) is None:
        prior_stage = prerequisite.removesuffix("_result")
        raise ValueError(f"{args.stage} requires a successful {prior_stage} result first")
    games = args.games or int(policy["game_stages"][args.stage])
    if games <= 0:
        raise ValueError("game count must be positive")
    max_allowed = int(policy["game_stages"][args.stage])
    if games > max_allowed and not args.allow_larger_run:
        raise ValueError(f"{args.stage} is capped at {max_allowed} games; use --allow-larger-run explicitly")

    run_number = len(experiment.get("runs", [])) + 1
    result_path = directory / "results" / f"{args.stage}-{run_number:03d}.json"
    log_path = directory / "logs" / f"{args.stage}-{run_number:03d}.log"
    command = [
        sys.executable,
        str(Path(__file__).with_name("benchmark_pair.py")),
        "--candidate", str(candidate / "main.py"),
        "--baseline", str(baseline / "main.py"),
        "--deck", str(candidate / "deck.csv"),
        "--games", str(games),
        "--max-steps", str(policy["max_steps_per_game"]),
        "--seed", str(args.seed),
        "--output", str(result_path),
        "--specialist", specialist.name,
        "--candidate-version", experiment["candidate_version"],
        "--baseline-version", experiment["baseline_version"],
        "--stage", args.stage,
    ]
    timeout_seconds = min(
        int(config["experiment_budget"]["max_runtime_minutes"]) * 60,
        int(args.timeout_seconds or config.get("benchmark_timeout_seconds", 1800)),
    )
    started_at = utc_now()
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        log_path.write_text(
            f"COMMAND: {subprocess.list2cmdline(command)}\n\nSTDOUT:\n{completed.stdout}\n\nSTDERR:\n{completed.stderr}",
            encoding="utf-8",
        )
        run_record = {
            "stage": args.stage,
            "games": games,
            "seed": args.seed,
            "started_at": started_at,
            "finished_at": utc_now(),
            "returncode": completed.returncode,
            "result": str(result_path.relative_to(directory)).replace("\\", "/") if result_path.exists() else None,
            "log": str(log_path.relative_to(directory)).replace("\\", "/"),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        log_path.write_text(
            f"COMMAND: {subprocess.list2cmdline(command)}\n\nTIMEOUT after {timeout_seconds}s\n\nSTDOUT:\n{exc.stdout or ''}\n\nSTDERR:\n{exc.stderr or ''}",
            encoding="utf-8",
        )
        run_record = {
            "stage": args.stage,
            "games": games,
            "seed": args.seed,
            "started_at": started_at,
            "finished_at": utc_now(),
            "returncode": None,
            "result": None,
            "log": str(log_path.relative_to(directory)).replace("\\", "/"),
            "timed_out": True,
        }

    experiment.setdefault("runs", []).append(run_record)
    experiment["updated_at"] = utc_now()
    experiment["status"] = "RUNNING"
    if result_path.exists():
        result = read_json(result_path)
        key = f"{args.stage}_result"
        experiment[key] = result
    write_json_atomic(directory / "experiment.json", experiment)

    if run_record["timed_out"]:
        print(f"ERROR: benchmark exceeded {timeout_seconds}s; see {log_path}", file=sys.stderr)
        return 124
    if run_record["returncode"] != 0:
        print(f"ERROR: benchmark failed; see {log_path}", file=sys.stderr)
        return int(run_record["returncode"] or 1)
    result = read_json(result_path)
    if args.stage == "smoke" and all(
        result.get(field, 0) == 0
        for field in ("timeouts", "illegal_actions", "crashes")
    ):
        status["validation"] = {
            "static": "passed",
            "runtime_import": "passed",
            "smoke_benchmark": "passed",
        }
        status["updated_at"] = utc_now()
        write_json_atomic(specialist / "status.json", status)
    print(
        f"{args.stage}: {result['wins']}/{result['games']} wins "
        f"({result['win_rate']:.1%}), {result['draws']} draws, {result['crashes']} crashes"
    )
    print(f"Result: {result_path}")
    return 0


def decide(args) -> int:
    specialist = resolve_specialist(args.specialist)
    config = read_json(specialist / "config.json")
    status, directory, experiment = active_context(specialist)
    candidate = directory / "candidate"
    accepted = args.accept
    if accepted and not experiment.get("runs"):
        raise ValueError("cannot accept an experiment without at least one recorded benchmark run")
    if accepted:
        policy = read_json((specialist / config["benchmark_policy"]).resolve())
        minimum_stage = policy.get("minimum_acceptance_stage", "main")
        if experiment.get(f"{minimum_stage}_result") is None:
            raise ValueError(f"acceptance requires a successful {minimum_stage} benchmark")
        required_cross_deck = int(policy.get("required_cross_deck_opponents", 0))
        completed_cross_deck = {
            result.get("opponent")
            for result in experiment.get("cross_deck_results", [])
            if result.get("status") == "complete"
        }
        if len(completed_cross_deck) < required_cross_deck:
            raise ValueError(
                f"acceptance requires {required_cross_deck} cross-deck opponents; "
                f"found {len(completed_cross_deck)}"
            )
        final_review = next(
            (
                review for review in reversed(experiment.get("review_history", []))
                if review.get("stage") == "confirmation" and review.get("decision") == "approved_for_acceptance"
            ),
            None,
        )
        if final_review is None:
            raise ValueError("acceptance requires final human approval after confirmation")
        failed_runs = [run for run in experiment["runs"] if run.get("timed_out") or run.get("returncode") != 0]
        if failed_runs:
            raise ValueError("cannot accept while failed or timed-out benchmark runs are recorded")
        errors = validate_candidate(candidate)
        if errors:
            raise ValueError("cannot accept invalid candidate: " + "; ".join(errors))
        accepted_version = experiment["candidate_version"].replace("-candidate", "-accepted")
        accepted_snapshot = specialist / "snapshots" / accepted_version
        if not accepted_snapshot.exists():
            copy_pair(candidate, accepted_snapshot)
            write_json_atomic(accepted_snapshot / "manifest.json", {
                "version": accepted_version,
                "created_at": utc_now(),
                "experiment": experiment["id"],
                "agent_sha256": sha256_file(accepted_snapshot / "main.py"),
                "deck_sha256": sha256_file(accepted_snapshot / "deck.csv"),
            })
        baseline = specialist / experiment["baseline_path"]
        try:
            copy_file_atomic(candidate / "main.py", specialist / "main.py")
            copy_file_atomic(candidate / "deck.csv", specialist / "deck.csv")
        except Exception:
            copy_file_atomic(baseline / "main.py", specialist / "main.py")
            copy_file_atomic(baseline / "deck.csv", specialist / "deck.csv")
            raise
        experiment["accepted_version"] = accepted_version
        status.update({
            "state": "READY_FOR_EXPERIMENT",
            "review_state": "AUTOMATIC",
            "current_version": accepted_version,
            "accepted_experiment": experiment["id"],
            "active_experiment": None,
            "updated_at": utc_now(),
            "agent_sha256": sha256_file(specialist / "main.py"),
            "deck_sha256": sha256_file(specialist / "deck.csv"),
        })
        decision = "accepted"
    else:
        status.update({
            "state": "READY_FOR_EXPERIMENT",
            "review_state": "AUTOMATIC",
            "active_experiment": None,
            "updated_at": utc_now(),
        })
        decision = "rejected"

    experiment.update({
        "status": "COMPLETE",
        "decision": decision,
        "reason": args.reason,
        "updated_at": utc_now(),
    })
    write_json_atomic(directory / "experiment.json", experiment)
    if not accepted:
        shutil.copy2(directory / "experiment.json", specialist / "rejected" / f"{experiment['id']}.json")
    write_json_atomic(specialist / "status.json", status)
    update_registry_specialist(
        specialist.name,
        state=status["state"],
        active_experiment=None,
        current_version=status["current_version"],
        agent_sha256=status["agent_sha256"],
        deck_sha256=status["deck_sha256"],
    )
    append_progress(specialist, f"""## {utc_now()[:10]} — {experiment['id']}

- **{decision.upper()}: {experiment['hypothesis']}**
  - Mechanisms: {', '.join(experiment['mechanisms'])}.
  - Baseline: `{experiment['baseline_version']}`; candidate: `{experiment['candidate_version']}`.
  - Benchmark runs recorded: {len(experiment.get('runs', []))}.
  - Decision reason: {args.reason}
""")
    print(f"{specialist.name}/{experiment['id']}: {decision.upper()}")
    return 0


def show(args) -> int:
    specialist = resolve_specialist(args.specialist)
    status = read_json(specialist / "status.json")
    output = {"specialist": specialist.name, "status": status}
    if status.get("active_experiment"):
        directory = experiment_path(specialist, status["active_experiment"])
        output["experiment"] = read_json(directory / "experiment.json")
    print(json.dumps(output, indent=2, ensure_ascii=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage bounded Plan_2 specialist experiments.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Stage a new private candidate")
    start_parser.add_argument("--specialist", required=True)
    start_parser.add_argument("--hypothesis", required=True)
    start_parser.add_argument("--mechanism", action="append", required=True)
    start_parser.add_argument("--expected-effect")
    start_parser.add_argument("--worker")
    start_parser.set_defaults(handler=start)

    run_parser = subparsers.add_parser("run", help="Validate and benchmark the active candidate")
    run_parser.add_argument("--specialist", required=True)
    run_parser.add_argument("--stage", required=True, choices=STAGES)
    run_parser.add_argument("--games", type=int)
    run_parser.add_argument("--seed", type=int, default=20260812)
    run_parser.add_argument("--timeout-seconds", type=int)
    run_parser.add_argument("--allow-larger-run", action="store_true")
    run_parser.set_defaults(handler=run_stage)

    decide_parser = subparsers.add_parser("decide", help="Explicitly accept or reject the active candidate")
    decide_parser.add_argument("--specialist", required=True)
    choice = decide_parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--accept", action="store_true")
    choice.add_argument("--reject", action="store_true")
    decide_parser.add_argument("--reason", required=True)
    decide_parser.set_defaults(handler=decide)

    status_parser = subparsers.add_parser("status", help="Show specialist and active experiment state")
    status_parser.add_argument("--specialist", required=True)
    status_parser.set_defaults(handler=show)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
