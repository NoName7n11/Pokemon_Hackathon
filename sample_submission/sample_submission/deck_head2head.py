"""Seat-balanced head-to-head between two Decs/*.csv decks, one agent piloting both.

Usage (from this directory):
    python3 deck_head2head.py DECK_A DECK_B [n_per_direction]

Reports A's win rate with a Wilson 95% CI, plus average game length and any
step-cap timeouts (long games are a real outcome, not a silent drop).
"""
import sys
from math import sqrt
from pathlib import Path

import main as agent_mod
from cg.api import to_observation_class
from cg.game import battle_finish, battle_select, battle_start

DECS = Path(__file__).resolve().parents[2] / "Decs"


def load(name):
    txt = (DECS / f"{name}.csv").read_text(encoding="utf-8")
    return [int(x) for x in txt.split() if x.strip()][:60]


def wilson(w, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt((p * (1 - p) + z * z / (4 * n)) / n) / d
    return c - h, c + h


def seat(deck_ids):
    def act(obs):
        agent_mod._MY_DECK = deck_ids
        return agent_mod.agent(obs)
    return act


def play(d0, d1, max_steps=1200):
    agents = [seat(d0), seat(d1)]
    obs, _ = battle_start(d0, d1)
    if obs is None:
        return 2, 0
    try:
        for step in range(max_steps):
            o = to_observation_class(obs)
            if o.current is not None and o.current.result != -1:
                return o.current.result, step
            pi = o.current.yourIndex if o.current else 0
            obs = battle_select(agents[pi](obs))
        return 2, max_steps
    finally:
        battle_finish()


def main():
    a_name, b_name = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    da, db = load(a_name), load(b_name)
    wins = draws = steps = 0
    for i in range(n):
        r, s = play(da, db)          # A as P0
        steps += s
        wins += r == 0
        draws += r == 2
        r, s = play(db, da)          # A as P1
        steps += s
        wins += r == 1
        draws += r == 2
        if (i + 1) % 10 == 0:
            print(f"  {2*(i+1)}/{2*n} games, A wins {wins}", flush=True)
    total = 2 * n
    lo, hi = wilson(wins, total)
    verdict = "TIE (CI spans 50%)" if lo <= 0.5 <= hi else (
        f"{a_name} BETTER" if wins / total > 0.5 else f"{b_name} BETTER")
    print(f"\n{a_name} vs {b_name}: {wins}/{total} = {wins/total:.1%} "
          f"[95% CI {lo:.1%}-{hi:.1%}]  avg {steps/total:.0f} steps, {draws} draws/timeouts")
    print("=>", verdict)


if __name__ == "__main__":
    main()
