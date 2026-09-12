from __future__ import annotations

import argparse
import json
from pathlib import Path

import _bootstrap  # noqa: F401

from plan1.paths import CONFIG_ROOT
from plan1.selfplay.config import load_reinforcement_config
from plan1.selfplay.coordinator import ReinforcementCoordinator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run/resume the Phase 8 reinforcement loop.")
    parser.add_argument(
        "--config", type=Path,
        default=CONFIG_ROOT / "phase8_reinforcement.json",
    )
    parser.add_argument(
        "--stop-after-stage",
        choices=("selfplay", "training"),
        help="Controlled interruption probe; rerun without this flag to resume.",
    )
    args = parser.parse_args()
    config = load_reinforcement_config(args.config)
    result = ReinforcementCoordinator(config, config_path=args.config).run(
        stop_after_stage=args.stop_after_stage
    )
    print(json.dumps({
        "status": result["status"],
        "passed": result["passed"],
        "resume_count": result["resume_count"],
        "iterations_complete": result["iterations_complete"],
        "decisions": result["decisions"],
        "gates": result["gates"],
        "final_champion": result["final_champion"],
    }, indent=2, ensure_ascii=True))
    return 0 if result["passed"] or result["status"] == "paused" else 1


if __name__ == "__main__":
    raise SystemExit(main())
