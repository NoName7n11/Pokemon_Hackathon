from __future__ import annotations

import tempfile
import unittest
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import _path  # noqa: F401

from plan1.belief.information_set import information_set_key
from plan1.data.trajectory import (
    ActionTarget,
    DecisionRecord,
    DeckIdentity,
    GameTrajectory,
    PolicyIdentity,
    TrajectoryError,
)
from plan1.game.actions import ActionGenerator
from plan1.game.records import PublicObservationRecord
from plan1.reproducibility import canonical_json_hash

from test_mcts import observation


NOW = datetime.now(timezone.utc).isoformat()


def fixture_game(
    game_id: str = "game-1",
    *,
    purpose: str = "training",
    seed: int = 10,
    seed_group: str = "group-1",
    created_utc: str = NOW,
) -> GameTrajectory:
    record = PublicObservationRecord.from_engine(observation("root", 0, 1, 2))
    generation = ActionGenerator().generate(record.selection, preferred_indices=[0])
    targets = tuple(
        ActionTarget(
            fingerprint=candidate.fingerprint,
            indices=candidate.indices,
            option_mask=candidate.option_mask,
            visits=1 if candidate.indices == (0,) else 0,
            prior=None,
            q_value=None,
        )
        for candidate in generation.candidates
    )
    deck = DeckIdentity("fixture", canonical_json_hash([1] * 60), (1,) * 60)
    policy = PolicyIdentity("fixture-policy", "v1", None)
    payload = record.to_dict()
    decision = DecisionRecord(
        schema_version=1,
        game_id=game_id,
        decision_index=0,
        player=0,
        seat=0,
        seed=seed,
        seed_group=seed_group,
        timestamp_utc=created_utc,
        observation=payload,
        observation_sha256=canonical_json_hash(payload),
        information_set_key=information_set_key(record, 0),
        selection_fingerprint=record.selection.fingerprint,
        legal_actions=targets,
        chosen_action_fingerprint=targets[0].fingerprint,
        chosen_indices=targets[0].indices,
        search={"kind": "fixture", "simulations": 0},
        belief={"version": "none"},
        acting_policy=policy,
        opponent_policy=policy,
        deck_sha256=deck.sha256,
        opponent_deck_sha256=deck.sha256,
        final_result=0,
        value_target=1.0,
        terminal_reason="fixture_terminal",
    )
    result = GameTrajectory(
        schema_version=1,
        game_id=game_id,
        run_id="fixture-run",
        purpose=purpose,
        seed=seed,
        seed_group=seed_group,
        created_utc=created_utc,
        decks=(deck, deck),
        policies=(policy, policy),
        decisions=(decision,),
        final_result=0,
        terminal_reason="fixture_terminal",
        completed=True,
    )
    result.validate()
    return result


class TrajectoryTests(unittest.TestCase):
    def test_dict_round_trip_is_exact(self) -> None:
        game = fixture_game()
        recovered = GameTrajectory.from_dict(game.to_dict())
        self.assertEqual(recovered, game)
        self.assertEqual(recovered.fingerprint, game.fingerprint)

    def test_tampered_observation_is_rejected(self) -> None:
        game = fixture_game()
        decision = game.decisions[0]
        observation_data = dict(decision.observation)
        observation_data["schema_version"] = 99
        tampered = replace(decision, observation=observation_data)
        with self.assertRaises(TrajectoryError):
            replace(game, decisions=(tampered,)).validate()

    def test_action_fingerprint_is_recomputed(self) -> None:
        game = fixture_game()
        action = replace(game.decisions[0].legal_actions[0], fingerprint="0" * 64)
        decision = replace(game.decisions[0], legal_actions=(action, *game.decisions[0].legal_actions[1:]))
        with self.assertRaises(TrajectoryError):
            replace(game, decisions=(decision,)).validate()

    def test_value_target_must_match_acting_seat(self) -> None:
        game = fixture_game()
        decision = replace(game.decisions[0], value_target=-1.0)
        with self.assertRaises(TrajectoryError):
            replace(game, decisions=(decision,)).validate()

    def test_incomplete_game_is_rejected(self) -> None:
        with self.assertRaises(TrajectoryError):
            replace(fixture_game(), completed=False).validate()


if __name__ == "__main__":
    unittest.main()
