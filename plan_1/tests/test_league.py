from __future__ import annotations

import unittest
from pathlib import Path

import _path  # noqa: F401

from plan1.league.analysis import analyze_league, dominance_cycles, wilson_interval
from plan1.league.config import load_league_config
from plan1.league.evaluator import build_schedule


class LeagueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.config = load_league_config(cls.root / "plan_1" / "configs" / "phase9_league.json")

    def test_config_has_development_heldout_and_three_checkpoints(self) -> None:
        self.assertEqual({deck.split for deck in self.config.decks}, {"development", "heldout"})
        self.assertGreaterEqual(sum(policy.kind == "checkpoint" for policy in self.config.policies), 3)

    def test_schedule_is_seat_balance_compatible_and_cross_deck(self) -> None:
        schedule = build_schedule(self.config)
        self.assertEqual(len(schedule), len({item["matchup_id"] for item in schedule}))
        self.assertTrue(any(item["category"] == "cross_deck_specialist" for item in schedule))
        self.assertTrue(any(item["split"] == "heldout" for item in schedule))
        self.assertEqual(self.config.games_per_matchup % 2, 0)

    def test_promotion_config_allows_draws_before_decisive_minimum(self) -> None:
        promotion = load_league_config(
            self.root / "plan_1" / "configs" / "phase9_promotion_gate.json"
        )
        self.assertGreater(
            promotion.games_per_matchup,
            promotion.gates.minimum_matchup_decisive_games,
        )

    def test_wilson_interval_is_bounded(self) -> None:
        interval = wilson_interval(60, 100)
        self.assertIsNotNone(interval)
        assert interval is not None
        self.assertLess(interval[0], 0.6)
        self.assertGreater(interval[1], 0.6)

    def test_cycle_detection_finds_three_policy_cycle(self) -> None:
        matches = [
            {"left_policy": "a", "right_policy": "b", "left_wins": 6, "right_wins": 4},
            {"left_policy": "b", "right_policy": "c", "left_wins": 6, "right_wins": 4},
            {"left_policy": "c", "right_policy": "a", "left_wins": 6, "right_wins": 4},
        ]
        result = dominance_cycles(matches, {"a", "b", "c"}, minimum_rate=0.55, minimum_games=10)
        self.assertTrue(result["cyclic_dominance_detected"])
        self.assertEqual(len(result["cycles"]), 1)

    def test_small_screen_cannot_pass_evidence_gate(self) -> None:
        matches = []
        for item in build_schedule(self.config):
            matches.append({**item, "games": 2, "left_wins": 2, "right_wins": 0, "draws": 0, "faults": {}, "errors": []})
        result = analyze_league(self.config, matches)
        self.assertFalse(result["gate"]["evidence_sufficient"])
        self.assertFalse(result["gate"]["promoted"])
        self.assertEqual(result["gate"]["decision"], "insufficient_evidence")
        self.assertEqual(
            len(result["catastrophic_forgetting"]["comparisons"]),
            6,
        )

    def test_powered_aggregate_strength_failure_is_rejected(self) -> None:
        matches = []
        for item in build_schedule(self.config):
            candidate_left = item["left_policy"] == "phase8_champion_i001"
            matches.append({
                **item,
                "games": 24,
                "left_wins": 8 if candidate_left else 16,
                "right_wins": 16 if candidate_left else 8,
                "draws": 0,
                "faults": {},
                "errors": [],
            })
        result = analyze_league(self.config, matches)
        self.assertTrue(result["gate"]["aggregate_evidence_sufficient"])
        self.assertTrue(result["gate"]["conclusive_strength_rejection"])
        self.assertEqual(result["gate"]["decision"], "rejected")


if __name__ == "__main__":
    unittest.main()
