from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class PriorChoice:
    deck: tuple[int, ...]
    component_index: int | None
    compatible_components: int
    fallback_used: bool


class DeckMixturePrior:
    """Uniform prior over candidate decklists, with a measured generic fallback."""

    def __init__(self, decks: Sequence[Sequence[int]], *, generic_pool: Sequence[int] = ()) -> None:
        normalized = tuple(tuple(int(card_id) for card_id in deck) for deck in decks)
        if any(len(deck) != 60 for deck in normalized):
            raise ValueError("every prior component must be a 60-card deck")
        pool = tuple(int(card_id) for card_id in generic_pool)
        if not normalized and not pool:
            raise ValueError("the prior requires a deck component or generic card pool")
        if any(card_id <= 0 for deck in normalized for card_id in deck) or any(card_id <= 0 for card_id in pool):
            raise ValueError("prior card IDs must be positive")
        self.decks = normalized
        self.generic_pool = pool or tuple(card_id for deck in normalized for card_id in deck)

    def choose(self, visible: Mapping[int, int], rng: random.Random) -> PriorChoice:
        compatible = []
        for index, deck in enumerate(self.decks):
            counts = Counter(deck)
            if all(counts[int(card_id)] >= int(count) for card_id, count in visible.items()):
                compatible.append(index)
        if compatible:
            index = compatible[rng.randrange(len(compatible))]
            return PriorChoice(self.decks[index], index, len(compatible), False)

        # The fallback preserves every observed card and fills the unknown part
        # from the declared generic pool. It is intentionally reported because
        # it is weaker than a coherent deck-level sample.
        cards = list(int(card_id) for card_id, count in visible.items() for _ in range(int(count)))
        if len(cards) > 60:
            raise ValueError("public cards exceed a legal 60-card deck")
        for _ in range(60 - len(cards)):
            cards.append(self.generic_pool[rng.randrange(len(self.generic_pool))])
        rng.shuffle(cards)
        return PriorChoice(tuple(cards), None, 0, True)
