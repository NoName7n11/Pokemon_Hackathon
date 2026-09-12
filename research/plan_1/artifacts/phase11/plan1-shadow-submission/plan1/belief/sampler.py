from __future__ import annotations

import json
import random
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from plan1.belief.card_accounting import AccountingError, account_public_cards, residual_deck
from plan1.belief.priors import DeckMixturePrior
from plan1.engine.lifecycle import SearchInputs
from plan1.game.records import PublicObservationRecord
from plan1.reproducibility import canonical_json_hash


@dataclass(frozen=True, slots=True)
class BeliefSample:
    inputs: SearchInputs
    mode: str
    fingerprint: str
    fallback_used: bool
    compatible_components: int
    component_index: int | None


class HiddenStateSampler(Protocol):
    def sample(self, record: PublicObservationRecord, rng: random.Random) -> BeliefSample: ...


def _deal(pool: list[int], counts: Sequence[int], rng: random.Random) -> tuple[tuple[int, ...], ...]:
    required = sum(counts)
    if len(pool) < required:
        raise AccountingError(f"hidden zones require {required} cards but only {len(pool)} remain")
    rng.shuffle(pool)
    result = []
    offset = 0
    for count in counts:
        result.append(tuple(pool[offset : offset + count]))
        offset += count
    return tuple(result)


def _merge_prizes(prizes: Sequence[Any], sampled: Sequence[int]) -> tuple[int, ...]:
    unknown = iter(sampled)
    merged = tuple(card.card_id if card is not None else next(unknown) for card in prizes)
    try:
        next(unknown)
    except StopIteration:
        return merged
    raise AccountingError("sampled prize count exceeds unknown prize positions")


class BeliefSampler:
    def __init__(
        self,
        own_deck: Sequence[int],
        opponent_prior: DeckMixturePrior,
        *,
        basic_pokemon_ids: Sequence[int] = (),
    ) -> None:
        if len(own_deck) != 60:
            raise ValueError("own_deck must contain 60 cards")
        self.own_deck = tuple(int(card_id) for card_id in own_deck)
        self.opponent_prior = opponent_prior
        self.basic_pokemon_ids = frozenset(int(card_id) for card_id in basic_pokemon_ids)

    def sample(self, record: PublicObservationRecord, rng: random.Random) -> BeliefSample:
        accounting = account_public_cards(record)
        root = accounting.root_player
        opponent = 1 - root

        own_pool = residual_deck(self.own_deck, accounting.visible_counter(root))
        own_deck_count = accounting.hidden_count(root, "deck")
        own_prize_count = accounting.hidden_count(root, "prize")
        if accounting.exact_own_deck is not None:
            own_deck = accounting.exact_own_deck
            if len(own_deck) != own_deck_count:
                raise AccountingError("visible search deck does not match public deck count")
            exact_counts = account_public_cards(record).visible_counter(root)
            exact_counts.update(own_deck)
            own_prize_pool = residual_deck(self.own_deck, exact_counts)
            (own_prize,) = _deal(own_prize_pool, (own_prize_count,), rng)
        else:
            own_deck, own_prize = _deal(own_pool, (own_deck_count, own_prize_count), rng)

        choice = self.opponent_prior.choose(accounting.visible_counter(opponent), rng)
        opponent_pool = residual_deck(choice.deck, accounting.visible_counter(opponent))
        opponent_active: tuple[int, ...] = ()
        state = record.state
        if state is not None and state.players[opponent].active and state.players[opponent].active[0] is None:
            candidates = [card_id for card_id in opponent_pool if card_id in self.basic_pokemon_ids]
            if not candidates:
                raise AccountingError("face-down opposing Active requires a sampled Basic Pokemon")
            selected = candidates[rng.randrange(len(candidates))]
            opponent_active = (selected,)
            opponent_pool.remove(selected)
        opponent_deck, opponent_prize, opponent_hand = _deal(
            opponent_pool,
            (
                accounting.hidden_count(opponent, "deck"),
                accounting.hidden_count(opponent, "prize"),
                accounting.hidden_count(opponent, "hand"),
            ),
            rng,
        )
        inputs = SearchInputs.from_sequences(
            your_deck=own_deck,
            your_prize=_merge_prizes(record.state.players[root].prize, own_prize),
            opponent_deck=opponent_deck,
            opponent_prize=_merge_prizes(record.state.players[opponent].prize, opponent_prize),
            opponent_hand=opponent_hand,
            opponent_active=opponent_active,
        )
        fingerprint = canonical_json_hash({"mode": "generic", "inputs": asdict(inputs)})
        return BeliefSample(
            inputs=inputs,
            mode="generic",
            fingerprint=fingerprint,
            fallback_used=choice.fallback_used,
            compatible_components=choice.compatible_components,
            component_index=choice.component_index,
        )


class MirrorFillSampler:
    """Phase 4's repeated-card prediction retained as an explicit baseline."""

    def __init__(
        self,
        own_deck: Sequence[int],
        opponent_deck: Sequence[int] | None = None,
        *,
        basic_pokemon_ids: Sequence[int] = (),
    ) -> None:
        self.own_deck = tuple(int(card_id) for card_id in own_deck)
        self.opponent_deck = tuple(int(card_id) for card_id in (opponent_deck or own_deck))
        self.basic_pokemon_ids = frozenset(int(card_id) for card_id in basic_pokemon_ids)

    @staticmethod
    def _take(pool: Sequence[int], count: int) -> tuple[int, ...]:
        return tuple(pool[index % len(pool)] for index in range(count))

    def sample(self, record: PublicObservationRecord, rng: random.Random) -> BeliefSample:
        del rng
        accounting = account_public_cards(record)
        root = accounting.root_player
        opponent = 1 - root
        opponent_active: tuple[int, ...] = ()
        state = record.state
        if state is not None and state.players[opponent].active and state.players[opponent].active[0] is None:
            candidates = [card_id for card_id in self.opponent_deck if card_id in self.basic_pokemon_ids]
            if not candidates:
                raise AccountingError("face-down opposing Active requires a Basic Pokemon")
            opponent_active = (candidates[0],)
        own_unknown_prizes = self._take(self.own_deck, accounting.hidden_count(root, "prize"))
        opponent_unknown_prizes = self._take(
            self.opponent_deck, accounting.hidden_count(opponent, "prize")
        )
        inputs = SearchInputs.from_sequences(
            your_deck=self._take(self.own_deck, accounting.hidden_count(root, "deck")),
            your_prize=_merge_prizes(record.state.players[root].prize, own_unknown_prizes),
            opponent_deck=self._take(self.opponent_deck, accounting.hidden_count(opponent, "deck")),
            opponent_prize=_merge_prizes(
                record.state.players[opponent].prize, opponent_unknown_prizes
            ),
            opponent_hand=self._take(self.opponent_deck, accounting.hidden_count(opponent, "hand")),
            opponent_active=opponent_active,
        )
        return BeliefSample(inputs, "mirror_fill", canonical_json_hash(asdict(inputs)), False, 1, 0)


class OracleSampler:
    """Offline diagnostic sampler. Exact inputs must be injected by the evaluator."""

    def __init__(self, inputs: SearchInputs) -> None:
        self.inputs = inputs

    def sample(self, record: PublicObservationRecord, rng: random.Random) -> BeliefSample:
        del record, rng
        return BeliefSample(self.inputs, "oracle", canonical_json_hash(asdict(self.inputs)), False, 1, 0)


def oracle_inputs_from_visualizer(visualizer_json: str, root_player: int) -> SearchInputs:
    """Extract exact hidden zones from local replay data for offline diagnostics.

    This function is intentionally separate from the agent and public records.
    Competition policy code must never call the visualizer.
    """
    frames = json.loads(visualizer_json)
    if not isinstance(frames, list) or not frames:
        raise ValueError("visualizer did not contain frames")
    current = frames[-1]["current"]
    players = current["players"]
    me, opponent = players[root_player], players[1 - root_player]

    def ids(cards: Sequence[dict[str, Any] | None]) -> tuple[int, ...]:
        return tuple(int(card["id"]) for card in cards if card is not None)

    opponent_active: tuple[int, ...] = ()
    active = opponent.get("active") or []
    if active and active[0] is not None:
        opponent_active = (int(active[0]["id"]),)
    return SearchInputs.from_sequences(
        your_deck=ids(me.get("deck") or []),
        your_prize=ids(me.get("prize") or []),
        opponent_deck=ids(opponent.get("deck") or []),
        opponent_prize=ids(opponent.get("prize") or []),
        opponent_hand=ids(opponent.get("hand") or []),
        opponent_active=opponent_active,
    )
