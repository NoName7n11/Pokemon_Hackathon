from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import (
    REPO_ROOT,
    SUB_AGENTS_ROOT,
    copy_file_atomic,
    read_json,
    resolve_specialist,
    sha256_file,
    validate_deck,
    validate_python_syntax,
    write_json_atomic,
)
from provider_adapters import build_provider_command, provider_status


PROVIDER_CONFIG_PATH = SUB_AGENTS_ROOT / "shared" / "provider_config.json"
IGNORED_WORKSPACE_NAMES = {".codex", ".claude", ".gemini", "__pycache__"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def active_context(specialist: Path):
    status = read_json(specialist / "status.json")
    active = status.get("active_experiment")
    if not active:
        raise ValueError(f"{specialist.name} has no active experiment; start one first")
    directory = specialist / "experiments" / active
    if not directory.is_dir():
        raise ValueError(f"active experiment directory is missing: {directory}")
    return status, directory, read_json(directory / "experiment.json")


def fingerprint(root: Path) -> dict[str, str]:
    result = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in IGNORED_WORKSPACE_NAMES for part in relative.parts):
            continue
        result[relative.as_posix()] = sha256_file(path)
    return result


def copy_context(specialist: Path, experiment_dir: Path, workspace: Path) -> None:
    candidate = experiment_dir / "candidate"
    workspace.mkdir(parents=True, exist_ok=False)
    shutil.copy2(candidate / "main.py", workspace / "main.py")
    shutil.copy2(candidate / "deck.csv", workspace / "deck.csv")

    context = workspace / "context"
    context.mkdir()
    sources = {
        "EXPERIMENT.json": experiment_dir / "experiment.json",
        "SPECIALIST_CONFIG.json": specialist / "config.json",
        "SPECIALIST_STATUS.json": specialist / "status.json",
        "SPECIALIST_PROGRESS.md": specialist / "PROGRESS.md",
        "AGENT_CONTRACT.md": SUB_AGENTS_ROOT / "shared" / "AGENT_CONTRACT.md",
        "POKEMON_RULES.md": REPO_ROOT / "POKEMON_RULES.md",
    }
    specialist_config = read_json(specialist / "config.json")
    strategy_source = specialist_config.get("source_strategy")
    if strategy_source:
        sources["STRATEGY.md"] = REPO_ROOT / strategy_source
    for destination_name, source in sources.items():
        if source.is_file():
            shutil.copy2(source, context / destination_name)

    experiment = read_json(experiment_dir / "experiment.json")
    baseline_path = specialist / experiment["baseline_path"]
    baseline = context / "baseline"
    baseline.mkdir()
    shutil.copy2(baseline_path / "main.py", baseline / "main.py")
    shutil.copy2(baseline_path / "deck.csv", baseline / "deck.csv")


def render_prompt(provider: str, specialist: Path, experiment: dict[str, Any]) -> str:
    mechanisms = ", ".join(experiment["mechanisms"])
    return f"""You are the {provider} development worker for the private Plan_2 specialist {specialist.name}.

This is a disposable, isolated workspace. Read `context/AGENT_CONTRACT.md`,
`context/EXPERIMENT.json`, `context/SPECIALIST_CONFIG.json`,
`context/SPECIALIST_PROGRESS.md`, `context/POKEMON_RULES.md`, any available
`context/STRATEGY.md`, the current
`main.py`, and `context/baseline/main.py` before editing.

Experiment hypothesis:
{experiment['hypothesis']}

Expected effect:
{experiment.get('expected_effect') or 'Not specified.'}

Mechanism under test:
{mechanisms}

Implement the smallest coherent change in the root `main.py` that tests this
hypothesis. Do not modify `deck.csv`, any file under `context/`, or create
additional project files. Do not run benchmarks and do not access parent
directories, the active submission, other specialists, the network, or external
services. The controller performs validation and games after your process exits.

Keep Kaggle compatibility: `main.py` must remain self-contained, define
`agent(obs_dict)` and `read_deck_csv()`, and must not add dependencies unavailable
to the competition environment. Finish with a concise description of the exact
behavior changed and any concern the human reviewer should inspect.
"""


def list_providers(_args) -> int:
    print(json.dumps(provider_status(read_json(PROVIDER_CONFIG_PATH)), indent=2, ensure_ascii=True))
    return 0


def run_provider(args) -> int:
    specialist = resolve_specialist(args.specialist)
    specialist_config = read_json(specialist / "config.json")
    provider_config = read_json(PROVIDER_CONFIG_PATH)
    _, experiment_dir, experiment = active_context(specialist)
    provider = args.provider or specialist_config["provider"]

    prior_runs = experiment.get("worker_runs", [])
    actual_runs = sum(not run.get("dry_run", False) for run in prior_runs)
    dry_runs = sum(run.get("dry_run", False) for run in prior_runs)
    if args.dry_run:
        maximum_dry_runs = int(provider_config["max_dry_runs_per_experiment"])
        if dry_runs >= maximum_dry_runs:
            raise ValueError(f"dry-run budget exhausted ({maximum_dry_runs} per experiment)")
    else:
        maximum_runs = int(provider_config["max_worker_runs_per_experiment"])
        if actual_runs >= maximum_runs:
            raise ValueError(f"worker run budget exhausted ({maximum_runs} per experiment)")

    run_number = len(experiment.get("worker_runs", [])) + 1
    run_dir = experiment_dir / "workers" / f"{run_number:03d}-{provider}"
    workspace = run_dir / "workspace"
    run_dir.mkdir(parents=True, exist_ok=False)
    try:
        copy_context(specialist, experiment_dir, workspace)
        prompt = render_prompt(provider, specialist, experiment)
        (run_dir / "prompt.md").write_text(prompt, encoding="utf-8")
        command = build_provider_command(provider, provider_config, workspace, args.model)
    except Exception:
        shutil.rmtree(run_dir, ignore_errors=True)
        raise
    command_record = {
        "provider": provider,
        "backend": command.backend,
        "executable": command.executable,
        "args": command.display_args(),
        "cwd": str(workspace),
        "model": args.model,
    }
    write_json_atomic(run_dir / "command.json", command_record)
    before = fingerprint(workspace)
    started_at = utc_now()

    if args.dry_run:
        worker_record = {
            "run": run_number,
            "provider": provider,
            "backend": command.backend,
            "model": args.model,
            "started_at": started_at,
            "finished_at": utc_now(),
            "dry_run": True,
            "returncode": None,
            "timed_out": False,
            "candidate_imported": False,
            "changed_files": [],
            "validation_errors": [],
            "run_dir": str(run_dir.relative_to(experiment_dir)).replace("\\", "/"),
        }
        experiment.setdefault("worker_runs", []).append(worker_record)
        experiment["updated_at"] = utc_now()
        write_json_atomic(experiment_dir / "experiment.json", experiment)
        print(json.dumps(command_record, indent=2, ensure_ascii=True))
        return 0

    timeout_seconds = min(
        int(args.timeout_seconds or provider_config["worker_timeout_seconds"]),
        int(specialist_config["experiment_budget"]["max_runtime_minutes"]) * 60,
    )
    try:
        completed = subprocess.run(
            [command.executable, *command.args],
            cwd=workspace,
            input=prompt if command.prompt_via_stdin else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        returncode = completed.returncode
        timed_out = False
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = None
        timed_out = True
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")

    (run_dir / "stdout.log").write_text(stdout, encoding="utf-8")
    (run_dir / "stderr.log").write_text(stderr, encoding="utf-8")
    after = fingerprint(workspace)
    changed = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
    forbidden_changes = [path for path in changed if path != "main.py"]

    validation_errors = []
    if timed_out:
        validation_errors.append(f"provider exceeded {timeout_seconds}s timeout")
    if returncode not in (0, None):
        validation_errors.append(f"provider exited with code {returncode}")
    if forbidden_changes:
        validation_errors.append("provider modified forbidden workspace files: " + ", ".join(forbidden_changes))
    if "main.py" not in changed:
        validation_errors.append("provider did not modify main.py")
    validation_errors.extend(validate_python_syntax(workspace / "main.py").errors)
    validation_errors.extend(validate_deck(workspace / "deck.csv").errors)

    candidate_imported = False
    if not validation_errors:
        copy_file_atomic(workspace / "main.py", experiment_dir / "candidate" / "main.py")
        candidate_imported = True

    worker_record = {
        "run": run_number,
        "provider": provider,
        "backend": command.backend,
        "model": args.model,
        "started_at": started_at,
        "finished_at": utc_now(),
        "dry_run": False,
        "returncode": returncode,
        "timed_out": timed_out,
        "candidate_imported": candidate_imported,
        "changed_files": changed,
        "validation_errors": validation_errors,
        "run_dir": str(run_dir.relative_to(experiment_dir)).replace("\\", "/"),
    }
    experiment.setdefault("worker_runs", []).append(worker_record)
    experiment["updated_at"] = utc_now()
    experiment["worker"] = provider
    write_json_atomic(experiment_dir / "experiment.json", experiment)
    write_json_atomic(run_dir / "result.json", worker_record)

    if not candidate_imported:
        print("ERROR: provider output was not imported into the candidate", file=sys.stderr)
        for error in validation_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Imported validated {provider} change into {experiment_dir / 'candidate' / 'main.py'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run coding providers inside isolated Plan_2 experiments.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    providers = subparsers.add_parser("providers", help="Report configured provider availability")
    providers.set_defaults(handler=list_providers)
    run = subparsers.add_parser("run", help="Run or dry-run a provider for the active experiment")
    run.add_argument("--specialist", required=True)
    run.add_argument("--provider", choices=("codex", "claude", "antigravity"))
    run.add_argument("--model")
    run.add_argument("--timeout-seconds", type=int)
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(handler=run_provider)
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
