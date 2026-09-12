from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from plan1.game.records import PlayerRecord, PublicObservationRecord


class AccountingError(ValueError):
    """Raised when public cards cannot fit a declared deck multiset."""


def _cards_from_pokemon(player: PlayerRecord) -> Iterable[int]:
    for pokemon in (*player.active, *player.bench):
        if pokemon is None:
            continue
        yield pokemon.card_id
        yield from (card.card_id for card in pokemon.energy_cards)
        yield from (card.card_id for card in pokemon.tools)
        yield from (card.card_id for card in pokemon.pre_evolution)


def _visible_cards(player: PlayerRecord, *, include_hand: bool) -> Counter[int]:
    result = Counter(_cards_from_pokemon(player))
    result.update(card.card_id for card in player.discard)
    if include_hand and player.hand is not None:
        result.update(card.card_id for card in player.hand)
    return result


@dataclass(frozen=True, slots=True)
class PublicCardAccounting:
    root_player: int
    visible: tuple[tuple[tuple[int, int], ...], ...]
    hidden_counts: tuple[tuple[int, int, int], ...]
    exact_own_deck: tuple[int, ...] | None

    def visible_counter(self, player_index: int) -> Counter[int]:
        return Counter(dict(self.visible[player_index]))

    def hidden_count(self, player_index: int, zone: str) -> int:
        deck, prize, hand = self.hidden_counts[player_index]
        return {"deck": deck, "prize": prize, "hand": hand}[zone]


def account_public_cards(record: PublicObservationRecord, *, root_player: int | None = None) -> PublicCardAccounting:
    state = record.state
    if state is None or len(state.players) != 2:
        raise AccountingError("belief accounting requires a two-player state")
    root = state.acting_player if root_player is None else root_player
    if root not in (0, 1):
        raise AccountingError("root_player must be 0 or 1")

    visible = [_visible_cards(player, include_hand=index == root) for index, player in enumerate(state.players)]
    for card in state.stadium:
        if card.player_index in (0, 1):
            visible[card.player_index][card.card_id] += 1

    exact_own_deck = None
    if record.selection is not None and record.selection.deck is not None:
        exact_own_deck = tuple(card.card_id for card in record.selection.deck)

    hidden_counts = []
    for index, player in enumerate(state.players):
        unknown_prizes = sum(card is None for card in player.prize)
        hidden_counts.append(
            (
                player.deck_count,
                unknown_prizes,
                0 if index == root and player.hand is not None else player.hand_count,
            )
        )
        visible[index].update(card.card_id for card in player.prize if card is not None)

    return PublicCardAccounting(
        root_player=root,
        visible=tuple(tuple(sorted(counter.items())) for counter in visible),
        hidden_counts=tuple(hidden_counts),
        exact_own_deck=exact_own_deck,
    )


def residual_deck(deck: Sequence[int], visible: Mapping[int, int]) -> list[int]:
    remaining = Counter(int(card_id) for card_id in deck)
    for card_id, count in visible.items():
        remaining[int(card_id)] -= int(count)
        if remaining[int(card_id)] < 0:
            raise AccountingError(f"public count for card {card_id} exceeds declared deck")
    return list(remaining.elements())
