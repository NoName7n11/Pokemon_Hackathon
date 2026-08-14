from __future__ import annotations

import argparse
import json
from pathlib import Path

import _bootstrap  # noqa: F401

from plan1.model.policy_value import ModelConfig
from plan1.model.validation import run_phase7_suite
from plan1.paths import ARTIFACT_ROOT, REPO_ROOT


DEFAULT_DECKS = (
    REPO_ROOT / "Decs" / "Hydrapple.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Fire.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Grass.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Dark.csv",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 7 supervised policy-value validation.")
    parser.add_argument("--deck", action="append", type=Path, dest="decks")
    parser.add_argument("--corpus-games", type=int, default=48)
    parser.add_argument("--screen-games", type=int, default=20)
    parser.add_argument("--run-id", default="phase7-bootstrap-v1")
    parser.add_argument("--seed", type=int, default=7027)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--feature-dimension", type=int, default=8192)
    parser.add_argument("--max-steps", type=int, default=3000)
    parser.add_argument(
        "--corpus-root", type=Path,
        default=ARTIFACT_ROOT / "trajectories" / "phase7-bootstrap",
    )
    parser.add_argument(
        "--checkpoint", type=Path,
        default=ARTIFACT_ROOT / "checkpoints" / "phase7-bootstrap-v1.json",
    )
    parser.add_argument(
        "--output", type=Path,
        default=ARTIFACT_ROOT / "reports" / "phase7-suite.json",
    )
    args = parser.parse_args()
    decks = tuple(args.decks or DEFAULT_DECKS)
    report = run_phase7_suite(
        decks,
        corpus_root=args.corpus_root,
        corpus_games=args.corpus_games,
        run_id=args.run_id,
        root_seed=args.seed,
        checkpoint_path=args.checkpoint,
        report_path=args.output,
        screen_deck=decks[0],
        screen_games=args.screen_games,
        max_steps=args.max_steps,
        model_config=ModelConfig(
            feature_dimension=args.feature_dimension,
            epochs=args.epochs,
            seed=args.seed,
        ),
    )
    print(json.dumps({
        "passed": report["passed"],
        "gates": report["gates"],
        "heldout_metrics": report["heldout_metrics"],
        "inference": report["inference"],
        "search_screen": {
            key: report["search_screen"][key]
            for key in ("candidate_wins", "baseline_wins", "draws", "noninferiority", "passed")
        },
    }, indent=2, ensure_ascii=True))
    print(f"Wrote {args.output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
