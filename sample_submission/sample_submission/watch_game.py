"""Step-by-step human-readable replay of one battle.

Prints, for every decision point: whose turn it is, what the acting agent chose,
and the resulting game events (draws, plays, attaches, evolutions, attacks, KOs).

Run from this directory:
    python watch_game.py            # heuristic vs heuristic
    python watch_game.py random     # heuristic (p0) vs random (p1)
    python watch_game.py > game.txt # save the full transcript
"""
import random
import sys

from cg.api import (
    AreaType,
    LogType,
    OptionType,
    SelectContext,
    SelectType,
    to_observation_class,
    all_attack,
    all_card_data,
)
from cg.game import battle_start, battle_select, battle_finish
from main import agent as heuristic_agent, read_deck_csv

_CARDS = {c.cardId: c for c in all_card_data()}
_ATKS = {a.attackId: a for a in all_attack()}

AREA = {a.value: a.name for a in AreaType}
LTYPE = {t.value: t.name for t in LogType}


def cname(cid):
    c = _CARDS.get(cid)
    return c.name if c else f"card#{cid}"


def random_agent(obs_dict):
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return read_deck_csv()
    sel = obs.select
    return random.sample(range(len(sel.option)), sel.maxCount)


def describe_option(opt):
    """One-line English for a chosen Option."""
    t = opt.type
    if t == OptionType.ATTACK:
        atk = _ATKS.get(opt.attackId)
        if atk:
            return f"ATTACK '{atk.name}' ({atk.damage} dmg)"
        return f"ATTACK #{opt.attackId}"
    if t == OptionType.END:
        return "END turn"
    if t == OptionType.RETREAT:
        return "RETREAT active"
    if t == OptionType.PLAY:
        return f"PLAY hand[{opt.index}]"
    if t == OptionType.EVOLVE:
        return f"EVOLVE -> {cname(opt.cardId)} onto {AREA.get(opt.inPlayArea,'?')}[{opt.inPlayIndex}]"
    if t == OptionType.ATTACH:
        what = cname(opt.cardId) if opt.cardId is not None else f"{AREA.get(opt.area,'?')}[{opt.index}]"
        return f"ATTACH {what} -> {AREA.get(opt.inPlayArea,'?')}[{opt.inPlayIndex}]"
    if t == OptionType.ABILITY:
        return f"ABILITY on {AREA.get(opt.area,'?')}[{opt.index}]"
    if t == OptionType.CARD:
        who = cname(opt.cardId) if opt.cardId is not None else f"{AREA.get(opt.area,'?')}[{opt.index}]"
        return f"CARD {who} (p{opt.playerIndex})"
    if t == OptionType.ENERGY:
        return f"ENERGY {cname(opt.cardId)} x{opt.count}"
    if t == OptionType.YES:
        return "YES"
    if t == OptionType.NO:
        return "NO"
    if t == OptionType.NUMBER:
        return f"NUMBER {opt.number}"
    return t.name


def describe_log(lg):
    """One-line English for a game event; returns None for noise we skip."""
    t = lg.get("type")
    p = lg.get("playerIndex")
    tag = f"P{p}" if p is not None else "--"
    if t == LogType.DRAW:
        return f"{tag} draws {cname(lg.get('cardId'))}"
    if t == LogType.PLAY:
        return f"{tag} plays {cname(lg.get('cardId'))}"
    if t == LogType.ATTACH:
        return f"{tag} attaches {cname(lg.get('cardId'))} to {cname(lg.get('cardIdTarget'))}"
    if t == LogType.EVOLVE:
        return f"{tag} evolves {cname(lg.get('cardIdTarget'))} -> {cname(lg.get('cardId'))}"
    if t == LogType.ATTACK:
        atk = _ATKS.get(lg.get("attackId"))
        aname = atk.name if atk else f"#{lg.get('attackId')}"
        return f"{tag} attacks with {cname(lg.get('cardId'))}: '{aname}'"
    if t == LogType.HP_CHANGE:
        v = lg.get("value")
        return f"{tag} {cname(lg.get('cardId'))} HP {'+' if v and v>0 else ''}{v}"
    if t == LogType.SWITCH:
        return f"{tag} switches active <-> bench"
    if t == LogType.CHANGE:
        return f"{tag} {cname(lg.get('cardIdBefore'))} -> {cname(lg.get('cardIdAfter'))}"
    if t in (LogType.POISONED, LogType.BURNED, LogType.ASLEEP, LogType.PARALYZED, LogType.CONFUSED):
        state = LTYPE.get(t, str(t)).title()
        return f"{tag} {'recovers from ' if lg.get('isRecover') else ''}{state}"
    if t == LogType.COIN:
        return f"{tag} coin: {'HEADS' if lg.get('head') else 'tails'}"
    if t == LogType.RESULT:
        r = lg.get("result")
        reasons = {1: "took all prizes", 2: "opponent decked out", 3: "no active Pokemon", 4: "card effect"}
        who = "DRAW" if r == 2 else f"P{r} WINS"
        return f"*** {who} ({reasons.get(lg.get('reason'),'?')}) ***"
    # Skipped as noise: SHUFFLE, HAS_BASIC_POKEMON, TURN_START/END, DRAW_REVERSE,
    # MOVE_CARD, MOVE_CARD_REVERSE, DEVOLVE, MOVE_ATTACHED.
    return None


def board_summary(state):
    lines = []
    for pi, pl in enumerate(state.players):
        act = pl.active[0] if pl.active else None
        act_s = f"{cname(act.id)} {act.hp}/{act.maxHp}HP e{len(act.energies)}" if act else "(none)"
        bench = ", ".join(f"{cname(b.id)}({b.hp})" for b in pl.bench) or "(empty)"
        lines.append(f"    P{pi}: Active={act_s} | Bench=[{bench}] | hand={pl.handCount} prizes-left={len(pl.prize)}")
    return "\n".join(lines)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1] if len(sys.argv) > 1 else "self"
    agents = [heuristic_agent, heuristic_agent if mode != "random" else random_agent]
    labels = ["heuristic", "heuristic" if mode != "random" else "random"]
    print(f"P0 = {labels[0]}, P1 = {labels[1]}\n" + "=" * 70)

    deck0 = read_deck_csv()
    deck1 = read_deck_csv()
    obs_dict, start = battle_start(deck0, deck1)
    if obs_dict is None:
        print("battle_start failed:", start)
        return

    last_turn = None
    try:
        for step in range(4000):
            obs = to_observation_class(obs_dict)
            state = obs.current

            if state is not None and state.turn != last_turn and state.turn > 0:
                print(f"\n----- TURN {state.turn} (P{state.firstPlayer} went first) -----")
                if state.turn > 1:
                    print(board_summary(state))
                last_turn = state.turn

            if state is not None and state.result != -1:
                break

            sel = obs.select
            if sel is None:
                obs_dict = battle_select(agents[0](obs_dict))
                continue

            pi = state.yourIndex if state else 0
            chosen = agents[pi](obs_dict)

            # Describe the decision (skip trivial forced single-option picks quietly).
            ctx = SelectContext(sel.context).name if sel.context in [c.value for c in SelectContext] else sel.context
            stype = SelectType(sel.type).name if sel.type in [s.value for s in SelectType] else sel.type
            picks = ", ".join(describe_option(sel.option[i]) for i in chosen if 0 <= i < len(sel.option))
            if sel.type != SelectType.MAIN or picks:
                print(f"  P{pi} [{stype}/{ctx}] -> {picks}")

            obs_dict = battle_select(chosen)

            # Decode resulting events.
            nxt = to_observation_class(obs_dict)
            for lg in obs_dict.get("logs", []):
                line = describe_log(lg)
                if line:
                    print(f"      {line}")
    finally:
        battle_finish()
    print("=" * 70 + "\nGame over.")


if __name__ == "__main__":
    main()
