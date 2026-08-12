from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import (
    REPO_ROOT,
    SPECIALISTS_ROOT,
    SUB_AGENTS_ROOT,
    read_json,
    safe_specialist_name,
    sha256_file,
    validate_deck,
    validate_python_syntax,
    write_json_atomic,
)


PROVIDERS = ("codex", "claude", "antigravity")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def relative_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def progress_template(name: str, provider: str, source_deck: Path, baseline: Path, created_at: str) -> str:
    return f"""# {name} Specialist Progress

Append-only experiment log for this private Plan_2 specialist. This directory is
not the active submission.

---

## {created_at[:10]}

- **Specialist initialized**:
  - Worker provider: `{provider}`.
  - Source deck: `{relative_to_repo(source_deck)}`.
  - Agent baseline: `{relative_to_repo(baseline)}`.
  - Static deck and Python-interface validation passed.
  - Runtime import and gameplay benchmarks remain pending in an environment with
    the competition `cg` engine.
  - **Reason:** establish an isolated, reproducible deck-agent workspace before
    any automated strategic experiments begin.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an isolated Plan_2 deck specialist.")
    parser.add_argument("--deck", required=True, type=Path, help="Source deck.csv path")
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    parser.add_argument("--name", help="Specialist name; defaults to deck filename")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=SUB_AGENTS_ROOT / "shared" / "baseline" / "main.py",
        help="Source agent baseline",
    )
    args = parser.parse_args()

    source_deck = args.deck.resolve()
    baseline = args.baseline.resolve()
    try:
        name = safe_specialist_name(args.name or source_deck.stem)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    deck_report = validate_deck(source_deck)
    agent_report = validate_python_syntax(baseline)
    for report in (deck_report, agent_report):
        for error in report.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if not deck_report.ok or not agent_report.ok:
        return 1

    destination = SPECIALISTS_ROOT / name
    if destination.exists():
        print(f"ERROR: specialist already exists: {destination}", file=sys.stderr)
        return 2

    registry_path = SUB_AGENTS_ROOT / "registry.json"
    registry = read_json(registry_path)
    entries = registry.setdefault("specialists", [])
    if any(entry.get("name") == name for entry in entries):
        print(f"ERROR: specialist is already registered: {name}", file=sys.stderr)
        return 2

    created_at = utc_now()
    destination.mkdir(parents=True)
    try:
        for directory in ("experiments", "benchmarks", "battle_traces", "rejected", "snapshots"):
            (destination / directory).mkdir()
        shutil.copy2(source_deck, destination / "deck.csv")
        shutil.copy2(baseline, destination / "main.py")

        config = {
            "schema_version": 1,
            "name": name,
            "provider": args.provider,
            "worker_profile": None,
            "deck_file": "deck.csv",
            "agent_file": "main.py",
            "source_deck": relative_to_repo(source_deck),
            "source_baseline": relative_to_repo(baseline),
            "experiment_budget": {"max_experiments_per_run": 3, "max_runtime_minutes": 180},
            "benchmark_timeout_seconds": 1800,
            "benchmark_policy": "../../shared/benchmark_config.json",
            "provider_policy": "../../shared/provider_config.json",
            "orchestration_policy": "../../shared/orchestration_config.json",
            "cross_deck_opponents": [],
            "human_review": {
                "strategic_change": "REVIEW_REQUIRED",
                "promotion": "PROMOTION_REQUIRED"
            },
            "allowed_writes": ["."],
            "forbidden_writes": [
                "../../../sample_submission/sample_submission/main.py",
                "../../../sample_submission/sample_submission/deck.csv",
                "../*",
                "../../*"
            ],
            "strategy_notes": []
        }
        status = {
            "schema_version": 1,
            "state": "READY_FOR_BASELINE",
            "review_state": "AUTOMATIC",
            "current_version": "v000-baseline",
            "accepted_experiment": None,
            "active_experiment": None,
            "created_at": created_at,
            "updated_at": created_at,
            "deck_sha256": sha256_file(destination / "deck.csv"),
            "agent_sha256": sha256_file(destination / "main.py"),
            "validation": {
                "static": "passed",
                "runtime_import": "pending",
                "smoke_benchmark": "pending"
            }
        }
        write_json_atomic(destination / "config.json", config)
        write_json_atomic(destination / "status.json", status)
        (destination / "PROGRESS.md").write_text(
            progress_template(name, args.provider, source_deck, baseline, created_at),
            encoding="utf-8",
        )

        entry = {
            "name": name,
            "path": f"specialists/{name}",
            "provider": args.provider,
            "state": status["state"],
            "current_version": status["current_version"],
            "created_at": created_at,
            "deck_sha256": status["deck_sha256"],
            "agent_sha256": status["agent_sha256"]
        }
        entries.append(entry)
        entries.sort(key=lambda item: item["name"].lower())
        write_json_atomic(registry_path, registry)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise

    print(f"Created specialist: {destination}")
    print("Static validation: PASS")
    print("Next: run validate_agent.py with --runtime inside the configured cg environment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
