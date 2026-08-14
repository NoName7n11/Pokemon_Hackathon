from __future__ import annotations

import importlib
import importlib.util
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from plan1.belief.information_set import information_set_key
from plan1.data.replay_buffer import CorpusStore
from plan1.data.trajectory import (
    ActionTarget,
    DecisionRecord,
    DeckIdentity,
    GameTrajectory,
    PolicyIdentity,
)
from plan1.engine.api_loader import load_competition_api
from plan1.game.actions import ActionGenerator
from plan1.game.records import PublicObservationRecord
from plan1.paths import ENGINE_PARENT
from plan1.reproducibility import canonical_json_hash, derive_seed, sha256_file


@dataclass(frozen=True, slots=True)
class GenerationSummary:
    requested_games: int
    existing_games: int
    generated_games: int
    completed_games: int
    decisions: int
    errors: tuple[str, ...]
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class _PendingDecision:
    decision_index: int
    player: int
    timestamp_utc: str
    observation: dict[str, Any]
    observation_sha256: str
    information_set_key: str
    selection_fingerprint: str
    legal_actions: tuple[ActionTarget, ...]
    chosen_action_fingerprint: str
    chosen_indices: tuple[int, ...]
    search: dict[str, Any]
    belief: dict[str, Any]


def deck_identity(name: str, cards: Sequence[int]) -> DeckIdentity:
    identity = DeckIdentity(name=name, sha256=canonical_json_hash(list(cards)), card_ids=tuple(cards))
    identity.validate()
    return identity


def _load_game() -> Any:
    load_competition_api()
    engine_path = str(ENGINE_PARENT.resolve())
    if engine_path not in sys.path:
        sys.path.insert(0, engine_path)
    return importlib.import_module("cg.game")


def _load_policy(name: str, deck: Sequence[int]) -> Any:
    path = ENGINE_PARENT / "main.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load policy module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._MY_DECK = list(deck)
    module._live_ability_count = {}
    module._last_seen_turn = -1
    return module


class HeuristicCorpusGenerator:
    def __init__(
        self,
        store: CorpusStore,
        decks: Sequence[DeckIdentity],
        *,
        run_id: str,
        root_seed: int,
        purpose: str = "training",
        max_candidates: int = 64,
        max_steps: int = 3000,
    ) -> None:
        if len(decks) < 1 or not run_id or root_seed < 0 or max_candidates < 1 or max_steps < 1:
            raise ValueError("invalid corpus generation configuration")
        if purpose not in {"training", "evaluation"}:
            raise ValueError("purpose must be training or evaluation")
        self.store = store
        self.decks = tuple(decks)
        self.run_id = run_id
        self.root_seed = root_seed
        self.purpose = purpose
        self.max_steps = max_steps
        self.generator = ActionGenerator(max_candidates=max_candidates)
        self.api = load_competition_api()
        self.game = _load_game()
        policy_hash = sha256_file(ENGINE_PARENT / "main.py")
        self.policy_identity = PolicyIdentity("shipped_heuristic", "phase6-bootstrap", policy_hash)

    def generate(self, target_games: int) -> GenerationSummary:
        if target_games < 1:
            raise ValueError("target_games must be positive")
        started = time.perf_counter()
        manifest = self.store.load_manifest()
        existing_ids = {entry.game_id for entry in manifest.entries}
        existing = sum(f"{self.run_id}-g{index:06d}" in existing_ids for index in range(target_games))
        generated = completed = decisions = 0
        errors: list[str] = []
        for game_index in range(target_games):
            game_id = f"{self.run_id}-g{game_index:06d}"
            if game_id in existing_ids:
                continue
            try:
                trajectory = self._play(game_index, game_id)
                self.store.commit(trajectory)
                generated += 1
                completed += 1
                decisions += len(trajectory.decisions)
            except Exception as exc:
                errors.append(f"{game_id}:{type(exc).__name__}:{exc}")
        return GenerationSummary(
            requested_games=target_games, existing_games=existing, generated_games=generated,
            completed_games=completed, decisions=decisions, errors=tuple(errors),
            elapsed_seconds=time.perf_counter() - started,
        )

    def _play(self, game_index: int, game_id: str) -> GameTrajectory:
        seed = derive_seed(self.root_seed, self.run_id, game_index)
        seed_group = f"{self.run_id}-seed-{game_index:06d}"
        first_index = game_index % len(self.decks)
        second_index = (game_index // len(self.decks) + 1) % len(self.decks)
        if len(self.decks) > 1 and second_index == first_index:
            second_index = (second_index + 1) % len(self.decks)
        pair = (self.decks[first_index], self.decks[second_index])
        policies = (
            _load_policy(f"plan1_data_{game_index}_0", pair[0].card_ids),
            _load_policy(f"plan1_data_{game_index}_1", pair[1].card_ids),
        )
        observation_dict, start_data = self.game.battle_start(list(pair[0].card_ids), list(pair[1].card_ids))
        if observation_dict is None:
            raise RuntimeError(f"battle_start failed: {start_data}")
        pending: list[_PendingDecision] = []
        try:
            for _ in range(self.max_steps):
                observation = self.api.to_observation_class(observation_dict)
                state = observation.current
                if state is not None and state.result != -1:
                    return self._finalize(game_id, seed, seed_group, pair, pending, int(state.result), "engine_terminal")
                if observation.select is None:
                    action = list(pair[0].card_ids)
                else:
                    actor = int(state.yourIndex) if state is not None else 0
                    module = policies[actor]
                    module._MY_DECK = list(pair[actor].card_ids)
                    action = list(module.agent(observation_dict))
                    pending.append(self._capture(game_id, seed, seed_group, actor, observation, action, len(pending)))
                observation_dict = self.game.battle_select(action)
            final = self.api.to_observation_class(observation_dict)
            if final.current is not None and final.current.result != -1:
                return self._finalize(
                    game_id, seed, seed_group, pair, pending, int(final.current.result), "engine_terminal"
                )
            raise RuntimeError(f"game exceeded {self.max_steps} decisions")
        finally:
            self.game.battle_finish()

    def _capture(
        self,
        game_id: str,
        seed: int,
        seed_group: str,
        actor: int,
        observation: Any,
        action: Sequence[int],
        decision_index: int,
    ) -> _PendingDecision:
        record = PublicObservationRecord.from_engine(observation)
        if record.selection is None:
            raise RuntimeError("cannot capture a decision without selection")
        generation = self.generator.generate(
            record.selection,
            preferred_indices=action,
            seed=seed + decision_index,
        )
        visits = [0] * len(generation.candidates)
        chosen_index = next(
            (index for index, candidate in enumerate(generation.candidates) if candidate.indices == tuple(action)),
            None,
        )
        if chosen_index is None:
            raise RuntimeError("chosen heuristic action was not retained by candidate generation")
        visits[chosen_index] = 1
        targets = tuple(
            ActionTarget(
                fingerprint=candidate.fingerprint, indices=candidate.indices,
                option_mask=candidate.option_mask, visits=visits[index], prior=None, q_value=None,
            )
            for index, candidate in enumerate(generation.candidates)
        )
        payload = record.to_dict()
        return _PendingDecision(
            decision_index=decision_index, player=actor, timestamp_utc=datetime.now(timezone.utc).isoformat(),
            observation=payload, observation_sha256=canonical_json_hash(payload),
            information_set_key=information_set_key(record, actor), selection_fingerprint=record.selection.fingerprint,
            legal_actions=targets, chosen_action_fingerprint=targets[chosen_index].fingerprint,
            chosen_indices=tuple(action),
            search={
                "kind": "heuristic_bootstrap", "version": "phase6-v1", "simulations": 0,
                "nodes": 0, "max_depth": 0, "elapsed_ms": 0.0,
                "candidate_exhaustive": generation.exhaustive,
                "candidate_count": len(generation.candidates), "total_action_count": generation.total_action_count,
                "issues": list(generation.issues),
            },
            belief={"version": "none-heuristic-bootstrap", "determinizations": 0, "hidden_policy_fields": False},
        )

    def _finalize(
        self,
        game_id: str,
        seed: int,
        seed_group: str,
        decks: tuple[DeckIdentity, DeckIdentity],
        pending: Sequence[_PendingDecision],
        result: int,
        terminal_reason: str,
    ) -> GameTrajectory:
        if not pending:
            raise RuntimeError("terminal game contained no policy decisions")
        policies = (self.policy_identity, self.policy_identity)
        decisions = tuple(
            DecisionRecord(
                schema_version=1, game_id=game_id, decision_index=item.decision_index,
                player=item.player, seat=item.player, seed=seed, seed_group=seed_group,
                timestamp_utc=item.timestamp_utc, observation=item.observation,
                observation_sha256=item.observation_sha256, information_set_key=item.information_set_key,
                selection_fingerprint=item.selection_fingerprint, legal_actions=item.legal_actions,
                chosen_action_fingerprint=item.chosen_action_fingerprint, chosen_indices=item.chosen_indices,
                search=item.search, belief=item.belief, acting_policy=policies[item.player],
                opponent_policy=policies[1 - item.player], deck_sha256=decks[item.player].sha256,
                opponent_deck_sha256=decks[1 - item.player].sha256, final_result=result,
                value_target=0.0 if result == 2 else (1.0 if result == item.player else -1.0),
                terminal_reason=terminal_reason,
            )
            for item in pending
        )
        trajectory = GameTrajectory(
            schema_version=1, game_id=game_id, run_id=self.run_id, purpose=self.purpose,
            seed=seed, seed_group=seed_group, created_utc=datetime.now(timezone.utc).isoformat(),
            decks=decks, policies=policies, decisions=decisions, final_result=result,
            terminal_reason=terminal_reason, completed=True,
        )
        trajectory.validate()
        return trajectory
