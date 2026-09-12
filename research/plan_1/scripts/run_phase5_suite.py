from __future__ import annotations

import argparse
import json
from pathlib import Path

import _bootstrap  # noqa: F401

from plan1.belief.validation import run_phase5_suite
from plan1.paths import ARTIFACT_ROOT, REPO_ROOT
from plan1.search.validation import load_baseline_config, validation_config


DEFAULT_DECKS = (
    REPO_ROOT / "Decs" / "Hydrapple.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Fire.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Grass.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Dark.csv",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 5 belief and ISMCTS validation suite.")
    parser.add_argument("--deck", action="append", type=Path, dest="decks")
    parser.add_argument("--decisions", type=int, default=24)
    parser.add_argument("--determinizations", type=int, default=4)
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument("--time-budget-ms", type=int, default=24)
    parser.add_argument("--cleanup-reserve-ms", type=int, default=16)
    parser.add_argument("--simulations", type=int, default=4)
    parser.add_argument("--nodes", type=int, default=32)
    parser.add_argument("--candidates", type=int, default=8)
    parser.add_argument(
        "--output",
        type=Path,
        default=ARTIFACT_ROOT / "reports" / "phase5-suite.json",
    )
    args = parser.parse_args()
    config = validation_config(
        load_baseline_config(),
        time_budget_ms=args.time_budget_ms,
        cleanup_reserve_ms=args.cleanup_reserve_ms,
        simulations=args.simulations,
        nodes=args.nodes,
        candidates=args.candidates,
    )
    report = run_phase5_suite(
        args.decks or DEFAULT_DECKS,
        decisions=args.decisions,
        max_steps=args.max_steps,
        determinizations=args.determinizations,
        config=config,
        report_path=args.output,
    )
    summary = {key: value for key, value in report.items() if key not in ("samples", "search_config")}
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    print(f"Wrote {args.output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
