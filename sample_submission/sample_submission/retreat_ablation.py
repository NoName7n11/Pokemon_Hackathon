"""Attribute the 2026-08-08 fix #2 win-rate gain to one of its two mechanisms.

Fix #2 shipped TWO changes at once (71.2% vs the 64.6% lookahead reference):
  (a) tactical retreat gate, ordered above "attack anyway" in the MAIN ladder
  (b) own-board CARD selection ranked by _live_attacker_score instead of static
      _option_card_power -- this fires on every forced promotion after a KO,
      which is far more common than RETREAT (3.9% of MAIN decisions)

So the gain cannot currently be credited to either. This harness disables each
arm independently against the same frozen opponent and prints a two-proportion
z-test of every arm against the "both" control.

Run from this directory:
    python3 retreat_ablation.py [n_games]    (default 500)
"""
import sys
from math import erf, sqrt

import main
from cg.api import AreaType, SelectContext, to_observation_class
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


def two_prop_z(w1, n1, w2, n2):
    """Two-sided two-proportion z-test. Preferred over comparing Wilson CIs by
    eye: overlapping CIs do NOT imply a non-significant difference."""
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    p1, p2 = w1 / n1, w2 / n2
    p = (w1 + w2) / (n1 + n2)
    se = sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0
    z = (p2 - p1) / se
    return z, 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))


def choose_card_prefix2(obs):
    """The _choose_card as it stood BEFORE fix #2: own-board options ranked by
    static _option_card_power, with no live-attacker awareness."""
    sel = obs.select
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
        opponent_indices = [
            i for i, opt in enumerate(options)
            if opt.playerIndex is not None and obs.current is not None
            and opt.playerIndex != obs.current.yourIndex
        ]
        if opponent_indices:
            indices = opponent_indices
        ranked = sorted(indices, key=lambda i: main._target_score(options[i], obs), reverse=True)
    else:
        reverse = sel.context not in weakest_first_contexts
        ranked = sorted(indices, key=lambda i: main._option_card_power(options[i]), reverse=reverse)
    return ranked[: sel.maxCount] if sel.maxCount > 0 else []


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


def run_arm(name, n, retreat_on, card_on):
    # The retreat gate this ablation targeted was DELETED from main.py after the
    # experiment (it measured to exactly zero). The arms are kept for reproducibility;
    # the retreat arms degrade to no-ops against the cleaned agent.
    orig_retreat = getattr(main, "_should_retreat_to_better_attacker", None)
    orig_card = main._choose_card
    if not retreat_on and orig_retreat is not None:
        # ponytail: disables tactical retreat entirely rather than restoring the
        # old <=30%-HP rule. Isolates the fix's own contribution; the pre-fix
        # rule fired rarely enough that "off" is the informative control.
        main._should_retreat_to_better_attacker = lambda me, opp_active: False
    if not card_on:
        main._choose_card = choose_card_prefix2
    try:
        wins = 0
        for i in range(n):
            if i % 2 == 0:
                wins += play(main.agent, previous_agent) == 0
            else:
                wins += play(previous_agent, main.agent) == 1
    finally:
        if orig_retreat is not None:
            main._should_retreat_to_better_attacker = orig_retreat
        main._choose_card = orig_card
    lo, hi = wilson(wins, n)
    print(f"{name:<20} {wins:>4}/{n}  {wins/n:>6.1%}  [95% CI {lo:.1%} - {hi:.1%}]", flush=True)
    return wins


def main_cli():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    print(f"Fix #2 ablation, {n} games/arm vs frozen previous_agent. "
          f"SEARCH_MAIN={main.SEARCH_MAIN}\n")
    arms = [
        ("both (control)", True, True),
        ("retreat_off", False, True),
        ("card_off", True, False),
        ("neither", False, False),
    ]
    results = {name: run_arm(name, n, r, c) for name, r, c in arms}

    control = results["both (control)"]
    print("\nvs control (two-proportion z):")
    for name, wins in results.items():
        if name == "both (control)":
            continue
        z, p = two_prop_z(control, n, wins, n)
        mark = "SIGNIFICANT" if p < 0.05 else "tie"
        print(f"  {name:<18} delta {(wins - control) / n:+.1%}  z={z:+.2f}  p={p:.4f}  {mark}")


if __name__ == "__main__":
    main_cli()
