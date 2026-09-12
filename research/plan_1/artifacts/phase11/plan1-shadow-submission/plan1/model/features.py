from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Iterable

from plan1.game.actions import ActionCandidate
from plan1.game.records import OptionRecord, PublicObservationRecord


SparseVector = tuple[tuple[int, float], ...]


def _bounded(value: float, scale: float) -> float:
    return max(-1.0, min(1.0, value / scale))


@dataclass(frozen=True, slots=True)
class FeatureEncoder:
    """Deterministic feature hashing for public states and legal actions."""

    dimension: int = 8192

    def __post_init__(self) -> None:
        if self.dimension < 128 or self.dimension & (self.dimension - 1):
            raise ValueError("feature dimension must be a power of two >= 128")

    def _index(self, name: str) -> tuple[int, float]:
        digest = hashlib.sha256(name.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") & (self.dimension - 1)
        sign = 1.0 if digest[8] & 1 else -1.0
        return index, sign

    def _vector(self, features: Iterable[tuple[str, float]]) -> SparseVector:
        merged: dict[int, float] = {}
        for name, value in features:
            if not value or not math.isfinite(value):
                continue
            index, sign = self._index(name)
            merged[index] = merged.get(index, 0.0) + sign * float(value)
        return tuple(sorted((index, value) for index, value in merged.items() if value))

    def observation(self, record: PublicObservationRecord, perspective: int) -> SparseVector:
        if perspective not in (0, 1):
            raise ValueError("perspective must be seat 0 or 1")
        features: list[tuple[str, float]] = [("state:bias", 1.0)]
        state = record.state
        selection = record.selection
        if state is None:
            features.append(("state:missing", 1.0))
        else:
            features.extend(
                (
                    ("state:turn", _bounded(state.turn, 100.0)),
                    ("state:actions", _bounded(state.turn_action_count, 20.0)),
                    ("state:first", 1.0 if state.first_player == perspective else -1.0),
                    ("state:actor", 1.0 if state.acting_player == perspective else -1.0),
                    ("state:supporter", float(state.supporter_played)),
                    ("state:stadium-played", float(state.stadium_played)),
                    ("state:energy-attached", float(state.energy_attached)),
                    ("state:retreated", float(state.retreated)),
                )
            )
            for relative, seat in (("self", perspective), ("opp", 1 - perspective)):
                player = state.players[seat]
                prizes = sum(card is not None for card in player.prize)
                features.extend(
                    (
                        (f"{relative}:deck", _bounded(player.deck_count, 60.0)),
                        (f"{relative}:hand", _bounded(player.hand_count, 20.0)),
                        (f"{relative}:prizes", _bounded(prizes, 6.0)),
                        (f"{relative}:bench", _bounded(len(player.bench), max(1, player.bench_max))),
                        (f"{relative}:discard", _bounded(len(player.discard), 30.0)),
                    )
                )
                for status in ("poisoned", "burned", "asleep", "paralyzed", "confused"):
                    features.append((f"{relative}:status:{status}", float(getattr(player, status))))
                pokemon = [item for item in player.active if item is not None]
                pokemon.extend(player.bench)
                for slot, item in enumerate(pokemon[:8]):
                    area = "active" if slot < len([v for v in player.active if v is not None]) else "bench"
                    prefix = f"{relative}:{area}:{slot}"
                    features.extend(
                        (
                            (f"{prefix}:card:{item.card_id}", 1.0),
                            (f"{prefix}:hp", _bounded(item.hp, 400.0)),
                            (f"{prefix}:hp-ratio", item.hp / max(1, item.max_hp)),
                            (f"{prefix}:damage", _bounded(item.max_hp - item.hp, 400.0)),
                            (f"{prefix}:energy", _bounded(len(item.energy_cards), 8.0)),
                            (f"{prefix}:tools", _bounded(len(item.tools), 3.0)),
                            (f"{prefix}:evolution", _bounded(len(item.pre_evolution), 3.0)),
                            (f"{relative}:card:{item.card_id}", 1.0),
                        )
                    )
                if player.hand is not None:
                    for card in player.hand:
                        features.append((f"{relative}:hand-card:{card.card_id}", 1.0))
                for card in player.discard:
                    features.append((f"{relative}:discard-card:{card.card_id}", 0.25))
            for card in state.stadium:
                features.append((f"state:stadium:{card.card_id}", 1.0))
        if selection is None:
            features.append(("selection:missing", 1.0))
        else:
            context = f"selection:{selection.select_type}:{selection.context}"
            features.extend(
                (
                    (context, 1.0),
                    ("selection:options", _bounded(len(selection.options), 20.0)),
                    ("selection:min", _bounded(selection.min_count, 6.0)),
                    ("selection:max", _bounded(selection.max_count, 6.0)),
                    ("selection:damage", _bounded(selection.remain_damage_counter, 40.0)),
                    ("selection:energy", _bounded(selection.remain_energy_cost, 8.0)),
                )
            )
            if selection.context_card is not None:
                features.append((f"selection:context-card:{selection.context_card.card_id}", 1.0))
            if selection.effect is not None:
                features.append((f"selection:effect:{selection.effect.card_id}", 1.0))
        return self._vector(features)

    def action(
        self,
        record: PublicObservationRecord,
        action: ActionCandidate,
        perspective: int,
    ) -> SparseVector:
        selection = record.selection
        if selection is None:
            raise ValueError("action features require a selection")
        context = f"{selection.select_type}:{selection.context}"
        features: list[tuple[str, float]] = [
            ("action:bias", 1.0),
            (f"action:context:{context}", 1.0),
            ("action:count", _bounded(len(action.indices), 6.0)),
            (f"action:context:{context}:count:{len(action.indices)}", 1.0),
        ]
        if not action.indices:
            features.append((f"action:context:{context}:empty", 1.0))
        for rank, index in enumerate(action.indices):
            option = selection.options[index]
            for name, value in self._option_features(option, index, rank, perspective):
                features.append((f"action:{name}", value))
                features.append((f"action:context:{context}:{name}", value))
        return self._vector(features)

    def value_observation(self, record: PublicObservationRecord, perspective: int) -> SparseVector:
        """Low-variance strategic features for outcome prediction."""
        if perspective not in (0, 1):
            raise ValueError("perspective must be seat 0 or 1")
        state = record.state
        if state is None:
            return self._vector((("value:bias", 1.0), ("value:state-missing", 1.0)))
        features: list[tuple[str, float]] = [
            ("value:bias", 1.0),
            ("value:turn", _bounded(state.turn, 100.0)),
            ("value:turn-squared", _bounded(state.turn, 100.0) ** 2),
            ("value:first", 1.0 if state.first_player == perspective else -1.0),
            ("value:actions", _bounded(state.turn_action_count, 20.0)),
        ]
        summaries: dict[str, dict[str, float]] = {}
        for relative, seat in (("self", perspective), ("opp", 1 - perspective)):
            player = state.players[seat]
            active = next((item for item in player.active if item is not None), None)
            board = ([active] if active is not None else []) + list(player.bench)
            total_hp = sum(item.hp for item in board)
            total_max_hp = sum(item.max_hp for item in board)
            total_energy = sum(len(item.energy_cards) for item in board)
            prizes = sum(card is not None for card in player.prize)
            summary = {
                "prizes": prizes / 6.0,
                "deck": player.deck_count / 60.0,
                "hand": min(player.hand_count, 20) / 20.0,
                "bench": len(player.bench) / max(1, player.bench_max),
                "board": len(board) / 6.0,
                "hp": total_hp / max(1, total_max_hp),
                "energy": min(total_energy, 18) / 18.0,
                "active-hp": active.hp / max(1, active.max_hp) if active is not None else 0.0,
                "active-energy": min(len(active.energy_cards), 6) / 6.0 if active is not None else 0.0,
                "discard": min(len(player.discard), 30) / 30.0,
                "status": float(
                    player.poisoned or player.burned or player.asleep
                    or player.paralyzed or player.confused
                ),
            }
            summaries[relative] = summary
            features.extend((f"value:{relative}:{name}", value) for name, value in summary.items())
        for name in summaries["self"]:
            difference = summaries["self"][name] - summaries["opp"][name]
            features.append((f"value:diff:{name}", difference))
            features.append((f"value:turn-x-diff:{name}", difference * _bounded(state.turn, 100.0)))
        selection = record.selection
        if selection is not None:
            features.append((f"value:selection:{selection.select_type}:{selection.context}", 0.25))
        return self._vector(features)

    @staticmethod
    def _option_features(
        option: OptionRecord,
        index: int,
        rank: int,
        perspective: int,
    ) -> list[tuple[str, float]]:
        values: list[tuple[str, float]] = [
            (f"option-type:{option.option_type}", 1.0),
            (f"index:{index}", 1.0),
            (f"rank:{rank}", 1.0),
        ]
        categorical = (
            ("area", option.area),
            ("in-play-area", option.in_play_area),
            ("card", option.card_id),
            ("attack", option.attack_id),
            ("special", option.special_condition_type),
        )
        for name, value in categorical:
            if value is not None:
                values.append((f"{name}:{value}", 1.0))
        if option.player_index is not None:
            relative = "self" if option.player_index == perspective else "opp"
            values.append((f"player:{relative}", 1.0))
        numeric = (
            ("number", option.number, 300.0),
            ("count", option.count, 10.0),
            ("in-play-index", option.in_play_index, 8.0),
            ("tool-index", option.tool_index, 4.0),
            ("energy-index", option.energy_index, 8.0),
        )
        for name, value, scale in numeric:
            if value is not None:
                values.append((name, _bounded(value, scale)))
        return values
