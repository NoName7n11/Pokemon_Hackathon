from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import _path  # noqa: F401

from plan1.game.records import PublicObservationRecord


class ObservationWithoutSearchAccess:
    select = None
    logs = []
    current = None

    @property
    def search_begin_input(self):
        raise AssertionError("search_begin_input must not be read by public records")


class RecordTests(unittest.TestCase):
    def test_converter_does_not_read_opaque_search_input(self) -> None:
        record = PublicObservationRecord.from_engine(ObservationWithoutSearchAccess())
        self.assertIsNone(record.selection)
        self.assertNotIn("search_begin", str(record.to_dict()))

    def test_records_are_immutable(self) -> None:
        record = PublicObservationRecord.from_engine(ObservationWithoutSearchAccess())
        with self.assertRaises(FrozenInstanceError):
            record.schema_version = 2

    def test_opponent_hidden_hand_stays_hidden(self) -> None:
        player = SimpleNamespace(
            active=[], bench=[], benchMax=5, deckCount=40, discard=[], prize=[None] * 6,
            handCount=7, hand=None, poisoned=False, burned=False, asleep=False,
            paralyzed=False, confused=False,
        )
        state = SimpleNamespace(
            turn=1, turnActionCount=0, yourIndex=0, firstPlayer=0,
            supporterPlayed=False, stadiumPlayed=False, energyAttached=False,
            retreated=False, result=-1, stadium=[], looking=None, players=[player, player],
        )
        observation = SimpleNamespace(select=None, logs=[], current=state)
        record = PublicObservationRecord.from_engine(observation)
        self.assertIsNone(record.state.players[1].hand)
        self.assertEqual(record.state.players[1].hand_count, 7)


if __name__ == "__main__":
    unittest.main()
