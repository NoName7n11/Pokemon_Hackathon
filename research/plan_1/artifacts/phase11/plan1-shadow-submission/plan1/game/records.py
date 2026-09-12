from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from enum import IntEnum
from typing import Any

from plan1.reproducibility import canonical_json_hash


Scalar = int | bool | str | None


def _enum_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("boolean is not an enum value")
    if isinstance(value, (int, IntEnum)):
        return int(value)
    raise TypeError(f"expected enum/int, got {type(value).__name__}")


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"expected optional integer, got {type(value).__name__}")
    return value


@dataclass(frozen=True, slots=True)
class CardRecord:
    card_id: int
    serial: int
    player_index: int

    @classmethod
    def from_engine(cls, card: Any) -> "CardRecord":
        return cls(card_id=int(card.id), serial=int(card.serial), player_index=int(card.playerIndex))


@dataclass(frozen=True, slots=True)
class PokemonRecord:
    card_id: int
    serial: int
    hp: int
    max_hp: int
    appear_this_turn: bool
    energies: tuple[int, ...]
    energy_cards: tuple[CardRecord, ...]
    tools: tuple[CardRecord, ...]
    pre_evolution: tuple[CardRecord, ...]

    @classmethod
    def from_engine(cls, pokemon: Any) -> "PokemonRecord":
        return cls(
            card_id=int(pokemon.id),
            serial=int(pokemon.serial),
            hp=int(pokemon.hp),
            max_hp=int(pokemon.maxHp),
            appear_this_turn=bool(pokemon.appearThisTurn),
            energies=tuple(int(energy) for energy in pokemon.energies),
            energy_cards=tuple(CardRecord.from_engine(card) for card in pokemon.energyCards),
            tools=tuple(CardRecord.from_engine(card) for card in pokemon.tools),
            pre_evolution=tuple(CardRecord.from_engine(card) for card in pokemon.preEvolution),
        )


@dataclass(frozen=True, slots=True)
class PlayerRecord:
    active: tuple[PokemonRecord | None, ...]
    bench: tuple[PokemonRecord, ...]
    bench_max: int
    deck_count: int
    discard: tuple[CardRecord, ...]
    prize: tuple[CardRecord | None, ...]
    hand_count: int
    hand: tuple[CardRecord, ...] | None
    poisoned: bool
    burned: bool
    asleep: bool
    paralyzed: bool
    confused: bool

    @classmethod
    def from_engine(cls, player: Any) -> "PlayerRecord":
        hand = None if player.hand is None else tuple(CardRecord.from_engine(card) for card in player.hand)
        return cls(
            active=tuple(None if pokemon is None else PokemonRecord.from_engine(pokemon) for pokemon in player.active),
            bench=tuple(PokemonRecord.from_engine(pokemon) for pokemon in player.bench),
            bench_max=int(player.benchMax),
            deck_count=int(player.deckCount),
            discard=tuple(CardRecord.from_engine(card) for card in player.discard),
            prize=tuple(None if card is None else CardRecord.from_engine(card) for card in player.prize),
            hand_count=int(player.handCount),
            hand=hand,
            poisoned=bool(player.poisoned),
            burned=bool(player.burned),
            asleep=bool(player.asleep),
            paralyzed=bool(player.paralyzed),
            confused=bool(player.confused),
        )


@dataclass(frozen=True, slots=True)
class StateRecord:
    turn: int
    turn_action_count: int
    acting_player: int
    first_player: int
    supporter_played: bool
    stadium_played: bool
    energy_attached: bool
    retreated: bool
    result: int
    stadium: tuple[CardRecord, ...]
    looking: tuple[CardRecord | None, ...] | None
    players: tuple[PlayerRecord, ...]

    @classmethod
    def from_engine(cls, state: Any) -> "StateRecord":
        looking = None
        if state.looking is not None:
            looking = tuple(None if card is None else CardRecord.from_engine(card) for card in state.looking)
        return cls(
            turn=int(state.turn),
            turn_action_count=int(state.turnActionCount),
            acting_player=int(state.yourIndex),
            first_player=int(state.firstPlayer),
            supporter_played=bool(state.supporterPlayed),
            stadium_played=bool(state.stadiumPlayed),
            energy_attached=bool(state.energyAttached),
            retreated=bool(state.retreated),
            result=int(state.result),
            stadium=tuple(CardRecord.from_engine(card) for card in state.stadium),
            looking=looking,
            players=tuple(PlayerRecord.from_engine(player) for player in state.players),
        )


@dataclass(frozen=True, slots=True)
class OptionRecord:
    option_type: int
    number: int | None
    area: int | None
    index: int | None
    player_index: int | None
    tool_index: int | None
    energy_index: int | None
    count: int | None
    in_play_area: int | None
    in_play_index: int | None
    attack_id: int | None
    card_id: int | None
    serial: int | None
    special_condition_type: int | None

    @classmethod
    def from_engine(cls, option: Any) -> "OptionRecord":
        return cls(
            option_type=int(option.type),
            number=_optional_int(option.number),
            area=_enum_int(option.area),
            index=_optional_int(option.index),
            player_index=_optional_int(option.playerIndex),
            tool_index=_optional_int(option.toolIndex),
            energy_index=_optional_int(option.energyIndex),
            count=_optional_int(option.count),
            in_play_area=_enum_int(option.inPlayArea),
            in_play_index=_optional_int(option.inPlayIndex),
            attack_id=_optional_int(option.attackId),
            card_id=_optional_int(option.cardId),
            serial=_optional_int(option.serial),
            special_condition_type=_enum_int(option.specialConditionType),
        )

    @property
    def fingerprint(self) -> str:
        return canonical_json_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class SelectionRecord:
    select_type: int
    context: int
    min_count: int
    max_count: int
    remain_damage_counter: int
    remain_energy_cost: int
    options: tuple[OptionRecord, ...]
    deck: tuple[CardRecord, ...] | None
    context_card: CardRecord | None
    effect: CardRecord | None

    @classmethod
    def from_engine(cls, select: Any) -> "SelectionRecord":
        deck = None if select.deck is None else tuple(CardRecord.from_engine(card) for card in select.deck)
        return cls(
            select_type=int(select.type),
            context=int(select.context),
            min_count=int(select.minCount),
            max_count=int(select.maxCount),
            remain_damage_counter=int(select.remainDamageCounter),
            remain_energy_cost=int(select.remainEnergyCost),
            options=tuple(OptionRecord.from_engine(option) for option in select.option),
            deck=deck,
            context_card=None if select.contextCard is None else CardRecord.from_engine(select.contextCard),
            effect=None if select.effect is None else CardRecord.from_engine(select.effect),
        )

    @property
    def fingerprint(self) -> str:
        return canonical_json_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class LogRecord:
    log_type: int
    attributes: tuple[tuple[str, Scalar], ...]

    @classmethod
    def from_engine(cls, log: Any) -> "LogRecord":
        attributes: list[tuple[str, Scalar]] = []
        for field in fields(log):
            if field.name == "type":
                continue
            value = getattr(log, field.name)
            if isinstance(value, IntEnum):
                value = int(value)
            if value is not None and not isinstance(value, (int, bool, str)):
                raise TypeError(f"unsupported log attribute {field.name}: {type(value).__name__}")
            attributes.append((field.name, value))
        return cls(log_type=int(log.type), attributes=tuple(attributes))


@dataclass(frozen=True, slots=True)
class PublicObservationRecord:
    schema_version: int
    selection: SelectionRecord | None
    logs: tuple[LogRecord, ...]
    state: StateRecord | None

    @classmethod
    def from_engine(cls, observation: Any) -> "PublicObservationRecord":
        # search_begin_input is intentionally not read. It is an opaque native
        # simulator reconstruction payload, not a policy/model feature.
        return cls(
            schema_version=1,
            selection=None if observation.select is None else SelectionRecord.from_engine(observation.select),
            logs=tuple(LogRecord.from_engine(log) for log in observation.logs),
            state=None if observation.current is None else StateRecord.from_engine(observation.current),
        )

    @property
    def fingerprint(self) -> str:
        return canonical_json_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
