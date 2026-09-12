from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import _bootstrap  # noqa: F401

from plan1.engine.conformance import (
    DEFAULT_MEMORY_TAIL_LIMIT_BYTES,
    conformance_passes,
    read_deck,
    run_coin_distribution_probe,
    run_conformance,
)
from plan1.paths import ARTIFACT_ROOT, REPO_ROOT
from plan1.reproducibility import sha256_file, write_json_atomic


DEFAULT_DECKS = (
    REPO_ROOT / "Decs" / "Hydrapple.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Fire.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Grass.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Dark.csv",
)
def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 1 conformance gate across multiple decks.")
    parser.add_argument("--deck", action="append", type=Path, dest="decks")
    parser.add_argument("--sessions", type=int, default=2000)
    parser.add_argument("--max-path-steps", type=int, default=600)
    parser.add_argument("--coin-trials", type=int, default=200)
    parser.add_argument("--output", type=Path, default=ARTIFACT_ROOT / "reports" / "phase1-suite.json")
    args = parser.parse_args()
    if args.sessions < 1 or args.max_path_steps < 1 or args.coin_trials < 2:
        parser.error("session/path counts must be positive and --coin-trials must be at least 2")

    reports = []
    for deck_path in args.decks or DEFAULT_DECKS:
        conformance = run_conformance(
            read_deck(deck_path),
            session_iterations=args.sessions,
            max_path_steps=args.max_path_steps,
        )
        result = conformance.to_dict()
        result["deck"] = str(deck_path.resolve())
        result["deck_sha256"] = sha256_file(deck_path)
        result["passed"] = conformance_passes(conformance)
        reports.append(result)
        print(f"{deck_path}: {'PASS' if result['passed'] else 'FAIL'}")

    coin = run_coin_distribution_probe(trials=args.coin_trials)
    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sessions_per_deck": args.sessions,
        "max_path_steps": args.max_path_steps,
        "tail_growth_limit_bytes": DEFAULT_MEMORY_TAIL_LIMIT_BYTES,
        "chance_events_observed": sum(item["replay_coin_events"] for item in reports) + coin["heads"] + coin["tails"],
        "coin_distribution": coin,
        "passed": all(item["passed"] for item in reports) and coin["passed"],
        "decks": reports,
    }
    write_json_atomic(args.output, report)
    print(f"Wrote {args.output}")
    print(f"chance_events_observed: {report['chance_events_observed']}")
    print(f"passed: {report['passed']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
