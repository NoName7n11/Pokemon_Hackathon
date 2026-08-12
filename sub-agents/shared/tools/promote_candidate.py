from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import (
    ENGINE_PARENT,
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


PROMOTION_ROOT = SUB_AGENTS_ROOT / "promotion"
CONFIG_PATH = PROMOTION_ROOT / "promotion_config.json"
REQUESTS_ROOT = PROMOTION_ROOT / "requests"
SNAPSHOTS_ROOT = PROMOTION_ROOT / "snapshots"
MANIFESTS_ROOT = PROMOTION_ROOT / "manifests"
REPORT_PATH = PROMOTION_ROOT / "REPORT.md"
LOCK_PATH = PROMOTION_ROOT / ".promotion.lock"
TOURNAMENT_RESULTS = SUB_AGENTS_ROOT / "tournaments" / "results"
TOOLS_DIR = Path(__file__).resolve().parent


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def promotion_lock():
    PROMOTION_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError(f"another promotion operation is active: {LOCK_PATH}") from exc
    try:
        os.write(descriptor, f"pid={os.getpid()}\nstarted_at={utc_now()}\n".encode("ascii"))
        yield
    finally:
        os.close(descriptor)
        LOCK_PATH.unlink(missing_ok=True)


def safe_id(value: str, pattern: str, label: str) -> str:
    if not re.fullmatch(pattern, value):
        raise ValueError(f"invalid {label}: {value}")
    return value


def next_promotion_id() -> str:
    highest = 0
    for path in REQUESTS_ROOT.glob("PROM-*.json"):
        match = re.fullmatch(r"PROM-(\d+)", path.stem)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"PROM-{highest + 1:04d}"


def request_path(promotion_id: str) -> Path:
    safe_id(promotion_id, r"PROM-\d{4}", "promotion ID")
    path = REQUESTS_ROOT / f"{promotion_id}.json"
    if not path.is_file():
        raise ValueError(f"promotion request does not exist: {promotion_id}")
    return path


def tournament_summary(tournament_id: str) -> dict[str, Any]:
    safe_id(tournament_id, r"T-[A-Za-z0-9-]+", "tournament ID")
    path = TOURNAMENT_RESULTS / tournament_id / "summary.json"
    if not path.is_file():
        raise ValueError(f"tournament summary does not exist: {tournament_id}")
    return read_json(path)


def accepted_experiment(specialist: Path, status: dict[str, Any]) -> dict[str, Any]:
    experiment_id = status.get("accepted_experiment")
    if not experiment_id:
        raise ValueError("specialist has no privately accepted experiment")
    path = specialist / "experiments" / experiment_id / "experiment.json"
    if not path.is_file():
        raise ValueError(f"accepted experiment record is missing: {experiment_id}")
    experiment = read_json(path)
    if experiment.get("decision") != "accepted":
        raise ValueError(f"accepted experiment is not marked accepted: {experiment_id}")
    return experiment


def verify_candidate(
    specialist: Path,
    tournament_id: str,
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    registry = read_json(SUB_AGENTS_ROOT / "registry.json")
    registry_entry = next((entry for entry in registry.get("specialists", []) if entry["name"] == specialist.name), None)
    if registry_entry is None:
        raise ValueError(f"specialist is not registered: {specialist.name}")
    status = read_json(specialist / "status.json")
    if status.get("state") != "READY_FOR_EXPERIMENT" or status.get("active_experiment"):
        raise ValueError("specialist must be READY_FOR_EXPERIMENT with no active experiment")
    summary = tournament_summary(tournament_id)
    if summary.get("status") != "complete" or summary.get("engine_crashes"):
        raise ValueError("tournament must be complete with zero engine crashes")
    if int(summary.get("games_per_seat", 0)) < int(config["minimum_tournament_games_per_seat"]):
        raise ValueError(
            f"tournament used {summary.get('games_per_seat', 0)} games per seat; "
            f"requires {config['minimum_tournament_games_per_seat']}"
        )
    if len(summary.get("entrants", [])) < int(config["minimum_tournament_entrants"]):
        raise ValueError(
            f"tournament has {len(summary.get('entrants', []))} entrants; "
            f"requires {config['minimum_tournament_entrants']}"
        )
    if summary.get("provisional_champion") != specialist.name:
        raise ValueError(f"specialist is not tournament champion: {summary.get('provisional_champion')}")
    ranking = next((row for row in summary.get("ranking", []) if row["name"] == specialist.name), None)
    if ranking is None or ranking.get("rank") != 1:
        raise ValueError("specialist is not ranked first")
    if config.get("require_fault_free_winner", True) and (
        not ranking.get("fault_free") or ranking.get("agent_crashes") or ranking.get("illegal_actions")
    ):
        raise ValueError("tournament winner is not fault-free")
    entrant = next((entry for entry in summary.get("entrants", []) if entry["name"] == specialist.name), None)
    if entrant is None:
        raise ValueError("tournament does not contain specialist entrant manifest")

    current_hashes = {
        "agent_sha256": sha256_file(specialist / "main.py"),
        "deck_sha256": sha256_file(specialist / "deck.csv"),
    }
    for key, value in current_hashes.items():
        if entrant.get(key) != value or registry_entry.get(key) != value or status.get(key) != value:
            raise ValueError(f"stale or inconsistent {key} for tournament winner")
    if entrant.get("version") != status.get("current_version"):
        raise ValueError("tournament version is stale relative to current specialist")
    if summary.get("auto_promote") is not False:
        raise ValueError("tournament summary does not preserve the no-auto-promotion boundary")

    experiment = accepted_experiment(specialist, status)
    confirmation = experiment.get("confirmation_result") or {}
    if int(confirmation.get("games", 0)) < int(config["minimum_confirmation_games"]):
        raise ValueError(
            f"accepted experiment confirmation has {confirmation.get('games', 0)} games; "
            f"requires {config['minimum_confirmation_games']}"
        )
    cross_deck = {
        item.get("opponent") for item in experiment.get("cross_deck_results", [])
        if item.get("status") == "complete"
    }
    if len(cross_deck) < int(config["minimum_cross_deck_opponents"]):
        raise ValueError(
            f"accepted experiment has {len(cross_deck)} cross-deck opponents; "
            f"requires {config['minimum_cross_deck_opponents']}"
        )

    for report in (validate_deck(specialist / "deck.csv"), validate_python_syntax(specialist / "main.py")):
        if not report.ok:
            raise ValueError("candidate validation failed: " + "; ".join(report.errors))
    return status, experiment, summary, entrant


def append_report(record: dict[str, Any], event: str, detail: str) -> None:
    marker = f"<!-- promotion:{record['id']}:{event} -->"
    if REPORT_PATH.is_file() and marker in REPORT_PATH.read_text(encoding="utf-8"):
        return
    is_new = not REPORT_PATH.is_file() or REPORT_PATH.stat().st_size == 0
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w" if is_new else "a", encoding="utf-8") as handle:
        if is_new:
            handle.write(
                "# Controlled Promotion History\n\n"
                "Append-only record of promotion requests, approvals, executions, failures, and rollbacks.\n\n"
            )
        handle.write(
            f"{marker}\n## {utc_now()} - {record['id']} - {event}\n\n"
            f"- Specialist: `{record['specialist']}` (`{record['specialist_version']}`)\n"
            f"- Tournament: `{record['tournament_id']}`\n"
            f"- State: `{record['state']}`\n"
            f"- Detail: {detail}\n\n"
        )


def request(args) -> int:
    specialist = resolve_specialist(args.specialist)
    config = read_json(CONFIG_PATH)
    status, experiment, summary, entrant = verify_candidate(specialist, args.tournament, config)
    with promotion_lock():
        promotion_id = next_promotion_id()
        now = utc_now()
        record = {
            "schema_version": 1,
            "id": promotion_id,
            "specialist": specialist.name,
            "specialist_version": status["current_version"],
            "tournament_id": args.tournament,
            "state": "PENDING_APPROVAL",
            "requested_at": now,
            "updated_at": now,
            "reason": args.reason,
            "source": {
                "agent": str((specialist / "main.py").relative_to(REPO_ROOT)).replace("\\", "/"),
                "deck": str((specialist / "deck.csv").relative_to(REPO_ROOT)).replace("\\", "/"),
                "agent_sha256": entrant["agent_sha256"],
                "deck_sha256": entrant["deck_sha256"],
                "accepted_experiment": experiment["id"],
            },
            "tournament": {
                "games_per_seat": summary["games_per_seat"],
                "entrants": len(summary["entrants"]),
                "rank": 1,
                "field_win_rate": next(row["field_win_rate"] for row in summary["ranking"] if row["name"] == specialist.name),
            },
            "approval": None,
            "execution": None,
        }
        REQUESTS_ROOT.mkdir(parents=True, exist_ok=True)
        write_json_atomic(REQUESTS_ROOT / f"{promotion_id}.json", record)
        append_report(record, "REQUESTED", args.reason)
    print(f"Created promotion request {promotion_id}; explicit human approval is required.")
    return 0


def approve(args) -> int:
    if not args.acknowledge_submission_change:
        raise ValueError("approval requires --acknowledge-submission-change")
    with promotion_lock():
        path = request_path(args.promotion)
        record = read_json(path)
        if record["state"] != "PENDING_APPROVAL":
            raise ValueError(f"promotion is not pending approval: {record['state']}")
        record["approval"] = {
            "reviewer": args.reviewer,
            "reason": args.reason,
            "approved_at": utc_now(),
            "acknowledged_submission_change": True,
        }
        record["state"] = "APPROVED"
        record["updated_at"] = utc_now()
        write_json_atomic(path, record)
        append_report(record, "APPROVED", f"{args.reviewer}: {args.reason}")
    print(f"Approved {record['id']}; execute remains a separate command.")
    return 0


def copy_pair_atomic(source: Path, destination: Path, rollback: Path | None = None) -> None:
    try:
        copy_file_atomic(source / "main.py", destination / "main.py")
        copy_file_atomic(source / "deck.csv", destination / "deck.csv")
    except Exception:
        if rollback is not None:
            copy_file_atomic(rollback / "main.py", destination / "main.py")
            copy_file_atomic(rollback / "deck.csv", destination / "deck.csv")
        raise


def snapshot_submission(promotion_id: str, submission_dir: Path = ENGINE_PARENT) -> Path:
    snapshot = SNAPSHOTS_ROOT / promotion_id
    if snapshot.exists():
        raise ValueError(f"promotion snapshot already exists: {snapshot}")
    snapshot.mkdir(parents=True)
    shutil.copy2(submission_dir / "main.py", snapshot / "main.py")
    shutil.copy2(submission_dir / "deck.csv", snapshot / "deck.csv")
    write_json_atomic(
        snapshot / "manifest.json",
        {
            "promotion_id": promotion_id,
            "created_at": utc_now(),
            "agent_sha256": sha256_file(snapshot / "main.py"),
            "deck_sha256": sha256_file(snapshot / "deck.csv"),
        },
    )
    return snapshot


def runtime_import(agent_path: Path) -> None:
    script = (
        "import importlib.util, pathlib, sys; "
        f"sys.path.insert(0, {str(ENGINE_PARENT)!r}); "
        f"p=pathlib.Path({str(agent_path)!r}); "
        "s=importlib.util.spec_from_file_location('promoted_submission', p); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "assert callable(getattr(m, 'agent', None)); assert callable(getattr(m, 'read_deck_csv', None))"
    )
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30, check=False)
    if completed.returncode != 0:
        raise ValueError(f"promoted runtime import failed: {completed.stderr.strip()}")


def run_submission_smoke(record: dict[str, Any], snapshot: Path, config: dict[str, Any]) -> dict[str, Any]:
    logs = MANIFESTS_ROOT / record["id"]
    logs.mkdir(parents=True, exist_ok=True)
    matchup_output = logs / "pair-smoke.json"
    command = [
        sys.executable, str(TOOLS_DIR / "matchup_pair.py"),
        "--agent-a", str(ENGINE_PARENT / "main.py"),
        "--deck-a", str(ENGINE_PARENT / "deck.csv"),
        "--name-a", f"promoted-{record['specialist']}",
        "--version-a", record["specialist_version"],
        "--agent-b", str(snapshot / "main.py"),
        "--deck-b", str(snapshot / "deck.csv"),
        "--name-b", "previous-submission",
        "--version-b", "snapshot",
        "--games-per-seat", str(int(config["submission_smoke_games"]) // 2),
        "--max-steps", "3000",
        "--seed", "20260813",
        "--output", str(matchup_output),
    ]
    completed = subprocess.run(
        command,
        cwd=ENGINE_PARENT,
        capture_output=True,
        text=True,
        timeout=int(config["smoke_timeout_seconds"]),
        check=False,
    )
    (logs / "pair-smoke.log").write_text(completed.stdout + "\nSTDERR:\n" + completed.stderr, encoding="utf-8")
    if completed.returncode != 0 or not matchup_output.is_file():
        raise ValueError(f"submission pair smoke failed with exit {completed.returncode}")
    result = read_json(matchup_output)
    candidate_faults = result["faults"]["a"]
    if result["engine_crashes"] or result["timeouts"] or candidate_faults["crashes"] or candidate_faults["illegal_actions"]:
        raise ValueError("submission pair smoke recorded a candidate or engine failure")

    package = subprocess.run(
        [sys.executable, "benchmark.py", str(config["submission_smoke_games"])],
        cwd=ENGINE_PARENT,
        capture_output=True,
        text=True,
        timeout=int(config["smoke_timeout_seconds"]),
        check=False,
    )
    (logs / "package-smoke.log").write_text(package.stdout + "\nSTDERR:\n" + package.stderr, encoding="utf-8")
    if package.returncode != 0:
        raise ValueError(f"submission-directory package smoke failed with exit {package.returncode}")
    return {
        "pair_smoke": str(matchup_output.relative_to(PROMOTION_ROOT)).replace("\\", "/"),
        "pair_smoke_games": result["games"],
        "package_smoke_games": int(config["submission_smoke_games"]),
        "logs": [
            str((logs / "pair-smoke.log").relative_to(PROMOTION_ROOT)).replace("\\", "/"),
            str((logs / "package-smoke.log").relative_to(PROMOTION_ROOT)).replace("\\", "/"),
        ],
    }


def execute(args) -> int:
    config = read_json(CONFIG_PATH)
    with promotion_lock():
        path = request_path(args.promotion)
        record = read_json(path)
        if record["state"] != "APPROVED" or not record.get("approval"):
            raise ValueError("promotion requires an approved request")
        specialist = resolve_specialist(record["specialist"])
        status, _, _, _ = verify_candidate(specialist, record["tournament_id"], config)
        if status["current_version"] != record["specialist_version"]:
            raise ValueError("approved request is stale: specialist version changed")
        if sha256_file(specialist / "main.py") != record["source"]["agent_sha256"]:
            raise ValueError("approved request is stale: agent hash changed")
        if sha256_file(specialist / "deck.csv") != record["source"]["deck_sha256"]:
            raise ValueError("approved request is stale: deck hash changed")

        snapshot = snapshot_submission(record["id"])
        record["state"] = "PROMOTING"
        record["updated_at"] = utc_now()
        write_json_atomic(path, record)
        try:
            copy_pair_atomic(specialist, ENGINE_PARENT, rollback=snapshot)
            for report in (validate_deck(ENGINE_PARENT / "deck.csv"), validate_python_syntax(ENGINE_PARENT / "main.py")):
                if not report.ok:
                    raise ValueError("promoted submission validation failed: " + "; ".join(report.errors))
            runtime_import(ENGINE_PARENT / "main.py")
            smoke = run_submission_smoke(record, snapshot, config)
        except Exception as exc:
            copy_pair_atomic(snapshot, ENGINE_PARENT)
            record["state"] = "FAILED_ROLLED_BACK"
            record["updated_at"] = utc_now()
            record["execution"] = {"failed_at": utc_now(), "error": f"{type(exc).__name__}: {exc}", "rollback": "automatic"}
            write_json_atomic(path, record)
            append_report(record, "FAILED_ROLLED_BACK", str(exc))
            raise

        record["state"] = "PROMOTED"
        record["updated_at"] = utc_now()
        record["execution"] = {
            "promoted_at": utc_now(),
            "snapshot": str(snapshot.relative_to(PROMOTION_ROOT)).replace("\\", "/"),
            "submission_agent_sha256": sha256_file(ENGINE_PARENT / "main.py"),
            "submission_deck_sha256": sha256_file(ENGINE_PARENT / "deck.csv"),
            "smoke": smoke,
        }
        write_json_atomic(path, record)
        MANIFESTS_ROOT.mkdir(parents=True, exist_ok=True)
        write_json_atomic(MANIFESTS_ROOT / f"{record['id']}.json", record)
        append_report(record, "PROMOTED", "Atomic pair promotion and submission-directory smoke passed.")
    print(f"Promoted {record['specialist']} through {record['id']}")
    return 0


def rollback(args) -> int:
    if not args.acknowledge_rollback:
        raise ValueError("rollback requires --acknowledge-rollback")
    with promotion_lock():
        path = request_path(args.promotion)
        record = read_json(path)
        if record["state"] != "PROMOTED":
            raise ValueError(f"only a promoted request can be rolled back: {record['state']}")
        snapshot = SNAPSHOTS_ROOT / record["id"]
        manifest = read_json(snapshot / "manifest.json")
        copy_pair_atomic(snapshot, ENGINE_PARENT)
        if sha256_file(ENGINE_PARENT / "main.py") != manifest["agent_sha256"]:
            raise ValueError("rollback agent hash verification failed")
        if sha256_file(ENGINE_PARENT / "deck.csv") != manifest["deck_sha256"]:
            raise ValueError("rollback deck hash verification failed")
        runtime_import(ENGINE_PARENT / "main.py")
        record["state"] = "ROLLED_BACK"
        record["updated_at"] = utc_now()
        record.setdefault("execution", {})["rollback"] = {
            "at": utc_now(), "reason": args.reason, "verified_snapshot_hashes": True
        }
        write_json_atomic(path, record)
        write_json_atomic(MANIFESTS_ROOT / f"{record['id']}.json", record)
        append_report(record, "ROLLED_BACK", args.reason)
    print(f"Rolled back {record['id']} to its preserved submission snapshot")
    return 0


def self_test(_args) -> int:
    PROMOTION_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="promotion-self-test-", dir=PROMOTION_ROOT) as temporary:
        root = Path(temporary)
        current = root / "current"
        candidate = root / "candidate"
        snapshot = root / "snapshot"
        for directory in (current, candidate, snapshot):
            directory.mkdir()
        shutil.copy2(ENGINE_PARENT / "main.py", current / "main.py")
        shutil.copy2(ENGINE_PARENT / "deck.csv", current / "deck.csv")
        shutil.copy2(current / "main.py", snapshot / "main.py")
        shutil.copy2(current / "deck.csv", snapshot / "deck.csv")
        venusaur = resolve_specialist("Claude_Grass_Venusaur")
        shutil.copy2(venusaur / "main.py", candidate / "main.py")
        shutil.copy2(venusaur / "deck.csv", candidate / "deck.csv")
        original = (sha256_file(current / "main.py"), sha256_file(current / "deck.csv"))
        copy_pair_atomic(candidate, current, rollback=snapshot)
        promoted = (sha256_file(current / "main.py"), sha256_file(current / "deck.csv"))
        expected = (sha256_file(candidate / "main.py"), sha256_file(candidate / "deck.csv"))
        if promoted != expected:
            raise ValueError("isolated promotion self-test hash mismatch")
        copy_pair_atomic(snapshot, current)
        rolled_back = (sha256_file(current / "main.py"), sha256_file(current / "deck.csv"))
        if rolled_back != original:
            raise ValueError("isolated rollback self-test hash mismatch")
        (candidate / "deck.csv").unlink()
        try:
            copy_pair_atomic(candidate, current, rollback=snapshot)
        except OSError:
            pass
        else:
            raise ValueError("isolated failure test unexpectedly promoted an incomplete pair")
        automatically_rolled_back = (sha256_file(current / "main.py"), sha256_file(current / "deck.csv"))
        if automatically_rolled_back != original:
            raise ValueError("automatic rollback after partial-copy failure did not restore original hashes")
    print("Isolated atomic promotion, explicit rollback, and failure rollback self-test: PASS")
    return 0


def status(_args) -> int:
    records = [read_json(path) for path in sorted(REQUESTS_ROOT.glob("PROM-*.json"))]
    print(json.dumps({"requests": records}, indent=2, ensure_ascii=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlled Plan_2 submission promotion.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    request_parser = subparsers.add_parser("request")
    request_parser.add_argument("--specialist", required=True)
    request_parser.add_argument("--tournament", required=True)
    request_parser.add_argument("--reason", required=True)
    request_parser.set_defaults(handler=request)
    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--promotion", required=True)
    approve_parser.add_argument("--reviewer", required=True)
    approve_parser.add_argument("--reason", required=True)
    approve_parser.add_argument("--acknowledge-submission-change", action="store_true")
    approve_parser.set_defaults(handler=approve)
    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--promotion", required=True)
    execute_parser.set_defaults(handler=execute)
    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.add_argument("--promotion", required=True)
    rollback_parser.add_argument("--reason", required=True)
    rollback_parser.add_argument("--acknowledge-rollback", action="store_true")
    rollback_parser.set_defaults(handler=rollback)
    self_test_parser = subparsers.add_parser("self-test")
    self_test_parser.set_defaults(handler=self_test)
    status_parser = subparsers.add_parser("status")
    status_parser.set_defaults(handler=status)
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, KeyError, TimeoutError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
