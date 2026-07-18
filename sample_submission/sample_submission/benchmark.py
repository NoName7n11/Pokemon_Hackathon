"""Benchmark the heuristic agent (main.agent) vs a random-move agent.

Run from this directory:
    python benchmark.py [n_games]
"""
import random
import sys

from cg.api import to_observation_class
from cg.game import battle_start, battle_select, battle_finish
from main import agent as heuristic_agent, read_deck_csv


def random_agent(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return read_deck_csv()
    sel = obs.select
    return random.sample(range(len(sel.option)), sel.maxCount)


def play_one(agent0, agent1, max_steps: int = 3000) -> int:
    """Returns 0 if agent0 (player0) wins, 1 if agent1 wins, 2 if draw/timeout."""
    deck0 = read_deck_csv()
    deck1 = read_deck_csv()
    obs_dict, start_data = battle_start(deck0, deck1)
    if obs_dict is None:
        print("battle_start failed:", start_data)
        return 2

    agents = [agent0, agent1]
    result = 2
    for _ in range(max_steps):
        obs = to_observation_class(obs_dict)
        if obs.current is not None and obs.current.result != -1:
            result = obs.current.result
            break
        player_idx = obs.current.yourIndex if obs.current else 0
        selection = agents[player_idx](obs_dict)
        obs_dict = battle_select(selection)
    battle_finish()
    return result


def main():
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    wins = {"heuristic": 0, "random": 0, "draw": 0}

    for i in range(n_games):
        # Alternate who plays player0 to cancel out first-move advantage.
        if i % 2 == 0:
            result = play_one(heuristic_agent, random_agent)
            if result == 0:
                wins["heuristic"] += 1
            elif result == 1:
                wins["random"] += 1
            else:
                wins["draw"] += 1
        else:
            result = play_one(random_agent, heuristic_agent)
            if result == 1:
                wins["heuristic"] += 1
            elif result == 0:
                wins["random"] += 1
            else:
                wins["draw"] += 1

        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{n_games} games done -- {wins}")

    print(f"\nFinal after {n_games} games: {wins}")
    win_rate = wins["heuristic"] / n_games
    print(f"Heuristic win rate: {win_rate:.1%}")


if __name__ == "__main__":
    main()
