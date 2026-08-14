from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plan1.optimization.config import load_optimization_config
from plan1.optimization.suite import run_optimization_suite
from plan1.reproducibility import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 10 optimization suite")
    parser.add_argument("--config", type=Path, default=Path("plan_1/configs/phase10_optimization.json"))
    parser.add_argument("--output", type=Path, default=Path("plan_1/artifacts/reports/phase10-suite.json"))
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--search-only", action="store_true")
    args = parser.parse_args()
    config = load_optimization_config(args.config)
    if args.validate_only:
        pairs = len(config.search_variants) * (len(config.search_variants) - 1) // 2
        result = {
            "run_id": config.run_id,
            "search_games": pairs * len(config.deck_paths) * config.games_per_pair,
            "model_dimensions": list(config.model_ablation.dimensions),
            "validated": True,
        }
    else:
        report = run_optimization_suite(
            config,
            config_path=args.config,
            output=args.output,
            include_model=not args.search_only,
        )
        result = {
            "run_id": config.run_id,
            "output": str(args.output.resolve()),
            "sha256": sha256_file(args.output),
            "search": report["search_analysis"],
            "selected_model_dimension": (
                None
                if report["model_ablation"] is None
                else report["model_ablation"]["selected_dimension"]
            ),
        }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
