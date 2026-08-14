from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plan1.league.config import load_league_config
from plan1.league.evaluator import build_schedule, run_league
from plan1.reproducibility import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen Phase 9 league suite")
    parser.add_argument("--config", type=Path, default=Path("plan_1/configs/phase9_league.json"))
    parser.add_argument("--output", type=Path, default=Path("plan_1/artifacts/reports/phase9-suite.json"))
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    config = load_league_config(args.config)
    if args.validate_only:
        result = {
            "run_id": config.run_id,
            "matchups": len(build_schedule(config)),
            "total_games": len(build_schedule(config)) * config.games_per_matchup,
            "validated": True,
        }
    else:
        report = run_league(
            config,
            config_path=args.config,
            output=args.output,
            workers=args.workers,
        )
        result = {
            "run_id": config.run_id,
            "output": str(args.output.resolve()),
            "sha256": sha256_file(args.output),
            "total_games": report["schedule"]["total_games"],
            "gate": report["analysis"]["gate"],
            "cycles": report["analysis"]["cyclic_dominance"]["cycles"],
        }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
