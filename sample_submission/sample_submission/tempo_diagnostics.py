"""Measure tempo/stall symptoms for an agent over local simulator games.

Run from this directory:
    python tempo_diagnostics.py [n_games]
"""
import random
import sys
from collections import Counter

from cg.api import OptionType, SelectType, to_observation_class
from cg.game import battle_finish, battle_select, battle_start
from main import agent as heuristic_agent, read_deck_csv


def random_agent(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return read_deck_csv()
    sel = obs.select
    return random.sample(range(len(sel.option)), sel.maxCount)


def option_counts(sel) -> Counter:
    return Counter(opt.type for opt in sel.option)


def play_one(agent0, agent1, max_steps: int = 3000) -> tuple[int, Counter]:
    deck0 = read_deck_csv()
    deck1 = read_deck_csv()
    obs_dict, start_data = battle_start(deck0, deck1)
    if obs_dict is None:
        print("battle_start failed:", start_data)
        return 2, Counter({"battle_start_failed": 1})

    stats = Counter()
    try:
        agents = [agent0, agent1]
        for _ in range(max_steps):
            obs = to_observation_class(obs_dict)
            if obs.current is not None and obs.current.result != -1:
                stats["finished"] += 1
                return obs.current.result, stats

            sel = obs.select
            player_idx = obs.current.yourIndex if obs.current else 0
            if sel is not None and obs.current is not None and player_idx == 0:
                me = obs.current.players[player_idx]
                counts = option_counts(sel)
                if sel.type == SelectType.MAIN:
                    stats["main_states"] += 1
                    if OptionType.ATTACK in counts:
                        stats["main_attack_available"] += 1
                    else:
                        stats["main_no_attack_available"] += 1
                    if OptionType.PLAY in counts:
                        stats["main_play_available"] += 1
                    if OptionType.END in counts and me.handCount >= 10:
                        stats["big_hand_main_states"] += 1

            selection = agents[player_idx](obs_dict)
            if sel is not None and obs.current is not None and player_idx == 0:
                selected_types = [sel.option[i].type for i in selection if 0 <= i < len(sel.option)]
                if sel.type == SelectType.MAIN and OptionType.END in selected_types:
                    stats["main_end_selected"] += 1
                    if obs.current.players[player_idx].handCount >= 10:
                        stats["big_hand_end_selected"] += 1
                if sel.type == SelectType.MAIN and OptionType.ATTACK in selected_types:
                    stats["main_attack_selected"] += 1
                if sel.type == SelectType.MAIN and OptionType.PLAY in selected_types:
                    stats["main_play_selected"] += 1

            obs_dict = battle_select(selection)

        stats["timeout"] += 1
        return 2, stats
    finally:
        battle_finish()


def main():
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    totals = Counter()
    results = Counter()

    for i in range(n_games):
        result, stats = play_one(heuristic_agent, random_agent)
        results[result] += 1
        totals.update(stats)
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{n_games} games done")

    print(f"\nResults: p0={results[0]} p1={results[1]} draw={results[2]}")
    for key in sorted(totals):
        print(f"{key}: {totals[key]}")
    if totals["main_states"]:
        print(f"attack availability: {totals['main_attack_available'] / totals['main_states']:.1%}")
        print(f"big-hand END rate: {totals['big_hand_end_selected'] / totals['main_states']:.1%}")


if __name__ == "__main__":
    main()
