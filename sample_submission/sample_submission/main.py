import os

from cg.api import (
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
    """Read deck.csv.

    Returns:
        list[int]: A list of card IDs in the deck.
    """
    file_path = "deck.csv"
    if not os.path.exists(file_path):
        file_path = "/kaggle_simulations/agent/" + file_path
    with open(file_path, "r") as file:
        csv = file.read().split("\n")
    deck = []
    for i in range(60):
        deck.append(int(csv[i]))
    return deck


def _group_by_type(options):
    by_type = {}
    for i, opt in enumerate(options):
        by_type.setdefault(opt.type, []).append(i)
    return by_type


def _best_attack_index(options, indices):
    """Index (into options) of the highest-damage attack among the given option indices."""
    attacks = _attack_data()
    best_i, best_dmg = indices[0], -1
    for i in indices:
        atk = attacks.get(options[i].attackId)
        dmg = atk.damage if atk else 0
        if dmg > best_dmg:
            best_i, best_dmg = i, dmg
    return best_i, best_dmg


def _choose_main(obs: Observation) -> list[int]:
    """Greedy priority: lethal attack > evolve > attach energy > play basics > ability
    > best attack > retreat if dying > end turn."""
    sel = obs.select
    state = obs.current
    assert sel is not None and state is not None
    options = sel.option
    me = state.players[state.yourIndex]
    opp = state.players[1 - state.yourIndex]
    opp_active = opp.active[0] if opp.active else None
    by_type = _group_by_type(options)

    # 1. Attack for lethal (engine only lists attacks we have Energy for).
    if OptionType.ATTACK in by_type and opp_active is not None:
        idx, dmg = _best_attack_index(options, by_type[OptionType.ATTACK])
        if dmg >= opp_active.hp:
            return [idx]

    # 2. Evolve — free stat upgrade, no downside.
    if OptionType.EVOLVE in by_type:
        return [by_type[OptionType.EVOLVE][0]]

    # 3. Attach Energy if we haven't this turn.
    if OptionType.ATTACH in by_type and not state.energyAttached:
        return [by_type[OptionType.ATTACH][0]]

    # 4. Develop the board: play Basics to Bench while there's room.
    if OptionType.PLAY in by_type and len(me.bench) < me.benchMax:
        return [by_type[OptionType.PLAY][0]]

    # 5. Use an Ability if one is available.
    if OptionType.ABILITY in by_type:
        return [by_type[OptionType.ABILITY][0]]

    # 6. Attack anyway with the strongest available attack.
    if OptionType.ATTACK in by_type:
        idx, _ = _best_attack_index(options, by_type[OptionType.ATTACK])
        return [idx]

    # 7. Retreat only if Active is low and a stronger Benched Pokémon exists.
    if OptionType.RETREAT in by_type:
        my_active = me.active[0] if me.active else None
        if my_active is not None and me.bench:
            low_hp = my_active.hp <= my_active.maxHp * 0.3
            stronger_bench = any(b.hp > my_active.hp for b in me.bench)
            if low_hp and stronger_bench:
                return [by_type[OptionType.RETREAT][0]]

    # 8. Nothing useful left to do.
    if OptionType.END in by_type:
        return [by_type[OptionType.END][0]]

    return [0]


def _choose_attack(obs: Observation) -> list[int]:
    sel = obs.select
    assert sel is not None
    idx, _ = _best_attack_index(sel.option, list(range(len(sel.option))))
    return [idx]


def _choose_evolve(obs: Observation) -> list[int]:
    """Prefer evolving into whichever option has the highest HP."""
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
    """Rank card choices by HP: strongest first for board-building contexts,
    weakest first when discarding/returning cards."""
    sel = obs.select
    assert sel is not None
    options = sel.option
    cards = _card_data()

    def hp_of(opt):
        card = cards.get(opt.cardId) if opt.cardId is not None else None
        return card.hp if card else 0

    weakest_first_contexts = (
        SelectContext.DISCARD,
        SelectContext.TO_DECK,
        SelectContext.TO_DECK_BOTTOM,
        SelectContext.DISCARD_CARD_OR_ATTACHED_CARD,
    )
    reverse = sel.context not in weakest_first_contexts
    ranked = sorted(range(len(options)), key=lambda i: hp_of(options[i]), reverse=reverse)
    return ranked[: sel.maxCount] if sel.maxCount > 0 else []


def _choose_yes_no(obs: Observation) -> list[int]:
    """Default optimistic: take the beneficial-sounding option when offered."""
    sel = obs.select
    assert sel is not None
    for i, opt in enumerate(sel.option):
        if opt.type == OptionType.YES:
            return [i]
    return [0]


def _choose_count(obs: Observation) -> list[int]:
    """Each option represents a candidate count; pick the option with the highest number."""
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
    """Enforce minCount <= len <= maxCount, no duplicates, valid range."""
    idx_list = [i for i in dict.fromkeys(idx_list) if 0 <= i < n_options]
    if len(idx_list) > sel.maxCount:
        idx_list = idx_list[: sel.maxCount]
    if len(idx_list) < sel.minCount:
        remaining = [i for i in range(n_options) if i not in idx_list]
        idx_list += remaining[: sel.minCount - len(idx_list)]
    return idx_list


def agent(obs_dict: dict) -> list[int]:
    """Greedy heuristic Pokémon TCG agent (no lookahead / no ML — v1 baseline).

    Returns:
        list[int]: A list of option index.
    """
    obs: Observation = to_observation_class(obs_dict)
    if obs.select is None:
        # Initial deck selection.
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
        # ENERGY, SKILL, SPECIAL_CONDITION, and any future types: safe minimal default.
        idx_list = list(range(sel.minCount))

    return _clamp(idx_list, sel, len(options))
