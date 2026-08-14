from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401

from plan1.data.manifests import SplitPolicy
from plan1.data.replay_buffer import CorpusStore
from plan1.selfplay.config import load_reinforcement_config
from plan1.selfplay.evaluation import promotion_decision
from plan1.selfplay.replay import select_replay_window
from plan1.selfplay.worker import _temperature_action
from plan1.search.mcts import EdgeTrace, SearchResult, SearchTrace

from test_trajectory import fixture_game


def search_result() -> SearchResult:
    edges = tuple(
        EdgeTrace(
            action=(index,), fingerprint=str(index) * 64, visits=visits,
            value_sum=0.0, mean_value=0.0, immediate_reward=0.0,
            terminal=False, expansion_failures=0, sampled_determinizations=1,
            prior=prior,
        )
        for index, (visits, prior) in enumerate(((1, 0.2), (3, 0.8)), start=1)
    )
    trace = SearchTrace(
        version="puct-v1", seed=1, root_player=0, root_turn=1, horizon_turns=0,
        simulations=4, completed_simulations=4, tree_nodes=3, native_steps=2,
        max_depth_reached=1, loop_cutoffs=0, horizon_cutoffs=0, depth_cutoffs=0,
        time_cutoffs=0, hard_deadline_exceeded=False, expansion_failures=0,
        elapsed_ms=1.0, stopped_reason="simulation_limit", fallback_used=False,
        fallback_reason=None, generation_exhaustive=True, total_root_actions=2,
        generated_root_actions=2, root_edges=edges, errors=(),
    )
    return SearchResult((2,), (1,), trace)


class SelfPlayTests(unittest.TestCase):
    def test_phase8_config_loads_strictly(self) -> None:
        root = Path(__file__).resolve().parents[2]
        config = load_reinforcement_config(root / "plan_1" / "configs" / "phase8_reinforcement.json")
        self.assertEqual(config.iterations, 3)
        self.assertEqual(config.validation_games_per_iteration, 2)
        self.assertTrue(config.initial_checkpoint.is_absolute())

    def test_temperature_sampling_is_deterministic_and_early_only(self) -> None:
        result = search_result()
        first = _temperature_action(
            result, turn=1, temperature_turns=8, temperature=1.0, seed=10
        )
        second = _temperature_action(
            result, turn=1, temperature_turns=8, temperature=1.0, seed=10
        )
        self.assertEqual(first, second)
        self.assertIn(first, {(1,), (2,)})
        self.assertIsNone(
            _temperature_action(
                result, turn=9, temperature_turns=8, temperature=1.0, seed=10
            )
        )

    def test_promotion_rule_is_explicit(self) -> None:
        self.assertTrue(
            promotion_decision(6, 4, 0, minimum_win_rate=0.55, safety_passed=True)["promoted"]
        )
        self.assertFalse(
            promotion_decision(5, 5, 0, minimum_win_rate=0.55, safety_passed=True)["promoted"]
        )
        self.assertFalse(
            promotion_decision(7, 3, 0, minimum_win_rate=0.55, safety_passed=False)["promoted"]
        )

    def test_replay_window_never_reads_evaluation_games(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CorpusStore(Path(temporary), "replay", SplitPolicy(100, 0, 0))
            store.commit(fixture_game("train", seed_group="train"))
            store.commit(fixture_game("evaluation", purpose="evaluation", seed=2, seed_group="eval"))
            selection = select_replay_window((store,), split="train", max_games=10)
            self.assertEqual(selection.game_ids, ("train",))
            self.assertNotIn("evaluation", selection.game_ids)


if __name__ == "__main__":
    unittest.main()
