from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from plan1.evaluation.handcrafted import HandcraftedEvaluator
from plan1.game.catalog import AttackMetadata, CardCatalog, CardMetadata, SkillMetadata
from plan1.game.records import CardRecord, PlayerRecord, PokemonRecord, PublicObservationRecord, StateRecord


@dataclass(frozen=True, slots=True)
class TacticalFixture:
    name: str
    preferred: PublicObservationRecord
    rejected: PublicObservationRecord
    perspective: int
    reason: str


@lru_cache(maxsize=1)
def synthetic_catalog() -> CardCatalog:
    attacks = (
        AttackMetadata(101, "Measured Strike", "", 60, (1,)),
        AttackMetadata(102, "Return Fire", "", 100, (2, 0)),
        AttackMetadata(103, "Weak Hit", "", 10, (1,)),
        AttackMetadata(104, "Mega Burst", "", 180, (2, 2, 0)),
        AttackMetadata(105, "Scaling Hit", "This attack does 20 more damage for each Energy.", 20, (1,)),
    )
    cards = (
        _card(1, "Striker", hp=120, energy_type=1, retreat=1, attacks=(101,)),
        _card(2, "Tank", hp=180, energy_type=2, retreat=2, attacks=(102,)),
        _card(3, "Weakling", hp=50, energy_type=1, retreat=1, attacks=(103,)),
        _card(4, "Mega Threat ex", hp=300, energy_type=2, retreat=3, attacks=(104,), ex=True, mega=True),
        _card(5, "Prize Target ex", hp=240, energy_type=1, retreat=2, attacks=(101,), weakness=2, ex=True),
        _card(6, "Evolved Striker", hp=170, energy_type=1, retreat=1, attacks=(105,), stage1=True, evolves_from="Striker"),
        _card(7, "Energy Guide", hp=90, energy_type=1, retreat=1, attacks=(103,), skills=(SkillMetadata("Guide", "Attach a Grass Energy from your discard pile."),)),
        _card(8, "Pivot", hp=80, energy_type=0, retreat=2),
        _card(20, "Search Item", card_type=1),
        _card(21, "Draw Supporter", card_type=3),
    )
    return CardCatalog(cards=cards, attacks=attacks)


def tactical_fixtures() -> tuple[TacticalFixture, ...]:
    neutral_p0 = _player(_pokemon(1, energies=(1,)), bench=(_pokemon(7),))
    neutral_p1 = _player(_pokemon(2, energies=(2, 0)), bench=(_pokemon(3),))

    terminal_nonterminal = _observation(neutral_p0, neutral_p1)
    fixtures = [
        TacticalFixture(
            "terminal_win_over_nonterminal",
            _observation(neutral_p0, neutral_p1, result=0),
            terminal_nonterminal,
            0,
            "A proven win must override every heuristic state score.",
        ),
        TacticalFixture(
            "nonterminal_over_terminal_loss",
            terminal_nonterminal,
            _observation(neutral_p0, neutral_p1, result=1),
            0,
            "A proven loss must score below every live position.",
        ),
        TacticalFixture(
            "prize_race_monotonic",
            _observation(_player(_pokemon(1, energies=(1,)), prizes=4), neutral_p1),
            _observation(_player(_pokemon(1, energies=(1,)), prizes=5), neutral_p1),
            0,
            "Taking an uncompensated prize must improve evaluation.",
        ),
        TacticalFixture(
            "attack_over_avoidable_pass",
            _observation(neutral_p0, _player(_pokemon(2, hp=120, energies=(2, 0)), bench=(_pokemon(3),))),
            _observation(neutral_p0, _player(_pokemon(2, hp=180, energies=(2, 0)), bench=(_pokemon(3),))),
            0,
            "Equivalent post-action states must reward damage actually dealt.",
        ),
        TacticalFixture(
            "useful_energy_readiness",
            _observation(_player(_pokemon(1, energies=(1,))), neutral_p1),
            _observation(_player(_pokemon(1)), neutral_p1),
            0,
            "An energy that activates an attack must not reduce readiness.",
        ),
        TacticalFixture(
            "stall_break_ready_attacker",
            _observation(_player(_pokemon(1, energies=(1,)), bench=(_pokemon(3),)), neutral_p1),
            _observation(_player(_pokemon(3), bench=(_pokemon(1, energies=(1,)),)), neutral_p1),
            0,
            "A ready meaningful attacker should be active instead of stalling behind a weak body.",
        ),
        TacticalFixture(
            "promotion_attacker_discipline",
            _observation(_player(_pokemon(4, energies=(2, 2, 0)), bench=(_pokemon(3),)), neutral_p1),
            _observation(_player(_pokemon(3), bench=(_pokemon(4, energies=(2, 2, 0)),)), neutral_p1),
            0,
            "Forced promotion should expose the prepared attacker, not the weakest bench Pokemon.",
        ),
        TacticalFixture(
            "retreat_escape_available",
            _observation(_player(_pokemon(8, energies=(0, 0)), bench=(_pokemon(1, energies=(1,)),)), neutral_p1),
            _observation(_player(_pokemon(8), bench=(_pokemon(1, energies=(1,)),)), neutral_p1),
            0,
            "A stranded active with a prepared bench attacker is better when retreat is payable.",
        ),
        TacticalFixture(
            "live_damage_targeting",
            _observation(neutral_p0, _player(_pokemon(5, hp=30, energies=(1,)), bench=(_pokemon(3),))),
            _observation(neutral_p0, _player(_pokemon(5, hp=180, energies=(1,)), bench=(_pokemon(3),))),
            0,
            "Live HP and multi-prize knockout proximity must affect target value.",
        ),
        TacticalFixture(
            "avoid_opponent_ko_back",
            _observation(_player(_pokemon(2, hp=150, energies=(2, 0))), _player(_pokemon(4, energies=(2, 2, 0)))),
            _observation(_player(_pokemon(2, hp=80, energies=(2, 0))), _player(_pokemon(4, energies=(2, 2, 0)))),
            0,
            "Otherwise equal lines should prefer an active that survives the likely reply.",
        ),
        TacticalFixture(
            "weakness_pressure",
            _observation(_player(_pokemon(4, energies=(2, 2, 0))), _player(_pokemon(5, hp=240, energies=(1,)))),
            _observation(_player(_pokemon(4, energies=(2, 2, 0))), _player(_pokemon(2, hp=240, max_hp=240, energies=(2, 0)))),
            0,
            "Exposed weakness should increase immediate attack pressure.",
        ),
        TacticalFixture(
            "evolution_in_hand_ready",
            _observation(_player(_pokemon(1), hand=(6,)), neutral_p1),
            _observation(_player(_pokemon(1), hand=()), neutral_p1),
            0,
            "A visible legal evolution line is useful board development.",
        ),
        TacticalFixture(
            "decking_risk",
            _observation(_player(_pokemon(1, energies=(1,)), deck=12), neutral_p1),
            _observation(_player(_pokemon(1, energies=(1,)), deck=1), neutral_p1),
            0,
            "A safe deck count should beat an otherwise identical near-deck-out state.",
        ),
    ]
    return tuple(fixtures)


def run_tactical_suite(evaluator: HandcraftedEvaluator | None = None) -> dict[str, object]:
    evaluator = evaluator or HandcraftedEvaluator(synthetic_catalog())
    results: list[dict[str, object]] = []
    for fixture in tactical_fixtures():
        preferred = evaluator.evaluate(fixture.preferred, fixture.perspective)
        rejected = evaluator.evaluate(fixture.rejected, fixture.perspective)
        results.append(
            {
                "name": fixture.name,
                "reason": fixture.reason,
                "preferred_score": preferred.total,
                "rejected_score": rejected.total,
                "margin": preferred.total - rejected.total,
                "passed": preferred.total > rejected.total,
            }
        )
    return {
        "schema_version": 1,
        "fixture_count": len(results),
        "passed_count": sum(bool(result["passed"]) for result in results),
        "passed": all(bool(result["passed"]) for result in results),
        "fixtures": results,
    }


def _card(
    card_id: int,
    name: str,
    *,
    card_type: int = 0,
    hp: int = 0,
    energy_type: int = 0,
    retreat: int = 0,
    attacks: tuple[int, ...] = (),
    weakness: int | None = None,
    ex: bool = False,
    mega: bool = False,
    stage1: bool = False,
    evolves_from: str | None = None,
    skills: tuple[SkillMetadata, ...] = (),
) -> CardMetadata:
    return CardMetadata(
        card_id=card_id,
        name=name,
        card_type=card_type,
        retreat_cost=retreat,
        hp=hp,
        weakness=weakness,
        resistance=None,
        energy_type=energy_type,
        basic=card_type == 0 and not stage1,
        stage1=stage1,
        stage2=False,
        ex=ex,
        mega_ex=mega,
        tera=False,
        ace_spec=False,
        evolves_from=evolves_from,
        skills=skills,
        attack_ids=attacks,
    )


def _pokemon(
    card_id: int,
    *,
    hp: int | None = None,
    max_hp: int | None = None,
    energies: tuple[int, ...] = (),
    serial: int | None = None,
) -> PokemonRecord:
    catalog = {card.card_id: card for card in synthetic_catalog().cards}
    printed_hp = catalog[card_id].hp
    return PokemonRecord(
        card_id=card_id,
        serial=card_id if serial is None else serial,
        hp=printed_hp if hp is None else hp,
        max_hp=printed_hp if max_hp is None else max_hp,
        appear_this_turn=False,
        energies=energies,
        energy_cards=(),
        tools=(),
        pre_evolution=(),
    )


def _player(
    active: PokemonRecord,
    *,
    bench: tuple[PokemonRecord, ...] = (),
    prizes: int = 6,
    deck: int = 30,
    hand: tuple[int, ...] = (),
) -> PlayerRecord:
    cards = tuple(CardRecord(card_id=card_id, serial=10_000 + index, player_index=0) for index, card_id in enumerate(hand))
    return PlayerRecord(
        active=(active,),
        bench=bench,
        bench_max=5,
        deck_count=deck,
        discard=(),
        prize=tuple(None for _ in range(prizes)),
        hand_count=len(cards),
        hand=cards,
        poisoned=False,
        burned=False,
        asleep=False,
        paralyzed=False,
        confused=False,
    )


def _observation(player0: PlayerRecord, player1: PlayerRecord, *, result: int = -1) -> PublicObservationRecord:
    state = StateRecord(
        turn=4,
        turn_action_count=1,
        acting_player=0,
        first_player=0,
        supporter_played=False,
        stadium_played=False,
        energy_attached=False,
        retreated=False,
        result=result,
        stadium=(),
        looking=None,
        players=(player0, player1),
    )
    return PublicObservationRecord(schema_version=1, selection=None, logs=(), state=state)
