from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import SUB_AGENTS_ROOT, assigned_review_identity, normalize_worker_identity, read_json


PENDING_ROOT = SUB_AGENTS_ROOT / "human-review" / "pending"


def infer_assignment(review: dict[str, Any]) -> dict[str, str]:
    assigned = review.get("assigned_reviewer")
    if isinstance(assigned, dict) and assigned.get("reviewer"):
        return {
            "reviewer": str(assigned.get("reviewer", "")),
            "provider": str(assigned.get("provider", "")),
            "model": str(assigned.get("model", "")),
            "reason": str(assigned.get("reason", "")),
        }
    worker = review.get("worker_identity")
    if isinstance(worker, dict):
        identity = str(worker.get("identity") or normalize_worker_identity(worker.get("provider"), worker.get("model")))
        return assigned_review_identity(identity)
    provider_run = review.get("provider_run")
    if isinstance(provider_run, dict):
        identity = normalize_worker_identity(provider_run.get("provider"), provider_run.get("model"))
        return assigned_review_identity(identity)
    return assigned_review_identity("unknown")


def pending_reviews() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(PENDING_ROOT.glob("*.json")):
        try:
            review = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if not review.get("specialist") or not review.get("experiment") or review.get("decision") != "pending":
            continue
        assignment = infer_assignment(review)
        markdown = path.with_suffix(".md")
        if review.get("markdown"):
            markdown = SUB_AGENTS_ROOT / str(review["markdown"])
        items.append(
            {
                "specialist": review.get("specialist"),
                "experiment": review.get("experiment"),
                "stage": review.get("stage"),
                "created_at": review.get("created_at"),
                "assigned_reviewer": assignment,
                "json": str(path),
                "markdown": str(markdown),
                "hypothesis": review.get("hypothesis", ""),
            }
        )
    return items


def list_command(args) -> int:
    reviewer = args.reviewer.lower() if args.reviewer else None
    rows = [
        item for item in pending_reviews()
        if reviewer is None or item["assigned_reviewer"]["reviewer"].lower() == reviewer
    ]
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=True))
        return 0
    if not rows:
        print("No pending reviews match the requested reviewer.")
        return 0
    for item in rows:
        assignment = item["assigned_reviewer"]
        print(f"{item['specialist']}-{item['experiment']} ({item['stage']})")
        print(f"  reviewer: {assignment['reviewer']} [{assignment['provider']} {assignment['model']}]")
        print(f"  markdown: {item['markdown']}")
        print(f"  reason: {assignment['reason']}")
        print(f"  hypothesis: {item['hypothesis']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="List pending Plan_2 reviews by assigned reviewer.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list", help="List pending review packs")
    list_parser.add_argument("--reviewer", choices=("codex", "opus"))
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(handler=list_command)
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
