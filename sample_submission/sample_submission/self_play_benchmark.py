"""Benchmark current agent against the frozen previous-agent baseline.

Run from this directory:
    python self_play_benchmark.py [n_games]
"""
import sys
from math import sqrt

from cg.api import to_observation_class
from cg.game import battle_finish, battle_select, battle_start
from main import agent as current_agent, read_deck_csv
from previous_agent import agent as previous_agent


def wilson_interval(wins: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    phat = wins / total
    denom = 1 + z * z / total
    center = (phat + z * z / (2 * total)) / denom
    half = z * sqrt((phat * (1 - phat) + z * z / (4 * total)) / total) / denom
    return center - half, center + half


def play_one(agent0, agent1, max_steps: int = 3000) -> tuple[int, int]:
    """Return (result, steps); result is 0, 1, or 2 for draw/timeout."""
    deck0 = read_deck_csv()
    deck1 = read_deck_csv()
    obs_dict, start_data = battle_start(deck0, deck1)
    if obs_dict is None:
        print("battle_start failed:", start_data)
        return 2, 0

    try:
        agents = [agent0, agent1]
        for step in range(max_steps):
            obs = to_observation_class(obs_dict)
            if obs.current is not None and obs.current.result != -1:
                return obs.current.result, step
            player_idx = obs.current.yourIndex if obs.current else 0
            obs_dict = battle_select(agents[player_idx](obs_dict))
        return 2, max_steps
    finally:
        battle_finish()


def main():
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    wins = {"current": 0, "previous": 0, "draw": 0}
    total_steps = 0

    for i in range(n_games):
        if i % 2 == 0:
            result, steps = play_one(current_agent, previous_agent)
            if result == 0:
                wins["current"] += 1
            elif result == 1:
                wins["previous"] += 1
            else:
                wins["draw"] += 1
        else:
            result, steps = play_one(previous_agent, current_agent)
            if result == 1:
                wins["current"] += 1
            elif result == 0:
                wins["previous"] += 1
            else:
                wins["draw"] += 1

        total_steps += steps
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{n_games} games done -- {wins}")

    print(f"\nFinal after {n_games} games: {wins}")
    lo, hi = wilson_interval(wins["current"], n_games)
    print(f"Current win rate: {wins['current'] / n_games:.1%} (95% CI {lo:.1%} - {hi:.1%})")
    print(f"Average steps: {total_steps / n_games:.1f}")


if __name__ == "__main__":
    main()
