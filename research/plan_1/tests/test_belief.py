from __future__ import annotations

import json
import random
import unittest
from dataclasses import replace

import _path  # noqa: F401

from plan1.belief.card_accounting import AccountingError, account_public_cards
from plan1.belief.information_set import information_set_key
from plan1.belief.priors import DeckMixturePrior
from plan1.belief.sampler import BeliefSampler, oracle_inputs_from_visualizer
from plan1.game.records import CardRecord, PlayerRecord, PokemonRecord, PublicObservationRecord, StateRecord


def card(card_id: int, serial: int, player: int) -> CardRecord:
    return CardRecord(card_id=card_id, serial=serial, player_index=player)


def pokemon(card_id: int, serial: int) -> PokemonRecord:
    return PokemonRecord(
        card_id=card_id,
        serial=serial,
        hp=100,
        max_hp=100,
        appear_this_turn=False,
        energies=(),
        energy_cards=(),
        tools=(),
        pre_evolution=(),
    )


def fixture_record() -> PublicObservationRecord:
    own = PlayerRecord(
        active=(pokemon(1, 1),),
        bench=(),
        bench_max=5,
        deck_count=45,
        discard=(card(1, 2, 0), card(1, 3, 0), card(1, 4, 0)),
        prize=(None,) * 6,
        hand_count=5,
        hand=tuple(card(1, 10 + index, 0) for index in range(5)),
        poisoned=False,
        burned=False,
        asleep=False,
        paralyzed=False,
        confused=False,
    )
    opponent = PlayerRecord(
        active=(pokemon(2, 20),),
        bench=(),
        bench_max=5,
        deck_count=45,
        discard=(card(2, 21, 1), card(2, 22, 1), card(2, 23, 1)),
        prize=(None,) * 6,
        hand_count=5,
        hand=None,
        poisoned=False,
        burned=False,
        asleep=False,
        paralyzed=False,
        confused=False,
    )
    state = StateRecord(
        turn=3,
        turn_action_count=4,
        acting_player=0,
        first_player=0,
        supporter_played=False,
        stadium_played=False,
        energy_attached=False,
        retreated=False,
        result=-1,
        stadium=(),
        looking=None,
        players=(own, opponent),
    )
    return PublicObservationRecord(schema_version=1, selection=None, logs=(), state=state)


class BeliefTests(unittest.TestCase):
    def test_public_accounting_counts_visible_and_hidden_zones(self) -> None:
        accounting = account_public_cards(fixture_record())
        self.assertEqual(accounting.visible_counter(0), {1: 9})
        self.assertEqual(accounting.visible_counter(1), {2: 4})
        self.assertEqual(accounting.hidden_counts, ((45, 6, 0), (45, 6, 5)))

    def test_constrained_sampler_conserves_declared_decks(self) -> None:
        prior = DeckMixturePrior(([2] * 60, [3] * 60))
        sampler = BeliefSampler([1] * 60, prior)
        sample = sampler.sample(fixture_record(), random.Random(17))
        self.assertEqual(len(sample.inputs.your_deck), 45)
        self.assertEqual(len(sample.inputs.your_prize), 6)
        self.assertEqual(len(sample.inputs.opponent_deck), 45)
        self.assertEqual(len(sample.inputs.opponent_prize), 6)
        self.assertEqual(len(sample.inputs.opponent_hand), 5)
        self.assertEqual(set(sample.inputs.opponent_deck), {2})
        self.assertEqual(sample.compatible_components, 1)
        self.assertFalse(sample.fallback_used)

    def test_sampler_is_reproducible_and_diverse_across_seeds(self) -> None:
        mixed = [2] * 30 + [4] * 30
        sampler = BeliefSampler([1] * 60, DeckMixturePrior((mixed,)))
        first = sampler.sample(fixture_record(), random.Random(2))
        repeated = sampler.sample(fixture_record(), random.Random(2))
        other = sampler.sample(fixture_record(), random.Random(3))
        self.assertEqual(first, repeated)
        self.assertNotEqual(first.fingerprint, other.fingerprint)

    def test_revealed_prizes_keep_position_and_full_zone_length(self) -> None:
        record = fixture_record()
        own = replace(record.state.players[0], prize=(None, card(1, 70, 0), None))
        opponent = replace(record.state.players[1], prize=(card(2, 71, 1), None, None))
        record = replace(record, state=replace(record.state, players=(own, opponent)))
        sample = BeliefSampler([1] * 60, DeckMixturePrior(([2] * 60,))).sample(
            record, random.Random(8)
        )
        self.assertEqual(len(sample.inputs.your_prize), 3)
        self.assertEqual(len(sample.inputs.opponent_prize), 3)
        self.assertEqual(sample.inputs.your_prize[1], 1)
        self.assertEqual(sample.inputs.opponent_prize[0], 2)

    def test_impossible_visible_cards_use_reported_generic_fallback(self) -> None:
        prior = DeckMixturePrior(([3] * 60,), generic_pool=[2, 3])
        sample = BeliefSampler([1] * 60, prior).sample(fixture_record(), random.Random(4))
        self.assertTrue(sample.fallback_used)
        self.assertEqual(sample.compatible_components, 0)
        self.assertEqual(
            len(sample.inputs.opponent_deck)
            + len(sample.inputs.opponent_prize)
            + len(sample.inputs.opponent_hand),
            56,
        )

    def test_public_overcount_is_rejected(self) -> None:
        with self.assertRaises(AccountingError):
            BeliefSampler([9] * 60, DeckMixturePrior(([2] * 60,))).sample(
                fixture_record(), random.Random(1)
            )

    def test_information_set_key_ignores_opponent_hidden_hand_identity(self) -> None:
        first = fixture_record()
        opponent = replace(first.state.players[1], hand=(card(20, 50, 1),) * 5)
        second = replace(first, state=replace(first.state, players=(first.state.players[0], opponent)))
        self.assertEqual(information_set_key(first, 0), information_set_key(second, 0))

    def test_information_set_key_preserves_root_visible_hand(self) -> None:
        first = fixture_record()
        own = replace(first.state.players[0], hand=(card(9, 60, 0),) * 5)
        second = replace(first, state=replace(first.state, players=(own, first.state.players[1])))
        self.assertNotEqual(information_set_key(first, 0), information_set_key(second, 0))

    def test_information_set_key_ignores_native_serial_allocation(self) -> None:
        first = fixture_record()
        own = replace(first.state.players[0], active=(pokemon(1, 999),))
        second = replace(first, state=replace(first.state, players=(own, first.state.players[1])))
        self.assertEqual(information_set_key(first, 0), information_set_key(second, 0))

    def test_oracle_extractor_is_explicit_offline_input(self) -> None:
        frame = {
            "current": {
                "players": [
                    {"deck": [{"id": 1}], "prize": [{"id": 2}], "hand": [{"id": 3}], "active": []},
                    {
                        "deck": [{"id": 4}],
                        "prize": [{"id": 5}],
                        "hand": [{"id": 6}],
                        "active": [{"id": 7}],
                    },
                ]
            }
        }
        inputs = oracle_inputs_from_visualizer(json.dumps([frame]), 0)
        self.assertEqual(inputs.your_deck, (1,))
        self.assertEqual(inputs.your_prize, (2,))
        self.assertEqual(inputs.opponent_deck, (4,))
        self.assertEqual(inputs.opponent_prize, (5,))
        self.assertEqual(inputs.opponent_hand, (6,))
        self.assertEqual(inputs.opponent_active, (7,))


if __name__ == "__main__":
    unittest.main()
