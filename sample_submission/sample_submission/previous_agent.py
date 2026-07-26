"""Frozen baseline agent for self-play benchmark comparisons.

This is the policy state before the live-HP targeting pass. Keep this file stable
unless intentionally refreshing the benchmark baseline.
"""
from pathlib import Path

from cg.api import (
    AreaType,
    CardType,
    Observation,
    OptionType,
    SelectContext,
    SelectType,
    all_attack,
    all_card_data,
    to_observation_class,
)

_CARD_DATA = None
_ATTACK_DATA = None


def _card_data():
    global _CARD_DATA
    if _CARD_DATA is None:
        _CARD_DATA = {c.cardId: c for c in all_card_data()}
    return _CARD_DATA


def _attack_data():
    global _ATTACK_DATA
    if _ATTACK_DATA is None:
        _ATTACK_DATA = {a.attackId: a for a in all_attack()}
    return _ATTACK_DATA


def read_deck_csv() -> list[int]:
    local_path = Path(__file__).with_name("deck.csv")
    kaggle_path = Path("/kaggle_simulations/agent/deck.csv")
    file_path = local_path if local_path.exists() else kaggle_path
    with open(file_path, "r", encoding="utf-8") as file:
        rows = [line.strip() for line in file if line.strip()]
    if len(rows) < 60:
        raise ValueError(f"deck.csv must contain at least 60 card IDs, found {len(rows)}.")
    return [int(card_id) for card_id in rows[:60]]


def _group_by_type(options):
    by_type = {}
    for i, opt in enumerate(options):
        by_type.setdefault(opt.type, []).append(i)
    return by_type


def _best_attack_index(options, indices):
    attacks = _attack_data()
    best_i, best_dmg = indices[0], -1
    for i in indices:
        atk = attacks.get(options[i].attackId)
        dmg = atk.damage if atk else 0
        if dmg > best_dmg:
            best_i, best_dmg = i, dmg
    return best_i, best_dmg


def _card_power(card_id):
    cards = _card_data()
    attacks = _attack_data()
    card = cards.get(card_id)
    if card is None:
        return 0
    best_damage = max((attacks[a].damage for a in card.attacks if a in attacks), default=0)
    stage_bonus = 60 if card.stage2 else 30 if card.stage1 else 0
    return card.hp + best_damage * 2 + stage_bonus


def _option_card_power(opt):
    return _card_power(opt.cardId) if opt.cardId is not None else 0


def _best_card_option(options, indices, reverse=True):
    return sorted(indices, key=lambda i: _option_card_power(options[i]), reverse=reverse)[0]


def _best_attach_index(options, indices, me):
    best_i, best_score = indices[0], -1
    for i in indices:
        opt = options[i]
        score = 0
        if opt.inPlayArea == AreaType.ACTIVE:
            target = me.active[0] if me.active else None
            score = 10000 + (target.maxHp + target.hp if target else 0)
        elif opt.inPlayArea == AreaType.BENCH and opt.inPlayIndex is not None and opt.inPlayIndex < len(me.bench):
            target = me.bench[opt.inPlayIndex]
            score = target.maxHp + target.hp
        if score > best_score:
            best_i, best_score = i, score
    return best_i


def _best_play_index(options, indices, me):
    cards = _card_data()
    best_i, best_score = indices[0], -1
    for i in indices:
        card = cards.get(options[i].cardId)
        score = 0
        if card is not None and card.cardType == CardType.POKEMON:
            if card.basic and len(me.bench) < me.benchMax:
                score = 5000 + _card_power(card.cardId)
            else:
                score = -1
        if score > best_score:
            best_i, best_score = i, score
    return best_i if best_score >= 0 else None


def _choose_main(obs: Observation) -> list[int]:
    sel = obs.select
    state = obs.current
    assert sel is not None and state is not None
    options = sel.option
    me = state.players[state.yourIndex]
    opp = state.players[1 - state.yourIndex]
    opp_active = opp.active[0] if opp.active else None
    by_type = _group_by_type(options)

    if OptionType.ATTACK in by_type and opp_active is not None:
        idx, dmg = _best_attack_index(options, by_type[OptionType.ATTACK])
        if dmg >= opp_active.hp:
            return [idx]

    if OptionType.EVOLVE in by_type:
        return [_best_card_option(options, by_type[OptionType.EVOLVE])]

    if OptionType.ATTACH in by_type and not state.energyAttached:
        return [_best_attach_index(options, by_type[OptionType.ATTACH], me)]

    if OptionType.PLAY in by_type and len(me.bench) < me.benchMax:
        play_idx = _best_play_index(options, by_type[OptionType.PLAY], me)
        if play_idx is not None:
            return [play_idx]

    if OptionType.ABILITY in by_type:
        return [by_type[OptionType.ABILITY][0]]

    if OptionType.ATTACK in by_type:
        idx, _ = _best_attack_index(options, by_type[OptionType.ATTACK])
        return [idx]

    if OptionType.RETREAT in by_type:
        my_active = me.active[0] if me.active else None
        if my_active is not None and me.bench:
            low_hp = my_active.hp <= my_active.maxHp * 0.3
            stronger_bench = any(b.hp > my_active.hp for b in me.bench)
            if low_hp and stronger_bench:
                return [by_type[OptionType.RETREAT][0]]

    if OptionType.END in by_type:
        return [by_type[OptionType.END][0]]

    return [0]


def _choose_attack(obs: Observation) -> list[int]:
    sel = obs.select
    assert sel is not None
    idx, _ = _best_attack_index(sel.option, list(range(len(sel.option))))
    return [idx]


def _choose_evolve(obs: Observation) -> list[int]:
    sel = obs.select
    assert sel is not None
    options = sel.option
    cards = _card_data()
    best_i, best_hp = 0, -1
    for i, opt in enumerate(options):
        card = cards.get(opt.cardId) if opt.cardId is not None else None
        hp = card.hp if card else 0
        if hp > best_hp:
            best_i, best_hp = i, hp
    return [best_i]


def _choose_card(obs: Observation) -> list[int]:
    sel = obs.select
    assert sel is not None
    options = sel.option
    weakest_first_contexts = (
        SelectContext.DISCARD,
        SelectContext.TO_DECK,
        SelectContext.TO_DECK_BOTTOM,
        SelectContext.DISCARD_CARD_OR_ATTACHED_CARD,
        SelectContext.DISCARD_ENERGY_CARD,
        SelectContext.DISCARD_TOOL_CARD,
    )
    opponent_target_contexts = (
        SelectContext.DAMAGE,
        SelectContext.DAMAGE_COUNTER,
        SelectContext.DAMAGE_COUNTER_ANY,
        SelectContext.EFFECT_TARGET,
    )
    indices = list(range(len(options)))
    if sel.context in opponent_target_contexts:
        opponent_indices = [
            i for i, opt in enumerate(options)
            if opt.playerIndex is not None and obs.current is not None and opt.playerIndex != obs.current.yourIndex
        ]
        if opponent_indices:
            indices = opponent_indices

    reverse = sel.context not in weakest_first_contexts
    ranked = sorted(indices, key=lambda i: _option_card_power(options[i]), reverse=reverse)
    return ranked[: sel.maxCount] if sel.maxCount > 0 else []


def _choose_yes_no(obs: Observation) -> list[int]:
    sel = obs.select
    assert sel is not None
    for i, opt in enumerate(sel.option):
        if opt.type == OptionType.YES:
            return [i]
    return [0]


def _choose_count(obs: Observation) -> list[int]:
    sel = obs.select
    assert sel is not None
    options = sel.option
    best_i, best_n = 0, -1
    for i, opt in enumerate(options):
        n = opt.number if opt.number is not None else 0
        if n > best_n:
            best_i, best_n = i, n
    return [best_i]


def _clamp(idx_list, sel, n_options):
    idx_list = [i for i in dict.fromkeys(idx_list) if 0 <= i < n_options]
    if len(idx_list) > sel.maxCount:
        idx_list = idx_list[: sel.maxCount]
    if len(idx_list) < sel.minCount:
        remaining = [i for i in range(n_options) if i not in idx_list]
        idx_list += remaining[: sel.minCount - len(idx_list)]
    return idx_list


def agent(obs_dict: dict) -> list[int]:
    obs: Observation = to_observation_class(obs_dict)
    if obs.select is None:
        return read_deck_csv()

    sel = obs.select
    options = sel.option
    if not options:
        return []

    if sel.type == SelectType.MAIN:
        idx_list = _choose_main(obs)
    elif sel.type == SelectType.ATTACK:
        idx_list = _choose_attack(obs)
    elif sel.type == SelectType.EVOLVE:
        idx_list = _choose_evolve(obs)
    elif sel.type in (SelectType.CARD, SelectType.CARD_OR_ATTACHED_CARD, SelectType.ATTACHED_CARD):
        idx_list = _choose_card(obs)
    elif sel.type == SelectType.YES_NO:
        idx_list = _choose_yes_no(obs)
    elif sel.type == SelectType.COUNT:
        idx_list = _choose_count(obs)
    else:
        idx_list = list(range(sel.minCount))

    return _clamp(idx_list, sel, len(options))
