from pathlib import Path

from cg.api import (
    AreaType,
    CardType,
    EnergyType,
    Observation,
    OptionType,
    SelectContext,
    SelectType,
    all_attack,
    all_card_data,
    search_begin,
    search_end,
    search_step,
    to_observation_class,
)

_CARD_DATA = None
_ATTACK_DATA = None
_MY_DECK = None

# MAIN-phase 1-ply lookahead config.
SEARCH_MAIN = True          # MAIN-phase 1-ply lookahead. MEASURED (Hydrapple deck,
                            # vs frozen greedy): lookahead 64.6% [60.3-68.7] n=500 vs
                            # greedy control 49.0% [43.4-54.6] n=300 => +15.6pts.
                            # NOTE: the gain is from lookahead itself and is
                            # DECK-DEPENDENT (it measured 45% on the old Water deck).
                            # The _eval_state v2 terms are within noise -- see
                            # eval_ablation.py and PROGRESS.md 2026-08-04.
MAX_ROLLOUT_STEPS = 40      # cap greedy rollout length inside a forked turn
WIN_SCORE = 1e9

ABILITY_CAP_PER_TURN = 4    # see _ability_cap_reached: guards against unbounded Abilities
_live_ability_count: dict = {}
_last_seen_turn = -1


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


# Last-resort copy of deck.csv, kept in sync by _assert_embedded_deck_matches()
# (run by check_embedded_deck.py). Every path-based lookup below can fail on
# Kaggle, and when it does the agent has no deck at all -- see read_deck_csv.
_EMBEDDED_DECK = [
    96, 96, 96, 96, 708, 708, 709, 709, 710, 710, 42, 42, 93, 93, 150, 150,
    920, 655, 1071, 140, 251, 1227, 1227, 1227, 1227, 1182, 1182, 1182,
    1188, 1184, 1201, 1231, 1094, 1094, 1094, 1094, 1097, 1097, 1152, 1152,
    1121, 1121, 1080, 1213, 1261, 1261, 1261, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1,
]


def read_deck_csv() -> list[int]:
    """Read deck.csv, falling back to the embedded deck if it can't be found.

    Returns:
        list[int]: A list of card IDs in the deck.
    """
    # Kaggle runs this file via exec() of its source, so `__file__` is NOT
    # defined there (it crashed submissions #55335664/#55351154 with NameError).
    #
    # Bug found 2026-08-15: the __file__-less fallbacks were ALSO wrong. Kaggle
    # puts the agent directory on sys.path (so `import cg` works) but does NOT
    # chdir into it, and the tree is not at /kaggle_simulations/agent/ anymore
    # (kaggle_environments 1.32.7). So all three candidates missed, open() raised
    # FileNotFoundError, agent()'s except-handler swallowed it and returned [],
    # and validation rejected the episode with "Player 1's deck does not have 60
    # cards" -- with an empty stderr, because nothing ever propagated. That took
    # down #55521916, #55522008 and #55522139. Reproduced locally by exec()ing
    # this source with no __file__ from an unrelated CWD.
    #
    # Reading the file must stay PRIMARY: the sub-agent specialists and the
    # matchup harnesses bind different decks by writing their own deck.csv next
    # to a copy of this agent. The embedded list is only the last resort.
    candidates = []
    module_file = globals().get("__file__")
    if module_file:
        candidates.append(Path(module_file).with_name("deck.csv"))
    # cg imports fine on Kaggle, so its package anchors the real agent directory
    # even when __file__ is undefined and the CWD points elsewhere.
    try:
        import cg

        cg_file = getattr(cg, "__file__", None)
        if cg_file:
            candidates.append(Path(cg_file).resolve().parent.parent / "deck.csv")
    except Exception:
        pass
    candidates.append(Path("/kaggle_simulations/agent/deck.csv"))
    candidates.append(Path("deck.csv"))
    for path in candidates:
        try:
            if not path.exists():
                continue
            with open(path, "r", encoding="utf-8") as file:
                rows = [line.strip() for line in file if line.strip()]
            if len(rows) >= 60:
                return [int(card_id) for card_id in rows[:60]]
        except Exception:
            continue  # unreadable/malformed candidate: try the next one
    return list(_EMBEDDED_DECK)


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


def _option_pokemon(opt, state):
    if opt.playerIndex is None or opt.area is None or opt.index is None:
        return None
    if opt.playerIndex < 0 or opt.playerIndex >= len(state.players):
        return None
    player = state.players[opt.playerIndex]
    if opt.area == AreaType.ACTIVE:
        return player.active[0] if player.active and player.active[0] is not None else None
    if opt.area == AreaType.BENCH and opt.index < len(player.bench):
        return player.bench[opt.index]
    return None


def _target_score(opt, obs):
    """Score a target using live board state first, static card data as fallback."""
    state = obs.current
    if state is None:
        return _option_card_power(opt)

    pokemon = _option_pokemon(opt, state)
    if pokemon is None:
        return _option_card_power(opt)

    card = _card_data().get(pokemon.id)
    prize_value = 3 if card and card.megaEx else 2 if card and card.ex else 1
    damage_taken = max(0, pokemon.maxHp - pokemon.hp)
    static_threat = _card_power(pokemon.id)

    lethal_damage = None
    sel = obs.select
    assert sel is not None
    if sel.context in (SelectContext.DAMAGE_COUNTER, SelectContext.DAMAGE_COUNTER_ANY):
        lethal_damage = sel.remainDamageCounter * 10
    lethal_bonus = 100000 * prize_value if lethal_damage is not None and pokemon.hp <= lethal_damage else 0
    active_bonus = 5000 if opt.area == AreaType.ACTIVE else 0

    if sel.context == SelectContext.DAMAGE:
        near_ko_bonus = 6000 + (10 - pokemon.hp) * 200 if pokemon.hp <= 10 else 0
        live_pressure = near_ko_bonus + damage_taken * 2
    else:
        live_pressure = damage_taken * 20 - pokemon.hp * 10
    return lethal_bonus + active_bonus + live_pressure + static_threat + prize_value * 1000


def _best_attach_index(options, indices, me):
    """Prefer powering the Active, then the strongest Bench target."""
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
    """Rank playable Basic Pokemon by likely board value."""
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


def _live_attacker_score(mon, opp_active=None) -> int:
    """Score an in-play Pokemon as an immediate Active attacker."""
    if mon is None:
        return -10**9
    dmg = _best_usable_damage(mon)
    lethal_bonus = 3000 if opp_active is not None and dmg >= opp_active.hp else 0
    prize_penalty = 120 * _prize_value(mon)
    return lethal_bonus + dmg * 20 + mon.hp + len(mon.energies) * 15 - prize_penalty


def _ability_cap_reached(state) -> bool:
    """Read-only: has this seat already used ABILITY the max allowed times on
    the CURRENT real turn? Shared by the greedy ladder and the search
    candidate list so a rollout preview sees the same constraint the live
    game actually faces. Never increments -- see _record_ability_use, the
    only writer, called once by _agent_impl on the actually-applied action.

    Bug found 2026-08-11: some Abilities are legal to use "as often as you
    like" during a turn (e.g. Mega Venusaur ex's Solar Transfer, Azumarill ex's
    Bubble Gathering, Dewgong's Wash Out -- all move Energy between your own
    in-play Pokemon at zero net cost, so nothing ever runs out). The eval's
    Active-quality term (`energies * 5`) rewards hoarding Energy with no
    penalty for never attacking, so once such a card is in the deck,
    `_search_choose_main` finds "use Ability again" scores higher than
    "attack" on literally every turn and re-picks it forever -- confirmed via
    direct trace, stuck cycling ENERGY -> CARD -> ABILITY on one turn for
    1500+ steps until the harness step cap cut it off (~35% of a 20-game
    sample never finished). An earlier version of this fix only capped the
    ladder inside `_choose_main`, which gates the ROLLOUT TAIL but not
    `_search_choose_main`'s own top-level candidate choice -- that path
    bypasses `_choose_main` entirely, so the loop persisted unchanged. This
    version gates the actual decision point instead.
    """
    global _last_seen_turn
    if state is None:
        return False
    turn = state.turn
    if turn < _last_seen_turn:
        _live_ability_count.clear()  # new game started; turn numbers restarted
    _last_seen_turn = turn
    return _live_ability_count.get((turn, state.yourIndex), 0) >= ABILITY_CAP_PER_TURN


def _record_ability_use(state) -> None:
    """Record a real, applied ABILITY choice against the per-turn cap. Call
    only from _agent_impl on the final chosen action -- never from inside a
    search rollout, or hypothetical deliberation would falsely eat into the
    real turn's budget before the live game has taken a single action."""
    if state is None:
        return
    key = (state.turn, state.yourIndex)
    _live_ability_count[key] = _live_ability_count.get(key, 0) + 1


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
        return [_best_card_option(options, by_type[OptionType.EVOLVE])]

    # 3. Attach Energy if we haven't this turn.
    if OptionType.ATTACH in by_type and not state.energyAttached:
        return [_best_attach_index(options, by_type[OptionType.ATTACH], me)]

    # 4. Develop the board: play the strongest Basic to Bench while there's room.
    if OptionType.PLAY in by_type and len(me.bench) < me.benchMax:
        play_idx = _best_play_index(options, by_type[OptionType.PLAY], me)
        if play_idx is not None:
            return [play_idx]

    # 5. Use an Ability if one is available (capped per real turn, see
    # _ability_cap_reached).
    if OptionType.ABILITY in by_type and not _ability_cap_reached(state):
        return [by_type[OptionType.ABILITY][0]]

    # 6. Attack anyway with the strongest available attack.
    if OptionType.ATTACK in by_type:
        idx, _ = _best_attack_index(options, by_type[OptionType.ATTACK])
        return [idx]

    # 7. Retreat only if the Active is dying and a stronger Benched Pokémon exists.
    # ponytail: deliberately the simple pre-2026-08-08 rule. A tactical
    # "retreat to a better attacker" gate was built and ABLATED to exactly zero
    # (retreat_ablation.py: card_off 62.4% vs neither 62.8%, n=500/arm) — attacker
    # choice is decided at forced promotion after a KO, not by voluntary retreat.
    # Don't reintroduce a retreat heuristic without measuring it in isolation.
    if OptionType.RETREAT in by_type:
        my_active = me.active[0] if me.active else None
        if my_active is not None and me.bench:
            low_hp = my_active.hp <= my_active.maxHp * 0.3
            if low_hp and any(b.hp > my_active.hp for b in me.bench):
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
    """Prefer evolving into the strongest resulting card."""
    sel = obs.select
    assert sel is not None
    return [_best_card_option(sel.option, list(range(len(sel.option))))]


def _choose_card(obs: Observation) -> list[int]:
    """Rank card choices by HP: strongest first for board-building contexts,
    weakest first when discarding/returning cards."""
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
    )
    indices = list(range(len(options)))
    if sel.context in opponent_target_contexts:
        opponent_indices = [i for i, opt in enumerate(options) if opt.playerIndex is not None and obs.current is not None and opt.playerIndex != obs.current.yourIndex]
        if opponent_indices:
            indices = opponent_indices

    if sel.context in opponent_target_contexts:
        ranked = sorted(indices, key=lambda i: _target_score(options[i], obs), reverse=True)
    else:
        reverse = sel.context not in weakest_first_contexts
        own_board_indices = []
        if reverse and obs.current is not None:
            own_board_indices = [
                i for i, opt in enumerate(options)
                if opt.playerIndex == obs.current.yourIndex
                and opt.area in (AreaType.ACTIVE, AreaType.BENCH)
                and _option_pokemon(opt, obs.current) is not None
            ]
        if own_board_indices:
            opp = obs.current.players[1 - obs.current.yourIndex]
            opp_active = opp.active[0] if opp.active else None
            ranked = sorted(
                indices,
                key=lambda i: _live_attacker_score(_option_pokemon(options[i], obs.current), opp_active),
                reverse=True,
            )
        else:
            ranked = sorted(indices, key=lambda i: _option_card_power(options[i]), reverse=reverse)
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


class _EnergyView:
    """Minimal stand-in for a Pokemon with a hypothetical Energy set.

    _best_usable_damage only reads `.id` and `.energies`, so this is enough to ask
    "could this Pokemon still attack if that Energy left?" without touching live state.
    """

    __slots__ = ("id", "energies")

    def __init__(self, card_id, energies):
        self.id = card_id
        self.energies = energies


def _energy_source_score(opt, me) -> int:
    """Rank one SWITCH_ENERGY / DISCARD_ENERGY source Energy: higher = more expendable.

    This context was previously answered by the blind `range(minCount)` default in
    _greedy_select, which on this deck means every Solar Transfer and Energy Switch
    source -- 44 selections per 10 games, with Solar Transfer firing 3.6 times a game --
    was picked arbitrarily. The whole point of the deck's energy engine is to move Energy
    ONTO the attacker, so taking it off the attacker is the one outcome that must not
    happen by accident.

    `opt.count` is documented as the number of Energy UNITS the option corresponds to,
    which already accounts for Meganium's Wild Growth doubling a Basic {G}.
    """
    mon = None
    if opt.area == AreaType.ACTIVE:
        mon = me.active[0] if me.active and me.active[0] is not None else None
    elif opt.area == AreaType.BENCH and opt.index is not None and opt.index < len(me.bench):
        mon = me.bench[opt.index]
    if mon is None:
        return 0

    is_active = opt.area == AreaType.ACTIVE
    units = opt.count if getattr(opt, "count", None) else 1
    before = _best_usable_damage(mon)

    # What this Pokemon could still do without the Energy being taken.
    remaining = list(mon.energies)
    drop = mon.energies[opt.energyIndex] if (
        opt.energyIndex is not None and opt.energyIndex < len(mon.energies)
    ) else None
    for _ in range(units):
        if drop is not None and drop in remaining:
            remaining.remove(drop)
        elif remaining:
            remaining.pop()
    after = _best_usable_damage(_EnergyView(mon.id, remaining))

    score = len(mon.energies) * 10          # a bigger pile has more to spare
    if not is_active:
        score += 300                        # Bench Energy is idle by default
    if before <= 0:
        score += 200                        # this Pokemon cannot attack either way
    if before > 0 and after <= 0:
        score -= 400                        # taking this disarms a ready attacker
    if is_active and before > 0:
        score -= 600                        # never disarm the Active
    return score


def _choose_energy(obs: Observation) -> list[int]:
    """Pick which attached Energy to move/discard, most expendable first."""
    sel = obs.select
    assert sel is not None
    state = obs.current
    if state is None:
        return list(range(sel.minCount))
    me = state.players[state.yourIndex]
    ranked = sorted(
        range(len(sel.option)),
        key=lambda i: _energy_source_score(sel.option[i], me),
        reverse=True,
    )
    return ranked[: max(sel.minCount, 1)]


def _clamp(idx_list, sel, n_options):
    """Enforce minCount <= len <= maxCount, no duplicates, valid range."""
    idx_list = [i for i in dict.fromkeys(idx_list) if 0 <= i < n_options]
    if len(idx_list) > sel.maxCount:
        idx_list = idx_list[: sel.maxCount]
    if len(idx_list) < sel.minCount:
        remaining = [i for i in range(n_options) if i not in idx_list]
        idx_list += remaining[: sel.minCount - len(idx_list)]
    return idx_list


def _greedy_select(obs: Observation) -> list[int]:
    """Pure greedy policy over one Observation. Used both as the agent's default
    and as the rollout policy inside lookahead (never recurses into search)."""
    sel = obs.select
    assert sel is not None
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
    elif sel.type == SelectType.ENERGY:
        idx_list = _choose_energy(obs)
    else:
        # SKILL, SPECIAL_CONDITION, and any future types: safe minimal default.
        idx_list = list(range(sel.minCount))

    return _clamp(idx_list, sel, len(options))


def _my_deck_ids() -> list[int]:
    global _MY_DECK
    if _MY_DECK is None:
        try:
            _MY_DECK = read_deck_csv()
        except Exception:
            _MY_DECK = []
    return _MY_DECK


def _can_pay(cost, have) -> bool:
    """Approximate attack-cost check: each typed symbol needs a matching attached
    Energy (RAINBOW counts as any type); Colorless symbols take whatever is left."""
    pool = list(have)
    colorless = 0
    for c in cost:
        if c == EnergyType.COLORLESS:
            colorless += 1
            continue
        for i, e in enumerate(pool):
            if e == c or e == EnergyType.RAINBOW:
                pool.pop(i)
                break
        else:
            return False
    return len(pool) >= colorless


def _best_usable_damage(mon) -> int:
    """Highest damage this Pokémon can actually deal right now (cost affordable)."""
    if mon is None:
        return 0
    card = _card_data().get(mon.id)
    if card is None:
        return 0
    attacks = _attack_data()
    best = 0
    for aid in card.attacks:
        a = attacks.get(aid)
        if a is not None and _can_pay(a.energies, mon.energies):
            best = max(best, a.damage)
    return best


def _prize_value(mon) -> int:
    """Prizes the opponent takes if this Pokémon is Knocked Out."""
    card = _card_data().get(mon.id) if mon is not None else None
    if card is None:
        return 1
    return 3 if card.megaEx else 2 if card.ex else 1


def _eval_state(state, my_index: int) -> float:
    """Score a board from my_index's perspective.

    Terms, in rough priority: prizes (the win condition), board HP (material),
    Active attacker quality (is the RIGHT Pokémon in the Active slot, powered up),
    and opponent KO-back risk (does this line leave my Active dying next turn,
    weighted by the prizes that KO would concede)."""
    if state is None:
        return 0.0
    if state.result != -1:
        if state.result == my_index:
            return WIN_SCORE
        if state.result == 1 - my_index:
            return -WIN_SCORE
        return 0.0  # draw

    me = state.players[my_index]
    opp = state.players[1 - my_index]

    def total_hp(p):
        mons = ([p.active[0]] if p.active and p.active[0] else []) + list(p.bench)
        return sum(m.hp for m in mons)

    # Fewer of MY prizes remaining = I've taken more = closer to winning.
    prize = (len(opp.prize) - len(me.prize)) * 1000
    hp_diff = total_hp(me) - total_hp(opp)

    my_active = me.active[0] if me.active else None
    opp_active = opp.active[0] if opp.active else None

    # Reward having a real, powered attacker Active (not a 40HP intermediate).
    active_quality = 0
    if my_active is not None:
        active_quality = _best_usable_damage(my_active) * 2 + len(my_active.energies) * 5

    # Penalize lines that leave my Active KO-able on the opponent's next turn,
    # scaled by how many Prize cards that KO would hand them.
    ko_risk = 0
    if my_active is not None and opp_active is not None:
        if _best_usable_damage(opp_active) >= my_active.hp:
            ko_risk = -300 * _prize_value(my_active)

    # Board development. The four terms above model prizes, material, the Active's
    # attacker quality and KO risk -- and nothing else. A rollout that dumps the entire
    # hand to develop nothing scores identically to one that builds a board, because
    # bench depth, evolution progress and cards still available are all invisible.
    # This deck cares about all three: it needs Meganium in play for Wild Growth, needs
    # its Stage 2 line assembled, and needs resources left to rebuild after a knockout.
    cards = _card_data()
    development = 0
    for mon in ([my_active] if my_active is not None else []) + list(me.bench):
        card = cards.get(mon.id)
        if card is None:
            continue
        if card.stage2:
            development += 40
        elif card.stage1:
            development += 20
        if mon.id == 710:          # Meganium: Wild Growth halves every attack cost
            development += 80
    development += len(me.bench) * 12
    # Resources left. Weighted low so it never outweighs a prize (1000) or real damage.
    resources = (me.handCount + me.deckCount // 4) * 3

    return prize + hp_diff + active_quality + ko_risk + development + resources


def _predictions(obs: Observation, my_deck: list[int], opp_deck: list[int]) -> dict:
    """Hidden-info args for search_begin. For a within-my-turn rollout the opponent
    never acts, so a mirror-deck fill is sufficient; counts must match observed."""
    st = obs.current
    assert st is not None
    yi = st.yourIndex
    me, opp = st.players[yi], st.players[1 - yi]

    def take(ids, n):
        if n <= 0:
            return []
        pool = ids or my_deck or [0]
        return [pool[i % len(pool)] for i in range(n)]

    return {
        "your_deck": take(my_deck, me.deckCount),
        "your_prize": take(my_deck, len(me.prize)),
        "opponent_deck": take(opp_deck, opp.deckCount),
        "opponent_prize": take(opp_deck, len(opp.prize)),
        "opponent_hand": take(opp_deck, opp.handCount),
        "opponent_active": [],
    }


def _rollout_score(first_select, obs: Observation, my_index: int,
                   my_deck: list[int], opp_deck: list[int]) -> float:
    """Fork the real state, apply first_select, then play out the REST of my turn
    greedily; return the end-of-turn board eval (or terminal win/loss)."""
    p = _predictions(obs, my_deck, opp_deck)
    ss = search_begin(obs, p["your_deck"], p["your_prize"], p["opponent_deck"],
                      p["opponent_prize"], p["opponent_hand"], p["opponent_active"])
    start_turn = obs.current.turn if obs.current else 0
    try:
        ss = search_step(ss.searchId, first_select)
        for _ in range(MAX_ROLLOUT_STEPS):
            o = ss.observation
            cur, s = o.current, o.select
            if cur is not None and cur.result != -1:
                return _eval_state(cur, my_index)
            if cur is not None and cur.turn != start_turn:
                break  # my turn ended
            if s is None:
                break
            ss = search_step(ss.searchId, _greedy_select(o))
        return _eval_state(ss.observation.current, my_index)
    finally:
        search_end()


def _search_choose_main(obs: Observation):
    """1-ply lookahead over MAIN options: pick the action whose greedy continuation
    yields the best end-of-turn board. Returns None to signal 'fall back to greedy'."""
    sel = obs.select
    if sel is None or obs.current is None:
        return None
    my_deck = _my_deck_ids()
    if not my_deck:
        return None
    my_index = obs.current.yourIndex
    opp_deck = my_deck  # mirror opponent (irrelevant during my own turn)
    ability_capped = _ability_cap_reached(obs.current)

    try:
        best_i, best_score = None, float("-inf")
        for i in range(len(sel.option)):
            if ability_capped and sel.option[i].type == OptionType.ABILITY:
                continue  # per-turn cap already used; don't let search re-pick it
            choice = _clamp([i], sel, len(sel.option))
            score = _rollout_score(choice, obs, my_index, my_deck, opp_deck)
            if score > best_score:
                best_score, best_i = score, i
    except Exception:
        return None  # any search failure => greedy fallback
    if best_i is None:
        return None
    return _clamp([best_i], sel, len(sel.option))


def _agent_impl(obs_dict: dict) -> list[int]:
    """Pokémon TCG agent: MAIN-phase 1-ply lookahead (greedy rollout) with a greedy
    fallback for all other decisions and on any search failure.

    Returns:
        list[int]: A list of option index.
    """
    obs: Observation = to_observation_class(obs_dict)
    if obs.select is None:
        # Initial deck selection.
        return read_deck_csv()
    if not obs.select.option:
        return []

    if SEARCH_MAIN and obs.select.type == SelectType.MAIN and obs.current is not None:
        chosen = _search_choose_main(obs)
        if chosen is not None:
            _record_if_ability(obs, chosen)
            return chosen

    chosen = _greedy_select(obs)
    if obs.select.type == SelectType.MAIN:
        _record_if_ability(obs, chosen)
    return chosen


def _record_if_ability(obs: Observation, chosen: list[int]) -> None:
    """If the action actually being returned to the engine is ABILITY, count
    it against the per-turn cap (see _record_ability_use)."""
    if not chosen or obs.current is None:
        return
    i = chosen[0]
    options = obs.select.option if obs.select else []
    if 0 <= i < len(options) and options[i].type == OptionType.ABILITY:
        _record_ability_use(obs.current)


# ---------------------------------------------------------------------------
# KEEP `agent` LAST IN THIS FILE. Kaggle's runner (kaggle_environments'
# get_last_callable) takes the LAST callable defined in the module as the
# entry point -- the submit dialog states it as "a python file with the last
# 'def' accepting an observation and returning an action".
#
# Bug found 2026-08-15: commit 569ca1d appended `_record_if_ability(obs,
# chosen)` after `_agent_impl`, so the LAST def became a 2-arg helper that
# returns None. Kaggle called it as the agent, got no action, and rejected
# every episode with "Player 1's deck does not have 60 cards" (#55521916,
# #55522008, #55522139, #55522XXX) -- while the identical agent scored 435.2
# seven days earlier, when `_agent_impl` was still last. Nothing about the
# deck or the deck-loading code was wrong; the entry point had been stolen.
#
# check_embedded_deck.py asserts this ordering. Add new helpers ABOVE here.
# ---------------------------------------------------------------------------
def agent(obs_dict: dict) -> list[int]:
    """Pokémon TCG agent entry point. Delegates to `_agent_impl`; on ANY unexpected
    exception there (e.g. the native cg engine failing to load on an unfamiliar
    host) falls back to a minimal, cg.api-free legal selection instead of
    forfeiting the match outright.

    Returns:
        list[int]: A list of option index.
    """
    try:
        return _agent_impl(obs_dict)
    except Exception:
        sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
        if sel is None:
            try:
                return read_deck_csv()
            except Exception:
                return []
        options = sel.get("option") or []
        min_count = sel.get("minCount", 0) or 0
        return list(range(min(min_count, len(options))))
