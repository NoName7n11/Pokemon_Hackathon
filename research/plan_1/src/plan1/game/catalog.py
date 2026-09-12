from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from plan1.reproducibility import canonical_json_hash


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    name: str
    text: str


@dataclass(frozen=True, slots=True)
class AttackMetadata:
    attack_id: int
    name: str
    text: str
    damage: int
    energies: tuple[int, ...]

    @classmethod
    def from_engine(cls, attack: Any) -> "AttackMetadata":
        return cls(
            attack_id=int(attack.attackId),
            name=str(attack.name),
            text=str(attack.text),
            damage=int(attack.damage),
            energies=tuple(int(energy) for energy in attack.energies),
        )


@dataclass(frozen=True, slots=True)
class CardMetadata:
    card_id: int
    name: str
    card_type: int
    retreat_cost: int
    hp: int
    weakness: int | None
    resistance: int | None
    energy_type: int
    basic: bool
    stage1: bool
    stage2: bool
    ex: bool
    mega_ex: bool
    tera: bool
    ace_spec: bool
    evolves_from: str | None
    skills: tuple[SkillMetadata, ...]
    attack_ids: tuple[int, ...]

    @classmethod
    def from_engine(cls, card: Any) -> "CardMetadata":
        return cls(
            card_id=int(card.cardId),
            name=str(card.name),
            card_type=int(card.cardType),
            retreat_cost=int(card.retreatCost),
            hp=int(card.hp),
            weakness=None if card.weakness is None else int(card.weakness),
            resistance=None if card.resistance is None else int(card.resistance),
            energy_type=int(card.energyType),
            basic=bool(card.basic),
            stage1=bool(card.stage1),
            stage2=bool(card.stage2),
            ex=bool(card.ex),
            mega_ex=bool(card.megaEx),
            tera=bool(card.tera),
            ace_spec=bool(card.aceSpec),
            evolves_from=None if card.evolvesFrom is None else str(card.evolvesFrom),
            skills=tuple(SkillMetadata(name=str(skill.name), text=str(skill.text)) for skill in card.skills),
            attack_ids=tuple(int(attack_id) for attack_id in card.attacks),
        )


@dataclass(frozen=True, slots=True)
class CardCatalog:
    cards: tuple[CardMetadata, ...]
    attacks: tuple[AttackMetadata, ...]

    @classmethod
    def from_engine(cls, cards: Iterable[Any], attacks: Iterable[Any]) -> "CardCatalog":
        card_records = tuple(sorted((CardMetadata.from_engine(card) for card in cards), key=lambda card: card.card_id))
        attack_records = tuple(
            sorted((AttackMetadata.from_engine(attack) for attack in attacks), key=lambda attack: attack.attack_id)
        )
        card_ids = [card.card_id for card in card_records]
        attack_ids = [attack.attack_id for attack in attack_records]
        if len(card_ids) != len(set(card_ids)):
            raise ValueError("card catalog contains duplicate card IDs")
        if len(attack_ids) != len(set(attack_ids)):
            raise ValueError("card catalog contains duplicate attack IDs")
        missing_attacks = sorted(
            {attack_id for card in card_records for attack_id in card.attack_ids} - set(attack_ids)
        )
        if missing_attacks:
            raise ValueError(f"card catalog references missing attacks: {missing_attacks[:20]}")
        return cls(cards=card_records, attacks=attack_records)

    @property
    def fingerprint(self) -> str:
        return canonical_json_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "cards": [asdict(card) for card in self.cards],
            "attacks": [asdict(attack) for attack in self.attacks],
        }
