from __future__ import annotations

import unittest
from types import SimpleNamespace

import _path  # noqa: F401

from plan1.game.catalog import CardCatalog


def attack(attack_id: int):
    return SimpleNamespace(attackId=attack_id, name="Hit", text="", damage=20, energies=[1])


def card(card_id: int, attack_ids: list[int]):
    return SimpleNamespace(
        cardId=card_id, name="Card", cardType=0, retreatCost=1, hp=60,
        weakness=None, resistance=None, energyType=1, basic=True, stage1=False,
        stage2=False, ex=False, megaEx=False, tera=False, aceSpec=False,
        evolvesFrom=None, skills=[SimpleNamespace(name="Skill", text="Text")],
        attacks=attack_ids,
    )


class CatalogTests(unittest.TestCase):
    def test_catalog_is_sorted_and_complete(self) -> None:
        catalog = CardCatalog.from_engine([card(2, [20]), card(1, [10])], [attack(20), attack(10)])
        self.assertEqual([item.card_id for item in catalog.cards], [1, 2])
        self.assertEqual([item.attack_id for item in catalog.attacks], [10, 20])
        self.assertEqual(catalog.cards[0].skills[0].name, "Skill")

    def test_missing_attack_reference_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing attacks"):
            CardCatalog.from_engine([card(1, [99])], [attack(10)])


if __name__ == "__main__":
    unittest.main()
