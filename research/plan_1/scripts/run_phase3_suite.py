from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401

from plan1.evaluation.validation import run_phase3_suite
from plan1.paths import ARTIFACT_ROOT, REPO_ROOT


DEFAULT_DECKS = (
    REPO_ROOT / "Decs" / "Hydrapple.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Fire.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Grass.csv",
    REPO_ROOT / "No_Name_Decks" / "No_Name_Dark.csv",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Phase 3 evaluator on tactical and live-game states.")
    parser.add_argument("--deck", action="append", type=Path, dest="decks")
    parser.add_argument("--games-per-deck", type=int, default=10)
    parser.add_argument("--max-steps", type=int, default=3000)
    parser.add_argument(
        "--report-output",
        type=Path,
        default=ARTIFACT_ROOT / "reports" / "phase3-suite.json",
    )
    args = parser.parse_args()
    report = run_phase3_suite(
        args.decks or DEFAULT_DECKS,
        games_per_deck=args.games_per_deck,
        max_steps=args.max_steps,
        report_path=args.report_output,
    )
    tactical = report["tactical"]
    print(f"tactical: {tactical['passed_count']}/{tactical['fixture_count']} passed")
    for deck in report["decks"]:
        print(
            f"{Path(deck['deck']).name}: {'PASS' if deck['passed'] else 'FAIL'} "
            f"games={deck['completed_games']}/{deck['games']} decisions={deck['decisions']} "
            f"eval_ms={deck['evaluator_ms_median']:.4f}/{deck['evaluator_ms_p95']:.4f} "
            f"native_step_ratio={deck['evaluator_to_simulator_median_ratio']:.3f}"
        )
        for error in deck["errors"][:3]:
            print(f"  error: {error}")
    print(f"totals: {report['totals']}")
    print(f"Wrote {args.report_output}")
    print(f"passed: {report['passed']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
