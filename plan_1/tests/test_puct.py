from __future__ import annotations

import unittest

import _path  # noqa: F401

from plan1.game.records import PublicObservationRecord
from plan1.search.mcts import UCTSearch

from test_mcts import INPUTS, FakeEvaluator, TreeBackend, observation, search_config


class FakeInference:
    def policy(self, _record, candidates, _perspective):
        return tuple(0.8 if candidate.indices == (2,) else 0.1 for candidate in candidates)

    def value(self, _record, _perspective):
        return 1.0


class PUCTTests(unittest.TestCase):
    def test_policy_prior_controls_first_expansion(self) -> None:
        root = observation("root", 0, 1, 3)
        transitions = {
            ("root", (0,)): observation("a", 0, 1, 0, result=0),
            ("root", (1,)): observation("b", 0, 1, 0, result=0),
            ("root", (2,)): observation("c", 0, 1, 0, result=0),
        }
        result = UCTSearch(
            TreeBackend(root, transitions),
            FakeEvaluator(),
            search_config(max_simulations=1, require_full_root_coverage=False),
            cleanup_reserve_ms=10,
            rollout_policy=lambda _observation: [0],
            policy_value=FakeInference(),
        ).search(root, INPUTS, seed=7, fallback_action=[0])
        self.assertEqual(result.action, (2,))
        self.assertEqual(result.trace.version, "puct-v1")
        self.assertEqual(result.trace.root_edges[0].action, (2,))

    def test_learned_value_is_bounded_and_blended(self) -> None:
        root = observation("root", 0, 1, 2)
        search = UCTSearch(
            TreeBackend(root, {}),
            FakeEvaluator(),
            search_config(),
            cleanup_reserve_ms=10,
            policy_value=FakeInference(),
            learned_value_mix=0.25,
        )
        record = PublicObservationRecord.from_engine(root)
        self.assertAlmostEqual(search._value(record, 0), 0.25)


if __name__ == "__main__":
    unittest.main()
