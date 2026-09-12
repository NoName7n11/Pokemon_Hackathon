from __future__ import annotations

import unittest
from types import SimpleNamespace

import _path  # noqa: F401

from plan1.game.vocabulary import CardVocabulary, INVALID_TOKEN, PAD_TOKEN, UNKNOWN_TOKEN


class VocabularyTests(unittest.TestCase):
    def test_special_and_card_tokens_are_distinct(self) -> None:
        vocabulary = CardVocabulary.from_card_data([SimpleNamespace(cardId=8), SimpleNamespace(cardId=3)])
        self.assertEqual(vocabulary.card_ids, (3, 8))
        self.assertEqual(vocabulary.encode(None), PAD_TOKEN)
        self.assertEqual(vocabulary.encode(999), UNKNOWN_TOKEN)
        self.assertEqual(vocabulary.encode(3, invalid=True), INVALID_TOKEN)
        token = vocabulary.encode(8)
        self.assertEqual(vocabulary.decode(token), 8)
        self.assertEqual(vocabulary.size, 5)

    def test_duplicate_or_unsorted_ids_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CardVocabulary((2, 1))


if __name__ == "__main__":
    unittest.main()
