from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from common import read_json, resolve_specialist, write_json_atomic


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Pause or resume a review-gated specialist without losing evidence.")
    parser.add_argument("action", choices=("pause", "resume"))
    parser.add_argument("--specialist", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()

    specialist = resolve_specialist(args.specialist)
    status = read_json(specialist / "status.json")
    experiment_id = status.get("active_experiment")
    if not experiment_id or status.get("state") != "REVIEW_REQUIRED":
        print("ERROR: specialist must have an active REVIEW_REQUIRED experiment", file=sys.stderr)
        return 2
    experiment_path = specialist / "experiments" / experiment_id / "experiment.json"
    experiment = read_json(experiment_path)
    orchestration = experiment.setdefault("orchestration", {})

    if args.action == "pause":
        if orchestration.get("state") == "PAUSED_BY_HUMAN":
            print(f"{specialist.name}/{experiment_id} is already paused")
            return 0
        orchestration["resume_state"] = orchestration.get("state", "REVIEW_REQUIRED")
        orchestration.update({
            "state": "PAUSED_BY_HUMAN",
            "paused_at": utc_now(),
            "pause_reason": args.reason,
        })
        verb = "paused"
    else:
        if orchestration.get("state") != "PAUSED_BY_HUMAN":
            print(f"ERROR: {specialist.name}/{experiment_id} is not paused", file=sys.stderr)
            return 2
        orchestration["state"] = orchestration.pop("resume_state", "REVIEW_REQUIRED")
        orchestration.update({
            "resumed_at": utc_now(),
            "resume_reason": args.reason,
        })
        verb = "resumed"

    experiment["updated_at"] = utc_now()
    experiment.setdefault("review_history", []).append({
        "stage": "operator_control",
        "decision": verb,
        "reason": args.reason,
        "at": utc_now(),
    })
    write_json_atomic(experiment_path, experiment)
    with (specialist / "PROGRESS.md").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            f"\n## {utc_now()[:10]} - specialist {verb}\n\n"
            f"- **{experiment_id} {verb} by human direction.**\n"
            f"  - Reason: {args.reason}\n"
            "  - Existing experiment and human-review evidence were preserved.\n"
        )
    print(f"{specialist.name}/{experiment_id}: {verb.upper()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
