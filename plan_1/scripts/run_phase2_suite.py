from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401

from plan1.game.validation import run_phase2_suite
from plan1.paths import ARTIFACT_ROOT, REPO_ROOT


DEFAULT_DECKS = (
    REPO_ROOT / "Decs" / "Hydrapple.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Fire.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Grass.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Dark.csv",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 2 records and generated actions against live games.")
    parser.add_argument("--deck", action="append", type=Path, dest="decks")
    parser.add_argument("--games-per-deck", type=int, default=10)
    parser.add_argument("--max-steps", type=int, default=3000)
    parser.add_argument("--max-candidates", type=int, default=128)
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument(
        "--fixture-output",
        type=Path,
        default=ARTIFACT_ROOT / "fixtures" / "phase2-observations.jsonl",
    )
    parser.add_argument(
        "--vocabulary-output",
        type=Path,
        default=ARTIFACT_ROOT / "fixtures" / "phase2-vocabulary.json",
    )
    parser.add_argument(
        "--catalog-output",
        type=Path,
        default=ARTIFACT_ROOT / "fixtures" / "phase2-card-catalog.json",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=ARTIFACT_ROOT / "reports" / "phase2-suite.json",
    )
    args = parser.parse_args()
    report = run_phase2_suite(
        args.decks or DEFAULT_DECKS,
        games_per_deck=args.games_per_deck,
        max_steps=args.max_steps,
        max_candidates=args.max_candidates,
        seed=args.seed,
        fixture_path=args.fixture_output,
        vocabulary_path=args.vocabulary_output,
        catalog_path=args.catalog_output,
        report_path=args.report_output,
    )
    for deck in report["decks"]:
        print(
            f"{Path(deck['deck']).name}: {'PASS' if deck['passed'] else 'FAIL'} "
            f"games={deck['completed_games']}/{deck['games']} "
            f"decisions={deck['decisions']} candidates={deck['generated_candidates']} "
            f"native={deck['native_validated_candidates']}"
        )
        for error in deck["errors"][:3]:
            print(f"  error: {error}")
    print(f"fixtures: {report['fixture_count']} / observed pairs: {len(report['observed_selection_pairs'])}")
    print(f"totals: {report['totals']}")
    print(f"Wrote {args.report_output}")
    print(f"passed: {report['passed']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
