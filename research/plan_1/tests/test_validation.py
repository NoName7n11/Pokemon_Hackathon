from __future__ import annotations

import unittest
from types import SimpleNamespace

import _path  # noqa: F401

from plan1.search.validation import BoundAgent, play_game


class _Api:
    @staticmethod
    def to_observation_class(observation):
        return observation


class _Game:
    def __init__(self) -> None:
        self.finished = False
        self.terminal = SimpleNamespace(
            select=None,
            current=SimpleNamespace(result=0, yourIndex=0),
        )

    def battle_start(self, first, second):
        del first, second
        return (
            SimpleNamespace(
                select=SimpleNamespace(),
                current=SimpleNamespace(result=-1, yourIndex=0),
            ),
            None,
        )

    def battle_select(self, action):
        del action
        return self.terminal

    def battle_finish(self):
        self.finished = True


class ValidationTests(unittest.TestCase):
    def test_terminal_state_on_last_allowed_action_is_not_timeout(self) -> None:
        game = _Game()
        modules = [
            SimpleNamespace(_MY_DECK=[], _live_ability_count={}, _last_seen_turn=-1),
            SimpleNamespace(_MY_DECK=[], _live_ability_count={}, _last_seen_turn=-1),
        ]
        agents = [BoundAgent(lambda observation: [0]), BoundAgent(lambda observation: [0])]
        outcome = play_game(
            game,
            _Api(),
            agents,
            modules,
            ([1] * 60, [1] * 60),
            max_steps=1,
        )
        self.assertEqual(outcome["result"], 0)
        self.assertIsNone(outcome["fault"])
        self.assertTrue(game.finished)


if __name__ == "__main__":
    unittest.main()
