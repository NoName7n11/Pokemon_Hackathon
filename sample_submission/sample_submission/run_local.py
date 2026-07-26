"""Run a local battle between two agents without kaggle-environments.

Usage: python run_local.py
"""
import random

from cg.api import to_observation_class
from cg.game import battle_start, battle_select, battle_finish, visualize_data
from main import agent, read_deck_csv


def run_battle(agent0, agent1, max_steps: int = 2000) -> None:
    deck0 = read_deck_csv()
    deck1 = read_deck_csv()
    obs_dict, start_data = battle_start(deck0, deck1)
    if obs_dict is None:
        print("battle_start failed:", start_data)
        return

    try:
        agents = [agent0, agent1]
        for step in range(max_steps):
            obs = to_observation_class(obs_dict)
            if obs.current is not None and obs.current.result != -1:
                print(f"Game over after {step} steps. Result: {obs.current.result}")
                break

            # yourIndex tells whose turn/selection this is
            player_idx = obs.current.yourIndex if obs.current else 0
            selection = agents[player_idx](obs_dict)
            obs_dict = battle_select(selection)
        else:
            print("Hit max_steps without a result.")

        with open("result.txt", "w", encoding="utf-8") as f:
            f.write(visualize_data())
        print("Wrote result.txt")
    finally:
        battle_finish()


if __name__ == "__main__":
    run_battle(agent, agent)
