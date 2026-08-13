from __future__ import annotations

import unittest
from dataclasses import dataclass
from enum import IntEnum
from types import SimpleNamespace

import _path  # noqa: F401

from plan1.engine.conformance import (
    ConformanceResult,
    conformance_passes,
    conformance_action,
    legal_probe_selection,
    observation_fingerprint,
    stochastic_boundary_reason,
)


class FakeOptionType(IntEnum):
    PLAY = 7
    ATTACH = 8
    EVOLVE = 9
    ABILITY = 10
    DISCARD = 11
    RETREAT = 12
    ATTACK = 13
    END = 14


class FakeSelectType(IntEnum):
    MAIN = 0
    CARD = 1


class FakeLogType(IntEnum):
    SHUFFLE = 0
    DRAW = 4
    DRAW_REVERSE = 5
    COIN = 22


@dataclass
class FakeOption:
    type: FakeOptionType


@dataclass
class FakeSelect:
    type: FakeSelectType
    minCount: int
    maxCount: int
    option: list[FakeOption]


class ConformanceHelpersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = SimpleNamespace(OptionType=FakeOptionType, SelectType=FakeSelectType, LogType=FakeLogType)

    def test_main_action_prefers_attachment_before_attack_and_end(self) -> None:
        select = FakeSelect(
            FakeSelectType.MAIN,
            1,
            1,
            [FakeOption(FakeOptionType.END), FakeOption(FakeOptionType.ATTACK), FakeOption(FakeOptionType.ATTACH)],
        )
        observation = SimpleNamespace(select=select)
        self.assertEqual(conformance_action(observation, self.api), [2])

    def test_optional_empty_selection_is_legal_when_no_options_exist(self) -> None:
        select = FakeSelect(FakeSelectType.CARD, 0, 0, [])
        self.assertEqual(legal_probe_selection(select), [])

    def test_fingerprint_ignores_incremental_logs(self) -> None:
        first = SimpleNamespace(current={"turn": 1}, select={"type": 0}, logs=["a"])
        second = SimpleNamespace(current={"turn": 1}, select={"type": 0}, logs=["b"])
        self.assertEqual(observation_fingerprint(first), observation_fingerprint(second))

    def test_fingerprint_changes_with_state(self) -> None:
        first = SimpleNamespace(current={"turn": 1}, select={"type": 0}, logs=[])
        second = SimpleNamespace(current={"turn": 2}, select={"type": 0}, logs=[])
        self.assertNotEqual(observation_fingerprint(first), observation_fingerprint(second))

    def test_randomized_deck_selection_is_a_replay_boundary(self) -> None:
        select = SimpleNamespace(deck=[SimpleNamespace(id=1)])
        observation = SimpleNamespace(select=select, logs=[])
        self.assertEqual(stochastic_boundary_reason(observation, self.api), "randomized_deck_selection")

    def test_hidden_draw_is_a_replay_boundary(self) -> None:
        select = SimpleNamespace(deck=None)
        observation = SimpleNamespace(select=select, logs=[SimpleNamespace(type=FakeLogType.DRAW)])
        self.assertEqual(stochastic_boundary_reason(observation, self.api), "hidden_draw")

    def test_conformance_gate_rejects_nonterminal_replay(self) -> None:
        values = {
            "branch_parent_reusable": True,
            "child_survives_parent_release": True,
            "sibling_survives_leaf_release": True,
            "descendant_survives_ancestor_release": True,
            "released_state_rejected": True,
            "double_release_idempotent": True,
            "crossed_turn_boundary": True,
            "max_path_steps": 1,
            "replay_exact": True,
            "replay_terminal": False,
            "replay_second_terminal": True,
            "replay_steps": 1,
            "replay_mismatch_step": None,
            "replay_stochastic_boundary_step": None,
            "replay_stochastic_boundary_reason": None,
            "replay_coin_events": 0,
            "session_iterations": 1,
            "root_ids_reused_across_sessions": False,
            "begin_ms_median": 0.1,
            "step_ms_median": 0.1,
            "rss_before_bytes": 1,
            "rss_after_bytes": 1,
            "rss_delta_bytes": 0,
            "rss_peak_bytes": 1,
            "rss_tail_growth_bytes": 0,
            "errors": [],
        }
        self.assertFalse(conformance_passes(ConformanceResult(**values)))


if __name__ == "__main__":
    unittest.main()
