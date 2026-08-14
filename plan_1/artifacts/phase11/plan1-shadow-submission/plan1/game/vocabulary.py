from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Any, Iterable

from plan1.reproducibility import canonical_json_hash


PAD_TOKEN = 0
UNKNOWN_TOKEN = 1
INVALID_TOKEN = 2
FIRST_CARD_TOKEN = 3


@dataclass(frozen=True, slots=True)
class CardVocabulary:
    card_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.card_ids))) != self.card_ids:
            raise ValueError("card_ids must be sorted, unique positive integers")
        if any(isinstance(card_id, bool) or card_id <= 0 for card_id in self.card_ids):
            raise ValueError("card_ids must be positive integers")

    @classmethod
    def from_card_data(cls, cards: Iterable[Any]) -> "CardVocabulary":
        return cls(tuple(sorted({int(card.cardId) for card in cards})))

    @property
    def size(self) -> int:
        return FIRST_CARD_TOKEN + len(self.card_ids)

    @property
    def fingerprint(self) -> str:
        return canonical_json_hash(self.to_dict())

    def encode(self, card_id: int | None, *, invalid: bool = False) -> int:
        if invalid:
            return INVALID_TOKEN
        if card_id is None:
            return PAD_TOKEN
        index = bisect.bisect_left(self.card_ids, card_id)
        if index >= len(self.card_ids) or self.card_ids[index] != card_id:
            return UNKNOWN_TOKEN
        return FIRST_CARD_TOKEN + index

    def decode(self, token: int) -> int | None:
        if token == PAD_TOKEN:
            return None
        if token in (UNKNOWN_TOKEN, INVALID_TOKEN):
            raise ValueError("UNKNOWN and INVALID tokens do not decode to a card ID")
        index = token - FIRST_CARD_TOKEN
        if index < 0 or index >= len(self.card_ids):
            raise ValueError(f"token is outside vocabulary: {token}")
        return self.card_ids[index]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "special_tokens": {"PAD": PAD_TOKEN, "UNKNOWN": UNKNOWN_TOKEN, "INVALID": INVALID_TOKEN},
            "card_ids": list(self.card_ids),
            "size": self.size,
        }
