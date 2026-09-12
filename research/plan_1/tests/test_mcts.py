from __future__ import annotations

import unittest
from dataclasses import dataclass
from types import SimpleNamespace

import _path  # noqa: F401

from plan1.config import SearchConfig
from plan1.engine.lifecycle import SearchInputs
from plan1.evaluation.handcrafted import TERMINAL_SCORE
from plan1.search.mcts import TimeManager, UCTSearch, search_fingerprint
from plan1.search.validation import TraceCollector
from plan1.game.records import PublicObservationRecord


def search_config(**overrides) -> SearchConfig:
    values = {
        "max_simulations": 32,
        "max_depth": 8,
        "max_nodes": 128,
        "max_candidates": 8,
        "time_budget_ms": 100,
        "exploration_constant": 1.0,
        "horizon_turns": 1,
        "progressive_widening_base": 2.0,
        "progressive_widening_exponent": 0.5,
        "value_scale": 10.0,
        "discount_factor": 1.0,
        "require_full_root_coverage": True,
    }
    values.update(overrides)
    return SearchConfig(**values)


def option(index: int) -> SimpleNamespace:
    return SimpleNamespace(
        type=3,
        number=None,
        area=None,
        index=index,
        playerIndex=0,
        toolIndex=None,
        energyIndex=None,
        count=None,
        inPlayArea=None,
        inPlayIndex=None,
        attackId=None,
        cardId=100 + index,
        serial=100 + index,
        specialConditionType=None,
    )


def player() -> SimpleNamespace:
    return SimpleNamespace(
        active=[], bench=[], benchMax=5, deckCount=20, discard=[], prize=[None] * 6,
        handCount=0, hand=[], poisoned=False, burned=False, asleep=False,
        paralyzed=False, confused=False,
    )


def observation(name: str, actor: int, turn: int, choices: int, *, result: int = -1, value: float = 0.0):
    select = None if result != -1 else SimpleNamespace(
        type=1,
        context=0,
        minCount=1,
        maxCount=1,
        remainDamageCounter=0,
        remainEnergyCost=0,
        option=[option(index) for index in range(choices)],
        deck=None,
        contextCard=None,
        effect=None,
    )
    players = [player(), player()]
    players[0].deckCount = 20 + int(value)
    current = SimpleNamespace(
        turn=turn,
        turnActionCount=0,
        yourIndex=actor,
        firstPlayer=0,
        supporterPlayed=False,
        stadiumPlayed=False,
        energyAttached=False,
        retreated=False,
        result=result,
        stadium=[],
        looking=None,
        players=players,
        name=name,
    )
    return SimpleNamespace(select=select, logs=[], current=current, search_begin_input=True)


@dataclass
class FakeSearchState:
    searchId: int
    observation: SimpleNamespace


@dataclass
class FakeLog:
    type: int
    playerIndex: int


class TreeBackend:
    def __init__(self, root, transitions, *, fail_step: bool = False):
        self.root_observation = root
        self.transitions = transitions
        self.fail_step = fail_step
        self.states: dict[int, FakeSearchState] = {}
        self.next_id = 1
        self.end_calls = 0
        self.release_calls: list[int] = []

    def search_begin(self, *_args, **_kwargs):
        root = FakeSearchState(0, self.root_observation)
        self.states = {0: root}
        return root

    def search_step(self, search_id, select):
        if self.fail_step:
            raise RuntimeError("synthetic step failure")
        source = self.states[search_id].observation.current.name
        target = self.transitions[(source, tuple(select))]
        state = FakeSearchState(self.next_id, target)
        self.states[self.next_id] = state
        self.next_id += 1
        return state

    def search_release(self, search_id):
        self.release_calls.append(search_id)

    def search_end(self):
        self.end_calls += 1


class FakeEvaluator:
    def score(self, record, perspective):
        if record.state.result != -1:
            return TERMINAL_SCORE if record.state.result == perspective else -TERMINAL_SCORE
        value = float(record.state.players[0].deck_count - 20)
        return value if perspective == 0 else -value


class FakeClock:
    def __init__(self, values):
        self.values = iter(values)
        self.last = 0

    def __call__(self):
        try:
            self.last = next(self.values)
        except StopIteration:
            pass
        return self.last


INPUTS = SearchInputs.from_sequences(
    your_deck=[1], your_prize=[1], opponent_deck=[1], opponent_prize=[1], opponent_hand=[1]
)


class MCTSTests(unittest.TestCase):
    def test_forced_action_skips_native_search(self) -> None:
        root = observation("root", 0, 1, 1)
        backend = TreeBackend(root, {})
        result = UCTSearch(backend, FakeEvaluator(), search_config(), cleanup_reserve_ms=10).search(
            root, INPUTS, seed=3
        )
        self.assertEqual(result.action, (0,))
        self.assertEqual(result.trace.stopped_reason, "forced_action")
        self.assertEqual(backend.end_calls, 0)
        collector = TraceCollector()
        collector(result)
        self.assertEqual(collector.summary()["chose_non_fallback"], 0)

    def test_terminal_win_is_selected_and_backed_up(self) -> None:
        root = observation("root", 0, 1, 2)
        win = observation("win", 1, 2, 0, result=0)
        loss = observation("loss", 1, 2, 0, result=1)
        backend = TreeBackend(root, {("root", (0,)): win, ("root", (1,)): loss})
        search = UCTSearch(backend, FakeEvaluator(), search_config(max_simulations=24), cleanup_reserve_ms=10)
        result = search.search(root, INPUTS, seed=9)
        self.assertEqual(result.action, (0,))
        self.assertGreater(result.trace.root_edges[0].mean_value, result.trace.root_edges[1].mean_value)
        self.assertEqual(backend.end_calls, 1)

    def test_trace_collector_compares_choice_with_actual_fallback(self) -> None:
        root = observation("root", 0, 1, 2)
        win = observation("win", 1, 2, 0, result=0)
        loss = observation("loss", 1, 2, 0, result=1)
        backend = TreeBackend(root, {("root", (0,)): win, ("root", (1,)): loss})
        result = UCTSearch(
            backend,
            FakeEvaluator(),
            search_config(max_simulations=24),
            cleanup_reserve_ms=10,
        ).search(root, INPUTS, seed=9, fallback_action=[1])
        collector = TraceCollector()
        collector(result)
        self.assertEqual(result.action, (0,))
        self.assertEqual(result.fallback_action, (1,))
        self.assertEqual(collector.summary()["chose_non_fallback"], 1)

    def test_opponent_node_minimizes_root_value(self) -> None:
        root = observation("root", 0, 1, 2)
        risky = observation("risky", 1, 2, 2)
        safe = observation("safe", 1, 2, 2)
        risky_good = observation("risky_good", 0, 3, 0, result=0)
        risky_bad = observation("risky_bad", 0, 3, 0, result=1)
        safe_a = observation("safe_a", 0, 3, 0, value=1.0)
        safe_b = observation("safe_b", 0, 3, 0, value=1.0)
        transitions = {
            ("root", (0,)): risky,
            ("root", (1,)): safe,
            ("risky", (0,)): risky_good,
            ("risky", (1,)): risky_bad,
            ("safe", (0,)): safe_a,
            ("safe", (1,)): safe_b,
        }
        backend = TreeBackend(root, transitions)
        search = UCTSearch(
            backend,
            FakeEvaluator(),
            search_config(max_simulations=96, progressive_widening_base=4.0),
            cleanup_reserve_ms=10,
            rollout_policy=lambda obs: [0],
        )
        result = search.search(root, INPUTS, seed=7)
        self.assertEqual(result.action, (1,))

    def test_opponent_response_horizon_changes_ko_back_choice(self) -> None:
        root = observation("root", 0, 1, 2)
        flashy = observation("flashy", 1, 2, 1, value=8.0)
        stable = observation("stable", 1, 2, 1, value=2.0)
        ko_back = observation("ko_back", 0, 3, 0, result=1)
        survives = observation("survives", 0, 3, 0, value=2.0)
        transitions = {
            ("root", (0,)): flashy,
            ("root", (1,)): stable,
            ("flashy", (0,)): ko_back,
            ("stable", (0,)): survives,
        }
        stage_a = UCTSearch(
            TreeBackend(root, transitions),
            FakeEvaluator(),
            search_config(horizon_turns=0, max_simulations=48),
            cleanup_reserve_ms=10,
            rollout_policy=lambda obs: [0],
        ).search(root, INPUTS, seed=12)
        stage_b = UCTSearch(
            TreeBackend(root, transitions),
            FakeEvaluator(),
            search_config(horizon_turns=1, max_simulations=48),
            cleanup_reserve_ms=10,
            rollout_policy=lambda obs: [0],
        ).search(root, INPUTS, seed=12)
        self.assertEqual(stage_a.action, (0,))
        self.assertEqual(stage_b.action, (1,))

    def test_search_error_returns_legal_fallback_and_cleans_up(self) -> None:
        root = observation("root", 0, 1, 2)
        backend = TreeBackend(root, {}, fail_step=True)
        result = UCTSearch(backend, FakeEvaluator(), search_config(), cleanup_reserve_ms=10).search(
            root, INPUTS, seed=1
        )
        self.assertEqual(result.action, (0,))
        self.assertTrue(result.trace.fallback_used)
        self.assertEqual(backend.end_calls, 1)

    def test_loop_is_cut_off_without_exhausting_depth(self) -> None:
        root = observation("root", 0, 1, 2)
        loop = observation("loop", 0, 1, 2)
        transitions = {
            ("root", (0,)): loop,
            ("root", (1,)): observation("terminal", 0, 1, 0, result=1),
            ("loop", (0,)): loop,
        }
        result = UCTSearch(
            TreeBackend(root, transitions),
            FakeEvaluator(),
            search_config(max_simulations=8, require_full_root_coverage=False),
            cleanup_reserve_ms=10,
            rollout_policy=lambda obs: [0],
        ).search(root, INPUTS, seed=2)
        self.assertGreater(result.trace.loop_cutoffs, 0)
        self.assertLess(result.trace.max_depth_reached, 8)

    def test_equal_roots_use_stable_fingerprint_tie_break(self) -> None:
        root = observation("root", 0, 1, 2)
        left = observation("left", 0, 2, 0, result=0)
        right = observation("right", 0, 2, 0, result=0)
        transitions = {("root", (0,)): left, ("root", (1,)): right}
        actions = []
        for _ in range(3):
            result = UCTSearch(
                TreeBackend(root, transitions),
                FakeEvaluator(),
                search_config(max_simulations=16),
                cleanup_reserve_ms=10,
            ).search(root, INPUTS, seed=5)
            actions.append(result.action)
        self.assertEqual(actions, [actions[0]] * 3)

    def test_node_limit_is_hard_cap(self) -> None:
        root = observation("root", 0, 1, 2)
        leaves = {
            ("root", (0,)): observation("a", 0, 1, 2, value=1.0),
            ("root", (1,)): observation("b", 0, 1, 2, value=0.0),
            ("a", (0,)): observation("a", 0, 1, 2, value=1.0),
            ("b", (0,)): observation("b", 0, 1, 2, value=0.0),
        }
        backend = TreeBackend(root, leaves)
        result = UCTSearch(
            backend,
            FakeEvaluator(),
            search_config(max_nodes=3, max_simulations=100),
            cleanup_reserve_ms=10,
            rollout_policy=lambda obs: [0],
        ).search(root, INPUTS, seed=4)
        self.assertLessEqual(result.trace.native_steps, 3)
        self.assertIn(result.trace.stopped_reason, ("node_limit", "simulation_limit"))

    def test_incomplete_root_coverage_returns_fallback(self) -> None:
        root = observation("root", 0, 1, 3)
        transitions = {
            ("root", (0,)): observation("a", 0, 1, 0, result=1),
            ("root", (1,)): observation("b", 0, 1, 0, result=0),
            ("root", (2,)): observation("c", 0, 1, 0, result=0),
        }
        result = UCTSearch(
            TreeBackend(root, transitions),
            FakeEvaluator(),
            search_config(max_simulations=1),
            cleanup_reserve_ms=10,
            rollout_policy=lambda obs: [0],
        ).search(root, INPUTS, seed=1)
        self.assertEqual(result.action, (0,))
        self.assertTrue(result.trace.fallback_used)
        self.assertEqual(result.trace.fallback_reason, "incomplete_root_coverage")

    def test_time_manager_reserves_cleanup_window(self) -> None:
        clock = FakeClock([0, 89_000_000, 90_000_000, 100_000_000])
        manager = TimeManager(100, 10, clock=clock)
        self.assertFalse(manager.search_expired())
        self.assertTrue(manager.search_expired())
        self.assertTrue(manager.hard_expired())

    def test_search_fingerprint_ignores_logs_and_action_count(self) -> None:
        first = observation("same", 0, 1, 2)
        second = observation("same", 0, 1, 2)
        first.logs = [FakeLog(type=2, playerIndex=0)]
        second.logs = [FakeLog(type=3, playerIndex=0)]
        second.current.turnActionCount = 9
        self.assertEqual(
            search_fingerprint(PublicObservationRecord.from_engine(first)),
            search_fingerprint(PublicObservationRecord.from_engine(second)),
        )


if __name__ == "__main__":
    unittest.main()
