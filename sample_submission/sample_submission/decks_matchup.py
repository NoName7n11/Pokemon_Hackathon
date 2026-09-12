"""Round of matchups: P0 fixed = Hide_n_Sneak, P1 = each deck in Decs/.

Both seats play the heuristic agent (main.agent); only the decks differ. Records
win/loss/draw and average game length per opponent.

Run from this directory:
    python3 decks_matchup.py [n_games]   (default 100)
"""
import sys
from pathlib import Path

from cg.api import to_observation_class
from cg.game import battle_finish, battle_select, battle_start
from main import agent as heuristic

DECS = Path(__file__).resolve().parents[2] / "decks" / "Decs"
P0_DECK = "Hide_n_Sneak.csv"


def load_deck(path: Path) -> list[int]:
    ids = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [int(x) for x in ids[:60]]


def play_one(deck0, deck1, max_steps=3000):
    obs_dict, start = battle_start(deck0, deck1)
    if obs_dict is None:
        print("battle_start failed:", start)
        return 2, 0
    try:
        for step in range(max_steps):
            obs = to_observation_class(obs_dict)
            if obs.current is not None and obs.current.result != -1:
                return obs.current.result, step
            pi = obs.current.yourIndex if obs.current else 0
            obs_dict = battle_select(heuristic(obs_dict))
        return 2, max_steps
    finally:
        battle_finish()


def main():
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    deck0 = load_deck(DECS / P0_DECK)
    opponents = sorted(p.name for p in DECS.glob("*.csv"))

    print(f"P0 = {P0_DECK} (fixed), heuristic vs heuristic, {n_games} games each\n")
    header = f"{'P1 opponent':<32} {'P0 win':>7} {'P1 win':>7} {'draw':>5} {'P0 win%':>8} {'avg steps':>10}"
    print(header)
    print("-" * len(header))

    results = []
    for opp in opponents:
        deck1 = load_deck(DECS / opp)
        w0 = w1 = draw = steps_sum = 0
        for _ in range(n_games):
            r, steps = play_one(deck0, deck1)
            steps_sum += steps
            if r == 0:
                w0 += 1
            elif r == 1:
                w1 += 1
            else:
                draw += 1
        rate = w0 / n_games
        print(f"{opp:<32} {w0:>7} {w1:>7} {draw:>5} {rate:>7.1%} {steps_sum/n_games:>10.1f}")
        results.append((opp, w0, w1, draw, rate))

    print("\nSummary (P0 = Hide_n_Sneak win rate vs each opponent):")
    for opp, w0, w1, draw, rate in sorted(results, key=lambda x: -x[4]):
        print(f"  {rate:>6.1%}  vs {opp}")


if __name__ == "__main__":
    main()
