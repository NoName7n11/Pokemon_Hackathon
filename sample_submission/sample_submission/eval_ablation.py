"""Ablate the _eval_state terms to attribute the lookahead's win rate.

Runs current-vs-frozen-previous self-play for each eval variant, so a gain can be
credited to a specific term instead of a bundle of changes.

Variants:
  full        prizes + hp + active_quality + ko_risk   (shipped v2)
  no_ko       prizes + hp + active_quality             (drop KO-back risk)
  no_quality  prizes + hp + ko_risk                    (drop Active quality)
  base        prizes + hp + active energy              (the v1 naive eval)

Run from this directory:
    python3 eval_ablation.py [n_games]    (default 200)
"""
import sys
from math import sqrt

import main
from cg.api import to_observation_class
from cg.game import battle_finish, battle_select, battle_start
from previous_agent import agent as previous_agent


def wilson(w, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt((p * (1 - p) + z * z / (4 * n)) / n) / d
    return c - h, c + h


def make_eval(use_quality: bool, use_ko: bool, v1_energy: bool = False):
    def _eval(state, my_index: int) -> float:
        if state is None:
            return 0.0
        if state.result != -1:
            if state.result == my_index:
                return main.WIN_SCORE
            if state.result == 1 - my_index:
                return -main.WIN_SCORE
            return 0.0
        me = state.players[my_index]
        opp = state.players[1 - my_index]

        def total_hp(p):
            mons = ([p.active[0]] if p.active and p.active[0] else []) + list(p.bench)
            return sum(m.hp for m in mons)

        score = (len(opp.prize) - len(me.prize)) * 1000 + total_hp(me) - total_hp(opp)
        my_active = me.active[0] if me.active else None
        opp_active = opp.active[0] if opp.active else None
        if v1_energy:
            return score + (len(my_active.energies) * 5 if my_active else 0)
        if use_quality and my_active is not None:
            score += main._best_usable_damage(my_active) * 2 + len(my_active.energies) * 5
        if use_ko and my_active is not None and opp_active is not None:
            if main._best_usable_damage(opp_active) >= my_active.hp:
                score -= 300 * main._prize_value(my_active)
        return score
    return _eval


def play(a0, a1, max_steps=3000):
    deck = main.read_deck_csv()
    obs, start = battle_start(deck, deck)
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


def run_variant(name, eval_fn, n):
    original = main._eval_state
    main._eval_state = eval_fn
    try:
        wins = 0
        for i in range(n):
            if i % 2 == 0:
                wins += play(main.agent, previous_agent) == 0
            else:
                wins += play(previous_agent, main.agent) == 1
    finally:
        main._eval_state = original
    lo, hi = wilson(wins, n)
    print(f"{name:<12} {wins:>4}/{n}  {wins/n:>6.1%}  [95% CI {lo:.1%} - {hi:.1%}]", flush=True)


def main_cli():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    print(f"Eval ablation, {n} games each (vs frozen previous_agent). SEARCH_MAIN={main.SEARCH_MAIN}\n")
    run_variant("full", make_eval(True, True), n)
    run_variant("no_ko", make_eval(True, False), n)
    run_variant("no_quality", make_eval(False, True), n)
    run_variant("base(v1)", make_eval(False, False, v1_energy=True), n)


if __name__ == "__main__":
    main_cli()
