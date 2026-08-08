"""Measure attacker concentration: what share of our attacks come from real
attackers vs weak/support Pokemon.

This is the metric behind the 2026-08-07 gap ("LiamK 88.7% of attacks by their two
real attackers, ours 66.3%"). It was quoted in three PROGRESS entries before any
committed tool produced it, so this is that tool.

Counts every ATTACK option our agent actually selects during heuristic-mirror games
and attributes it to the attacking Active Pokemon, then reports the per-card share.
Cards are not hardcoded into "real" vs "weak" lists -- the ranking is printed and the
top-2 concentration is reported, which is the figure comparable to LiamK's 88.7%.

Run from this directory:
    python3 attacker_share.py [n_games]    (default 40)
"""
import sys
from collections import Counter

import main
from cg.api import OptionType, to_observation_class
from cg.game import battle_finish, battle_select, battle_start


def instrumented(agent, counter):
    """Wrap an agent, recording the Active card whenever it selects an ATTACK."""
    def wrapped(obs_dict):
        picked = agent(obs_dict)
        obs = to_observation_class(obs_dict)
        sel, state = obs.select, obs.current
        if sel is not None and state is not None and picked:
            i = picked[0]
            if 0 <= i < len(sel.option) and sel.option[i].type == OptionType.ATTACK:
                me = state.players[state.yourIndex]
                active = me.active[0] if me.active else None
                if active is not None:
                    card = main._card_data().get(active.id)
                    counter[card.name if card else f"card:{active.id}"] += 1
        return picked
    return wrapped


def play(a0, a1, max_steps=3000):
    deck = main.read_deck_csv()
    obs, _start = battle_start(deck, deck)
    if obs is None:
        return 2
    try:
        agents = [a0, a1]
        for _ in range(max_steps):
            o = to_observation_class(obs)
            if o.current is not None and o.current.result != -1:
                return o.current.result
            pi = o.current.yourIndex if o.current else 0
            obs = battle_select(agents[pi](obs))
        return 2
    finally:
        battle_finish()


def main_cli():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    counter = Counter()
    tracked = instrumented(main.agent, counter)
    # ponytail: only seat 0 is instrumented; the mirror opponent is the same policy,
    # so one seat is a sufficient sample and halves the bookkeeping.
    for i in range(n):
        play(tracked, main.agent) if i % 2 == 0 else play(main.agent, tracked)

    total = sum(counter.values())
    print(f"Attacker share over {n} games -- {total} attacks, "
          f"{total / n:.1f} per game\n")
    if total == 0:
        print("no attacks recorded")
        return
    ranked = counter.most_common()
    for name, c in ranked:
        print(f"  {name:<28} {c:>5}  {c / total:>6.1%}")
    top2 = sum(c for _, c in ranked[:2]) / total
    print(f"\ntop-2 attacker concentration: {top2:.1%}  "
          f"(LiamK reference 88.7%, ours 2026-08-07: 66.3%)")


if __name__ == "__main__":
    main_cli()
