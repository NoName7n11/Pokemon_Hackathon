"""Measure cabt search-API speed to size a future lookahead.

At several real MAIN decision points, times:
  - search_begin (fork current state, providing hidden-info predictions)
  - each search_step (advance one selection inside the forked state)
  - a full one-turn rollout (begin -> steps until the turn changes or ends)

Then reports how many rollouts fit into example per-decision budgets, given the
env's ~600s per-game overage bank.

Run from this directory:
    python3 time_probe.py [n_decision_points]   (default 25)
"""
import statistics
import sys
import time
from pathlib import Path

from cg.api import SelectType, to_observation_class, search_begin, search_step, search_end
from cg.game import battle_finish, battle_select, battle_start
from main import agent as heuristic, read_deck_csv

DECS = Path(__file__).resolve().parents[2] / "Decs"


def load(name):
    ids = [ln.strip() for ln in (DECS / name).read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [int(x) for x in ids[:60]]


def predictions(obs, my_deck_ids, opp_deck_ids):
    """Build the hidden-info args search_begin needs. For a timing probe the
    identities need only be valid card IDs of the right COUNT; realism is
    irrelevant to how long the C++ search takes."""
    st = obs.current
    yi = st.yourIndex
    me, opp = st.players[yi], st.players[1 - yi]

    def take(ids, n):
        # Repeat/truncate a valid-ID pool to exactly n cards.
        if n <= 0:
            return []
        pool = ids or [my_deck_ids[0]]
        return [pool[i % len(pool)] for i in range(n)]

    return {
        "your_deck": take(my_deck_ids, me.deckCount),
        "your_prize": take(my_deck_ids, len(me.prize)),
        "opponent_deck": take(opp_deck_ids, opp.deckCount),
        "opponent_prize": take(opp_deck_ids, len(opp.prize)),
        "opponent_hand": take(opp_deck_ids, opp.handCount),
        "opponent_active": [],
    }


def valid_select(sel):
    if sel.minCount > 0:
        return list(range(sel.minCount))
    return [0] if sel.maxCount >= 1 and sel.option else []


def probe_one(obs, my_deck_ids, opp_deck_ids, max_rollout_steps=40):
    """Return (begin_ms, [step_ms...], rollout_ms, n_steps) or None on failure."""
    pred = predictions(obs, my_deck_ids, opp_deck_ids)
    start_turn = obs.current.turn
    t0 = time.perf_counter()
    try:
        ss = search_begin(obs, pred["your_deck"], pred["your_prize"], pred["opponent_deck"],
                          pred["opponent_prize"], pred["opponent_hand"], pred["opponent_active"])
    except Exception as e:
        return None, repr(e)
    begin_ms = (time.perf_counter() - t0) * 1000

    step_ms = []
    try:
        for _ in range(max_rollout_steps):
            s = ss.observation.select
            cur = ss.observation.current
            if s is None or (cur is not None and cur.result != -1):
                break
            if cur is not None and cur.turn != start_turn:
                break  # a full turn has elapsed
            ts = time.perf_counter()
            ss = search_step(ss.searchId, valid_select(s))
            step_ms.append((time.perf_counter() - ts) * 1000)
    except Exception:
        pass
    finally:
        search_end()
    rollout_ms = begin_ms + sum(step_ms)
    return (begin_ms, step_ms, rollout_ms, len(step_ms)), None


def main():
    n_points = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    my_deck = load("Hydrapple.csv")
    opp_deck = load("Hydrapple.csv")

    obs_dict, start = battle_start(my_deck, opp_deck)
    if obs_dict is None:
        print("battle_start failed:", start)
        return

    begins, all_steps, rollouts, fails = [], [], [], 0
    err_samples = []
    collected = 0
    try:
        for _ in range(6000):
            obs = to_observation_class(obs_dict)
            st = obs.current
            if st is not None and st.result != -1:
                break
            sel = obs.select
            # Probe only at our own MAIN decisions with real choices.
            if (sel is not None and st is not None and st.yourIndex == 0
                    and sel.type == SelectType.MAIN and len(sel.option) >= 2
                    and collected < n_points):
                res, err = probe_one(obs, my_deck, opp_deck)
                if res is None:
                    fails += 1
                    if len(err_samples) < 3:
                        err_samples.append(err)
                else:
                    b, steps, roll, nst = res
                    begins.append(b)
                    all_steps.extend(steps)
                    rollouts.append((roll, nst))
                    collected += 1
            obs_dict = battle_select(heuristic(obs_dict))
            if collected >= n_points:
                break
    finally:
        battle_finish()

    print(f"Probed {collected} MAIN decision points (failures: {fails})")
    if err_samples:
        print("Sample search_begin errors:", err_samples)
    if not begins:
        print("No successful search calls — check prediction construction.")
        return

    def stat(xs):
        return f"mean={statistics.mean(xs):.2f}ms median={statistics.median(xs):.2f}ms max={max(xs):.2f}ms"

    print(f"\nsearch_begin:  {stat(begins)}")
    if all_steps:
        print(f"search_step:   {stat(all_steps)}  (n={len(all_steps)})")
    roll_ms = [r for r, _ in rollouts]
    roll_steps = [n for _, n in rollouts]
    print(f"one-turn rollout (begin+steps): {stat(roll_ms)}  avg steps/rollout={statistics.mean(roll_steps):.1f}")

    med = statistics.median(roll_ms)
    print(f"\nAt median {med:.1f}ms per one-turn rollout:")
    for budget_ms in (200, 500, 1000, 2000, 4000):
        print(f"  {budget_ms/1000:>4.1f}s budget -> ~{int(budget_ms/med)} candidate rollouts")
    print(f"\nEnv budget: ~600s overage bank per game (actTimeout=0). "
          f"A ~150-decision game leaves ~{600/150*1000:.0f}ms/decision on average.")


if __name__ == "__main__":
    main()
