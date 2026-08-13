from __future__ import annotations

import argparse
import json
from pathlib import Path

import _bootstrap  # noqa: F401

from plan1.paths import ARTIFACT_ROOT, REPO_ROOT
from plan1.search.validation import (
    load_baseline_config,
    run_ablation,
    run_horizon_ablation,
    run_soak,
    validation_config,
)


DEFAULT_DECKS = (
    REPO_ROOT / "Decs" / "Hydrapple.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Fire.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Grass.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Dark.csv",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 4 MCTS safety soak or strength ablation.")
    parser.add_argument("mode", choices=("soak", "ablation", "horizon-ablation"))
    parser.add_argument("--deck", action="append", type=Path, dest="decks")
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument("--horizon-turns", type=int, choices=(0, 1), default=0)
    parser.add_argument("--time-budget-ms", type=int, default=24)
    parser.add_argument("--cleanup-reserve-ms", type=int, default=16)
    parser.add_argument("--simulations", type=int, default=4)
    parser.add_argument("--nodes", type=int, default=32)
    parser.add_argument("--candidates", type=int, default=8)
    parser.add_argument("--p95-limit-ms", type=float, default=35.0)
    parser.add_argument("--max-limit-ms", type=float, default=500.0)
    parser.add_argument("--hard-overrun-rate-limit", type=float, default=0.01)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = validation_config(
        load_baseline_config(),
        time_budget_ms=args.time_budget_ms,
        cleanup_reserve_ms=args.cleanup_reserve_ms,
        simulations=args.simulations,
        nodes=args.nodes,
        candidates=args.candidates,
    )
    if args.mode == "soak":
        output = args.output or ARTIFACT_ROOT / "reports" / "phase4-soak.json"
        report = run_soak(
            args.decks or DEFAULT_DECKS,
            total_games=args.games,
            max_steps=args.max_steps,
            config=config,
            horizon_turns=args.horizon_turns,
            p95_limit_ms=args.p95_limit_ms,
            max_limit_ms=args.max_limit_ms,
            hard_overrun_rate_limit=args.hard_overrun_rate_limit,
            report_path=output,
        )
        success = bool(report["passed"])
    elif args.mode == "ablation":
        decks = args.decks or [DEFAULT_DECKS[0]]
        if len(decks) != 1:
            raise ValueError("ablation mode accepts exactly one --deck")
        output = args.output or ARTIFACT_ROOT / "reports" / f"phase4-ablation-h{args.horizon_turns}.json"
        report = run_ablation(
            decks[0],
            games=args.games,
            max_steps=args.max_steps,
            config=config,
            horizon_turns=args.horizon_turns,
            report_path=output,
        )
        success = bool(report["passed_safety"])
    else:
        decks = args.decks or [DEFAULT_DECKS[0]]
        if len(decks) != 1:
            raise ValueError("horizon-ablation mode accepts exactly one --deck")
        output = args.output or ARTIFACT_ROOT / "reports" / "phase4-horizon-ablation.json"
        report = run_horizon_ablation(
            decks[0],
            games=args.games,
            max_steps=args.max_steps,
            config=config,
            report_path=output,
        )
        success = bool(report["passed_safety"])
    summary = {key: value for key, value in report.items() if key not in ("search", "config")}
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    print(f"Wrote {output}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
