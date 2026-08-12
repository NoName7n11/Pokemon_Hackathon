from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import SUB_AGENTS_ROOT, read_json, resolve_specialist, update_registry_specialist, write_json_atomic


TOOLS_DIR = Path(__file__).resolve().parent


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def active_review(specialist: Path):
    status = read_json(specialist / "status.json")
    if status.get("review_state") != "REVIEW_REQUIRED" or not status.get("active_experiment"):
        raise ValueError(f"{specialist.name} has no pending human review")
    directory = specialist / "experiments" / status["active_experiment"]
    experiment = read_json(directory / "experiment.json")
    pending = next((review for review in reversed(experiment.get("reviews", [])) if review["status"] == "pending"), None)
    if pending is None:
        raise ValueError("experiment has no pending review record")
    return status, directory, experiment, pending


def move_review_files(pending: dict, destination_name: str) -> None:
    destination = SUB_AGENTS_ROOT / "human-review" / destination_name
    destination.mkdir(parents=True, exist_ok=True)
    for key in ("json", "markdown"):
        source = SUB_AGENTS_ROOT / pending[key]
        if source.is_file():
            target = destination / source.name
            if key == "json":
                review = read_json(source)
                review.update({
                    "decision": pending["status"],
                    "reviewer_reason": pending.get("reason", ""),
                    "reviewed_at": pending.get("reviewed_at"),
                })
                write_json_atomic(source, review)
            shutil.move(str(source), str(target))
            pending[key] = str(target.relative_to(SUB_AGENTS_ROOT)).replace("\\", "/")


def approve(args) -> int:
    specialist = resolve_specialist(args.specialist)
    status, directory, experiment, pending = active_review(specialist)
    if pending.get("stage") != "screening":
        raise ValueError("approve authorizes deep evaluation only from the screening review; use accept after confirmation")
    pending.update({"status": "approved_for_deep_evaluation", "reviewed_at": utc_now(), "reason": args.reason})
    move_review_files(pending, "approved")
    status.update({"state": "EXPERIMENT_ACTIVE", "review_state": "AUTOMATIC", "updated_at": utc_now()})
    experiment.update({"status": "RUNNING", "updated_at": utc_now()})
    experiment.setdefault("orchestration", {}).update({
        "state": "MAIN_AUTHORIZED",
        "review_pack": pending["markdown"],
        "updated_at": utc_now(),
    })
    experiment.setdefault("review_history", []).append({
        "stage": pending["stage"], "decision": "approved_for_deep_evaluation", "reason": args.reason, "at": utc_now()
    })
    write_json_atomic(specialist / "status.json", status)
    write_json_atomic(directory / "experiment.json", experiment)
    update_registry_specialist(specialist.name, state=status["state"], active_experiment=experiment["id"])
    print(f"{specialist.name}/{experiment['id']}: approved for deep evaluation only")
    return 0


def accept(args) -> int:
    specialist = resolve_specialist(args.specialist)
    status, directory, experiment, pending = active_review(specialist)
    if pending.get("stage") != "confirmation":
        raise ValueError("private acceptance requires the final confirmation review")
    config = read_json(specialist / "config.json")
    policy = read_json((specialist / config["benchmark_policy"]).resolve())
    required = int(policy.get("required_cross_deck_opponents", 0))
    completed = {
        result.get("opponent") for result in experiment.get("cross_deck_results", [])
        if result.get("status") == "complete"
    }
    if len(completed) < required:
        raise ValueError(f"final acceptance requires {required} cross-deck opponents; found {len(completed)}")
    pending.update({"status": "approved_for_acceptance", "reviewed_at": utc_now(), "reason": args.reason})
    move_review_files(pending, "approved")
    experiment.setdefault("review_history", []).append({
        "stage": pending["stage"], "decision": "approved_for_acceptance", "reason": args.reason, "at": utc_now()
    })
    experiment.setdefault("orchestration", {}).update({
        "state": "ACCEPTANCE_AUTHORIZED",
        "review_pack": pending["markdown"],
        "updated_at": utc_now(),
    })
    write_json_atomic(directory / "experiment.json", experiment)
    completed = subprocess.run(
        [
            sys.executable, str(TOOLS_DIR / "run_experiment.py"), "decide",
            "--specialist", specialist.name, "--accept", "--reason", f"final human approval: {args.reason}",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        print(completed.stdout, file=sys.stderr)
        print(completed.stderr, file=sys.stderr)
        return completed.returncode
    print(completed.stdout.strip())
    return 0


def reject(args) -> int:
    specialist = resolve_specialist(args.specialist)
    _, directory, experiment, pending = active_review(specialist)
    pending.update({"status": "rejected", "reviewed_at": utc_now(), "reason": args.reason})
    move_review_files(pending, "rejected")
    experiment.setdefault("review_history", []).append({
        "stage": pending["stage"], "decision": "rejected", "reason": args.reason, "at": utc_now()
    })
    experiment.setdefault("orchestration", {}).update({
        "state": "REJECTED_BY_HUMAN",
        "review_pack": pending["markdown"],
        "updated_at": utc_now(),
    })
    write_json_atomic(directory / "experiment.json", experiment)
    completed = subprocess.run(
        [
            sys.executable, str(TOOLS_DIR / "run_experiment.py"), "decide",
            "--specialist", specialist.name, "--reject", "--reason", f"human review rejection: {args.reason}",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        print(completed.stdout, file=sys.stderr)
        print(completed.stderr, file=sys.stderr)
        return completed.returncode
    print(completed.stdout.strip())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a Plan_2 human-review gate.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    approve_parser = subparsers.add_parser("approve", help="Authorize deep evaluation after screening")
    approve_parser.add_argument("--specialist", required=True)
    approve_parser.add_argument("--reason", required=True)
    approve_parser.set_defaults(handler=approve)
    accept_parser = subparsers.add_parser("accept", help="Accept a privately confirmed candidate; never promotes submission")
    accept_parser.add_argument("--specialist", required=True)
    accept_parser.add_argument("--reason", required=True)
    accept_parser.set_defaults(handler=accept)
    reject_parser = subparsers.add_parser("reject", help="Reject and close the candidate")
    reject_parser.add_argument("--specialist", required=True)
    reject_parser.add_argument("--reason", required=True)
    reject_parser.set_defaults(handler=reject)
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
