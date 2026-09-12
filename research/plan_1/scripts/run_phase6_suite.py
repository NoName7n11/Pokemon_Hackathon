from __future__ import annotations

import argparse
import json
from pathlib import Path

import _bootstrap  # noqa: F401

from plan1.data.validation import run_phase6_suite
from plan1.paths import ARTIFACT_ROOT, REPO_ROOT


DEFAULT_DECKS = (
    REPO_ROOT / "Decs" / "Hydrapple.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Fire.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Grass.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Dark.csv",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 6 trajectory pipeline validation.")
    parser.add_argument("--deck", action="append", type=Path, dest="decks")
    parser.add_argument("--games", type=int, default=12)
    parser.add_argument("--evaluation-games", type=int, default=2)
    parser.add_argument("--run-id", default="phase6-live-v1")
    parser.add_argument("--seed", type=int, default=6026)
    parser.add_argument("--max-steps", type=int, default=3000)
    parser.add_argument("--max-candidates", type=int, default=64)
    parser.add_argument(
        "--corpus-root", type=Path,
        default=ARTIFACT_ROOT / "trajectories" / "phase6-validation",
    )
    parser.add_argument(
        "--scratch-root", type=Path,
        default=ARTIFACT_ROOT / "tmp" / "phase6-corruption-copy",
    )
    parser.add_argument(
        "--output", type=Path,
        default=ARTIFACT_ROOT / "reports" / "phase6-suite.json",
    )
    args = parser.parse_args()
    report = run_phase6_suite(
        args.decks or DEFAULT_DECKS,
        corpus_root=args.corpus_root,
        run_id=args.run_id,
        games=args.games,
        evaluation_games=args.evaluation_games,
        root_seed=args.seed,
        max_steps=args.max_steps,
        max_candidates=args.max_candidates,
        report_path=args.output,
        scratch_root=args.scratch_root,
    )
    summary = {
        key: value for key, value in report.items()
        if key not in {"configuration", "decks"}
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    print(f"Wrote {args.output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
