from __future__ import annotations

import unittest
from types import SimpleNamespace

import _path  # noqa: F401

from plan1.belief.sampler import BeliefSample
from plan1.engine.lifecycle import SearchInputs
from plan1.search.ismcts import RootSampledISMCTS

from test_mcts import observation


class SequentialSampler:
    def __init__(self) -> None:
        self.calls = 0

    def sample(self, record, rng):
        del record, rng
        self.calls += 1
        inputs = SearchInputs.from_sequences(
            your_deck=[self.calls],
            your_prize=[1],
            opponent_deck=[1],
            opponent_prize=[1],
            opponent_hand=[1],
        )
        return BeliefSample(inputs, "test", f"world-{self.calls}", False, 2, self.calls % 2)


class FakeSearcher:
    def __init__(self) -> None:
        self.calls = 0

    @staticmethod
    def _fallback(observation):
        del observation
        return (1,)

    def search(self, observation, inputs, *, seed, fallback_action):
        del observation, inputs, seed, fallback_action
        self.calls += 1
        if self.calls == 1:
            edges = (
                SimpleNamespace(action=(0,), fingerprint="a", visits=3, value_sum=1.5),
                SimpleNamespace(action=(1,), fingerprint="b", visits=1, value_sum=0.2),
            )
        else:
            edges = (
                SimpleNamespace(action=(0,), fingerprint="a", visits=2, value_sum=0.8),
                SimpleNamespace(action=(1,), fingerprint="b", visits=4, value_sum=1.2),
            )
        return SimpleNamespace(trace=SimpleNamespace(root_edges=edges, fallback_used=False))


class ISMCTSTests(unittest.TestCase):
    def test_root_statistics_merge_across_determinizations(self) -> None:
        result = RootSampledISMCTS(FakeSearcher(), SequentialSampler(), determinizations=2).search(
            observation("root", 0, 1, 2), seed=9, fallback_action=[1]
        )
        self.assertEqual(result.action, (0,))
        self.assertEqual(result.trace.completed_determinizations, 2)
        self.assertEqual(result.trace.sampled_determinizations, 2)
        self.assertEqual(result.trace.unique_determinizations, 2)
        edges = {edge.fingerprint: edge for edge in result.trace.edges}
        self.assertEqual(edges["a"].visits, 5)
        self.assertEqual(edges["a"].determinizations, 2)
        self.assertEqual(edges["b"].visits, 5)

    def test_all_sampling_failures_return_fallback(self) -> None:
        class BrokenSampler:
            def sample(self, record, rng):
                raise ValueError("broken belief")

        result = RootSampledISMCTS(FakeSearcher(), BrokenSampler(), determinizations=3).search(
            observation("root", 0, 1, 2), seed=1, fallback_action=[1]
        )
        self.assertEqual(result.action, (1,))
        self.assertTrue(result.trace.fallback_used)
        self.assertEqual(result.trace.completed_determinizations, 0)
        self.assertEqual(len(result.trace.errors), 3)

    def test_duplicate_determinizations_are_reported(self) -> None:
        class DuplicateSampler(SequentialSampler):
            def sample(self, record, rng):
                sample = super().sample(record, rng)
                return BeliefSample(
                    sample.inputs, sample.mode, "same-world", False, 1, 0
                )

        result = RootSampledISMCTS(FakeSearcher(), DuplicateSampler(), determinizations=2).search(
            observation("root", 0, 1, 2), seed=2, fallback_action=[1]
        )
        self.assertEqual(result.trace.sampled_determinizations, 2)
        self.assertEqual(result.trace.unique_determinizations, 1)
        self.assertEqual(result.trace.duplicate_determinizations, 1)


if __name__ == "__main__":
    unittest.main()
