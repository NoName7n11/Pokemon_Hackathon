from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable

from plan1.game.catalog import AttackMetadata, CardCatalog, CardMetadata
from plan1.game.records import PlayerRecord, PokemonRecord, PublicObservationRecord


EVALUATOR_VERSION = "handcrafted-v1"
TERMINAL_SCORE = 1_000_000.0
NONTERMINAL_BOUND = 100_000.0

ITEM_CARD_TYPE = 1
SUPPORTER_CARD_TYPE = 3
STADIUM_CARD_TYPE = 4

COLORLESS_ENERGY = 0
PSYCHIC_ENERGY = 5
DARKNESS_ENERGY = 7
RAINBOW_ENERGY = 10
TEAM_ROCKET_ENERGY = 11


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    name: str
    raw: float
    weight: float
    value: float


@dataclass(frozen=True, slots=True)
class EvaluationBreakdown:
    version: str
    perspective: int
    total: float
    terminal: bool
    components: tuple[ScoreComponent, ...]
    metrics: tuple[tuple[str, float], ...]
    diagnostics: tuple[str, ...]

    def component(self, name: str) -> float:
        for component in self.components:
            if component.name == name:
                return component.value
        raise KeyError(name)


@dataclass(frozen=True, slots=True)
class _AttackProfile:
    damage: float
    raw_damage: int
    affordable: bool
    missing_energy: int
    dynamic_text: bool


@dataclass(frozen=True, slots=True)
class _SideProfile:
    prize_remaining: int
    board_hp: int
    bench_depth: int
    stage_value: int
    hand_size: int
    trainer_access: int
    supporter_access: int
    evolution_ready: int
    ability_bodies: int
    acceleration_bodies: int
    ready_attackers: int
    energy_readiness: float
    stranded_energy: int
    deck_safety: float
    status_burden: float
    retreat_flexibility: float


WEIGHTS: tuple[tuple[str, float], ...] = (
    ("prize_race", 1_200.0),
    ("board_hp", 0.45),
    ("bench_depth", 55.0),
    ("stage_development", 45.0),
    ("hand_size", 12.0),
    ("trainer_access", 16.0),
    ("supporter_access", 20.0),
    ("evolution_ready", 80.0),
    ("ability_potential", 30.0),
    ("energy_acceleration", 55.0),
    ("ready_attackers", 100.0),
    ("energy_readiness", 160.0),
    ("stranded_energy", -35.0),
    ("deck_safety", 90.0),
    ("status_burden", -90.0),
    ("retreat_flexibility", 90.0),
    ("attack_pressure", 2.2),
    ("lethal_pressure", 850.0),
    ("survivability", 1.4),
    ("multi_prize_liability", -350.0),
)


class HandcraftedEvaluator:
    """Transparent public-state evaluator for search leaves.

    Every nonterminal term is constructed as ``root - opponent``. This makes
    perspective conversion exactly antisymmetric and prevents search code from
    accidentally maximizing for both players. Printed attack damage is a lower
    fidelity estimate for attacks whose text changes damage; those cases are
    surfaced in diagnostics and can later be replaced by effect-aware features.
    """

    def __init__(self, catalog: CardCatalog) -> None:
        self._cards = {card.card_id: card for card in catalog.cards}
        self._attacks = {attack.attack_id: attack for attack in catalog.attacks}
        self._card_attacks = {
            card.card_id: tuple(self._attacks[attack_id] for attack_id in card.attack_ids if attack_id in self._attacks)
            for card in catalog.cards
        }
        self._ability_cards = frozenset(card.card_id for card in catalog.cards if card.skills)
        self._acceleration_cards = frozenset(
            card.card_id
            for card in catalog.cards
            if any(self._is_acceleration_text(skill.text) for skill in card.skills)
        )

    def score(self, observation: PublicObservationRecord, perspective: int) -> float:
        """Return the allocation-light scalar used inside the search loop."""
        if perspective not in (0, 1):
            raise ValueError("perspective must be player 0 or player 1")
        state = observation.state
        if state is None:
            return 0.0
        if len(state.players) != 2:
            raise ValueError("the evaluator requires exactly two players")
        if state.result != -1:
            if state.result == perspective:
                return TERMINAL_SCORE
            if state.result == 1 - perspective:
                return -TERMINAL_SCORE
            return 0.0
        terms, _, _, _, _, _ = self._position_terms(observation, perspective, set())
        total = sum(raw * weight for raw, (_, weight) in zip(terms, WEIGHTS))
        if not isfinite(total):
            raise ArithmeticError("evaluator produced a non-finite score")
        return max(-NONTERMINAL_BOUND, min(NONTERMINAL_BOUND, total))

    def evaluate(self, observation: PublicObservationRecord, perspective: int) -> EvaluationBreakdown:
        if perspective not in (0, 1):
            raise ValueError("perspective must be player 0 or player 1")
        state = observation.state
        if state is None:
            return EvaluationBreakdown(
                version=EVALUATOR_VERSION,
                perspective=perspective,
                total=0.0,
                terminal=False,
                components=(),
                metrics=(),
                diagnostics=("missing_state",),
            )
        if len(state.players) != 2:
            raise ValueError("the evaluator requires exactly two players")
        if state.result != -1:
            if state.result == perspective:
                total = TERMINAL_SCORE
            elif state.result == 1 - perspective:
                total = -TERMINAL_SCORE
            else:
                total = 0.0
            return EvaluationBreakdown(
                version=EVALUATOR_VERSION,
                perspective=perspective,
                total=total,
                terminal=True,
                components=(ScoreComponent("terminal", total, 1.0, total),),
                metrics=(),
                diagnostics=(),
            )

        diagnostics: set[str] = set()
        raw_terms, root_attack, opponent_attack, root_active, opponent_active, diagnostics = self._position_terms(
            observation, perspective, diagnostics
        )
        components = tuple(
            ScoreComponent(name=name, raw=float(raw), weight=weight, value=float(raw) * weight)
            for raw, (name, weight) in zip(raw_terms, WEIGHTS)
        )
        total = sum(component.value for component in components)
        if not isfinite(total):
            raise ArithmeticError("evaluator produced a non-finite score")
        total = max(-NONTERMINAL_BOUND, min(NONTERMINAL_BOUND, total))
        metrics = (
            ("root_attack_damage", root_attack.damage),
            ("opponent_attack_damage", opponent_attack.damage),
            ("root_missing_energy", float(root_attack.missing_energy)),
            ("opponent_missing_energy", float(opponent_attack.missing_energy)),
            ("root_active_hp", float(root_active.hp if root_active else 0)),
            ("opponent_active_hp", float(opponent_active.hp if opponent_active else 0)),
        )
        return EvaluationBreakdown(
            version=EVALUATOR_VERSION,
            perspective=perspective,
            total=total,
            terminal=False,
            components=components,
            metrics=metrics,
            diagnostics=tuple(sorted(diagnostics)),
        )

    def _position_terms(
        self,
        observation: PublicObservationRecord,
        perspective: int,
        diagnostics: set[str],
    ) -> tuple[
        tuple[float, ...],
        _AttackProfile,
        _AttackProfile,
        PokemonRecord | None,
        PokemonRecord | None,
        set[str],
    ]:
        state = observation.state
        if state is None:
            raise ValueError("position terms require a state")
        root_player = state.players[perspective]
        opponent_player = state.players[1 - perspective]
        root = self._side_profile(
            root_player,
            diagnostics,
            supporter_used=state.supporter_played and state.acting_player == perspective,
            retreat_used=state.retreated and state.acting_player == perspective,
        )
        opponent = self._side_profile(
            opponent_player,
            diagnostics,
            supporter_used=state.supporter_played and state.acting_player == 1 - perspective,
            retreat_used=state.retreated and state.acting_player == 1 - perspective,
        )
        root_active = self._active(root_player)
        opponent_active = self._active(opponent_player)
        root_attack = self._attack_profile(root_active, opponent_active, root_player, diagnostics)
        opponent_attack = self._attack_profile(opponent_active, root_active, opponent_player, diagnostics)
        terms = (
            float(opponent.prize_remaining - root.prize_remaining),
            float(root.board_hp - opponent.board_hp),
            float(root.bench_depth - opponent.bench_depth),
            float(root.stage_value - opponent.stage_value),
            float(root.hand_size - opponent.hand_size),
            float(root.trainer_access - opponent.trainer_access),
            float(root.supporter_access - opponent.supporter_access),
            float(root.evolution_ready - opponent.evolution_ready),
            float(root.ability_bodies - opponent.ability_bodies),
            float(root.acceleration_bodies - opponent.acceleration_bodies),
            float(root.ready_attackers - opponent.ready_attackers),
            root.energy_readiness - opponent.energy_readiness,
            float(root.stranded_energy - opponent.stranded_energy),
            root.deck_safety - opponent.deck_safety,
            root.status_burden - opponent.status_burden,
            root.retreat_flexibility - opponent.retreat_flexibility,
            root_attack.damage - opponent_attack.damage,
            self._lethal_value(root_attack, opponent_active) - self._lethal_value(opponent_attack, root_active),
            self._survival_margin(root_active, opponent_attack) - self._survival_margin(opponent_active, root_attack),
            self._liability(root_active, opponent_attack) - self._liability(opponent_active, root_attack),
        )
        return terms, root_attack, opponent_attack, root_active, opponent_active, diagnostics

    def _side_profile(
        self,
        player: PlayerRecord,
        diagnostics: set[str],
        *,
        supporter_used: bool,
        retreat_used: bool,
    ) -> _SideProfile:
        pokemon = tuple(mon for mon in player.active if mon is not None) + player.bench
        active = self._active(player)
        ready_attackers = 0
        readiness = 0.0
        stranded = 0
        stages = 0
        abilities = 0
        accelerators = 0
        in_play_names: set[str] = set()
        for mon in pokemon:
            card = self._card(mon.card_id, diagnostics)
            if card is None:
                stranded += len(mon.energies)
                continue
            if not mon.appear_this_turn:
                in_play_names.add(card.name.casefold())
            stages += 2 if card.stage2 else 1 if card.stage1 else 0
            abilities += int(card.card_id in self._ability_cards)
            accelerators += int(card.card_id in self._acceleration_cards)
            attacks = self._card_attacks.get(card.card_id, ())
            if attacks:
                missing = min(self._missing_energy(attack.energies, mon.energies) for attack in attacks)
                status_blocked = bool(
                    active is not None
                    and mon.serial == active.serial
                    and (player.asleep or player.paralyzed)
                )
                # Effect-only attacks still count as available actions even
                # when their printed damage is zero.
                ready_attackers += int(missing == 0 and not status_blocked)
                readiness += 0.0 if status_blocked else 1.0 / (1.0 + missing)
            elif mon.energies:
                stranded += len(mon.energies)

        trainer_access = supporter_access = evolution_ready = 0
        if player.hand is not None:
            for hand_card in player.hand:
                card = self._card(hand_card.card_id, diagnostics)
                if card is None:
                    continue
                trainer_access += int(card.card_type in (ITEM_CARD_TYPE, SUPPORTER_CARD_TYPE, STADIUM_CARD_TYPE))
                supporter_access += int(card.card_type == SUPPORTER_CARD_TYPE and not supporter_used)
                if card.evolves_from and card.evolves_from.casefold() in in_play_names:
                    evolution_ready += 1

        active_card = self._card(active.card_id, diagnostics) if active else None
        retreat_flexibility = 0.0
        if active and active_card and player.bench:
            retreat_cost = max(0, active_card.retreat_cost)
            if retreat_used or player.asleep or player.paralyzed:
                retreat_flexibility = -1.0
            else:
                retreat_flexibility = 1.0 if len(active.energies) >= retreat_cost else -min(1.0, (retreat_cost - len(active.energies)) / 3.0)
        status_burden = (
            float(player.poisoned)
            + float(player.burned)
            + 1.5 * float(player.asleep)
            + 2.0 * float(player.paralyzed)
            + 0.75 * float(player.confused)
        )
        return _SideProfile(
            prize_remaining=len(player.prize),
            board_hp=sum(mon.hp for mon in pokemon),
            bench_depth=len(player.bench),
            stage_value=stages,
            hand_size=min(player.hand_count, 12),
            trainer_access=min(trainer_access, 4),
            supporter_access=min(supporter_access, 2),
            evolution_ready=min(evolution_ready, 3),
            ability_bodies=min(abilities, 4),
            acceleration_bodies=min(accelerators, 3),
            ready_attackers=ready_attackers,
            energy_readiness=readiness,
            stranded_energy=stranded,
            deck_safety=self._deck_safety(player.deck_count),
            status_burden=status_burden,
            retreat_flexibility=retreat_flexibility,
        )

    def _attack_profile(
        self,
        attacker: PokemonRecord | None,
        defender: PokemonRecord | None,
        owner: PlayerRecord,
        diagnostics: set[str],
    ) -> _AttackProfile:
        if attacker is None:
            return _AttackProfile(0.0, 0, False, 99, False)
        card = self._card(attacker.card_id, diagnostics)
        if card is None or not card.attack_ids:
            return _AttackProfile(0.0, 0, False, 99, False)
        best_damage = 0.0
        best_raw = 0
        minimum_missing = 99
        any_affordable = False
        dynamic = False
        known_attacks = self._card_attacks.get(card.card_id, ())
        if len(known_attacks) != len(card.attack_ids):
            for attack_id in card.attack_ids:
                if attack_id not in self._attacks:
                    diagnostics.add(f"unknown_attack:{attack_id}")
        for attack in known_attacks:
            missing = self._missing_energy(attack.energies, attacker.energies)
            minimum_missing = min(minimum_missing, missing)
            dynamic = dynamic or self._dynamic_attack(attack)
            if missing:
                continue
            any_affordable = True
            damage = float(max(0, attack.damage))
            if defender is not None:
                defender_card = self._card(defender.card_id, diagnostics)
                if defender_card is not None:
                    if defender_card.weakness == card.energy_type:
                        damage *= 2.0
                    if defender_card.resistance == card.energy_type:
                        damage = max(0.0, damage - 30.0)
            if owner.asleep or owner.paralyzed:
                damage = 0.0
            elif owner.confused:
                damage *= 0.5
            if damage > best_damage:
                best_damage = damage
                best_raw = max(0, attack.damage)
        if dynamic:
            diagnostics.add("dynamic_attack_damage_approximated")
        return _AttackProfile(best_damage, best_raw, any_affordable, minimum_missing, dynamic)

    def _card(self, card_id: int, diagnostics: set[str]) -> CardMetadata | None:
        card = self._cards.get(card_id)
        if card is None:
            diagnostics.add(f"unknown_card:{card_id}")
        return card

    @staticmethod
    def _active(player: PlayerRecord) -> PokemonRecord | None:
        return next((pokemon for pokemon in player.active if pokemon is not None), None)

    @staticmethod
    def _is_acceleration_text(text: str) -> bool:
        lowered = text.casefold()
        return "attach" in lowered and "energy" in lowered

    @staticmethod
    def _dynamic_attack(attack: AttackMetadata) -> bool:
        text = attack.text.casefold()
        signals = ("more damage", "for each", "times", "damage counters", "instead")
        return any(signal in text for signal in signals)

    @staticmethod
    def _energy_matches(required: int, attached: int) -> bool:
        if required == COLORLESS_ENERGY:
            return True
        if attached == RAINBOW_ENERGY:
            return True
        if attached == TEAM_ROCKET_ENERGY and required in (PSYCHIC_ENERGY, DARKNESS_ENERGY):
            return True
        return required == attached

    @classmethod
    def _missing_energy(cls, cost: Iterable[int], attached: Iterable[int]) -> int:
        remaining = list(attached)
        colorless = 0
        missing = 0
        for required in cost:
            if required == COLORLESS_ENERGY:
                colorless += 1
                continue
            match = next((index for index, energy in enumerate(remaining) if cls._energy_matches(required, energy)), None)
            if match is None:
                missing += 1
            else:
                remaining.pop(match)
        return missing + max(0, colorless - len(remaining))

    def _prize_value(self, pokemon: PokemonRecord | None) -> int:
        if pokemon is None:
            return 0
        card = self._cards.get(pokemon.card_id)
        if card is None:
            return 1
        return 3 if card.mega_ex else 2 if card.ex else 1

    def _lethal_value(self, attack: _AttackProfile, target: PokemonRecord | None) -> float:
        if target is None or attack.damage <= 0 or attack.damage < target.hp:
            return 0.0
        return float(self._prize_value(target))

    @staticmethod
    def _survival_margin(active: PokemonRecord | None, incoming: _AttackProfile) -> float:
        if active is None:
            return -300.0
        return max(-300.0, min(300.0, active.hp - incoming.damage))

    def _liability(self, active: PokemonRecord | None, incoming: _AttackProfile) -> float:
        if active is None or active.max_hp <= 0:
            return 0.0
        damage_fraction = 1.0 - max(0.0, min(1.0, active.hp / active.max_hp))
        lethal = incoming.damage >= active.hp and incoming.damage > 0
        return self._prize_value(active) * (damage_fraction + float(lethal))

    @staticmethod
    def _deck_safety(deck_count: int) -> float:
        if deck_count <= 0:
            return -4.0
        if deck_count <= 2:
            return -3.0
        if deck_count <= 5:
            return -1.5
        return min(deck_count, 20) / 20.0
