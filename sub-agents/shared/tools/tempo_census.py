"""Tempo census: when does the agent first land Phantom Dive, and does it matter?

Curated PalSystem replays put the first Phantom Dive on turn 9.08 in wins vs
9.58 in losses, and the first Dragapult Active on turn 8.0 vs 7.8. Those gaps
are small, so before any tempo hypothesis is worth an experiment we need the
local number: if self-play lands Phantom Dive far later than 9, the deck is
being piloted too slowly and tempo is the lever; if it already lands near 9,
the replay gap is noise and the next experiment should go elsewhere.

Records, per game: the turn of the first named attack, the turn a named Pokemon
first becomes Active, and the game result -- so first-use turn can be split by
win and loss the same way the replay report does.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

from common import ENGINE_PARENT, load_deck_ids

DEFAULT_ATTACKS = ("Phantom Dive", "Jet Headbutt", "Itchy Pollen")
DEFAULT_ACTIVE = ("Dragapult ex",)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Python module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "agent", None)):
        raise ValueError(f"{path} does not define callable agent()")
    return module


def summarize(values: list[int]) -> dict[str, float | int]:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 2),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure first-use turn of key attacks and Active Pokemon.")
    parser.add_argument("--agent", required=True, type=Path)
    parser.add_argument("--deck", required=True, type=Path)
    parser.add_argument("--opponent", type=Path, help="defaults to --agent (mirror match)")
    parser.add_argument("--games", type=int, default=30)
    parser.add_argument("--seed", type=int, default=2026081570)
    parser.add_argument("--max-steps", type=int, default=3000)
    parser.add_argument("--attacks", nargs="*", default=list(DEFAULT_ATTACKS))
    parser.add_argument("--active", nargs="*", default=list(DEFAULT_ACTIVE))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    sys.path.insert(0, str(ENGINE_PARENT))
    from cg.api import all_attack, all_card_data, to_observation_class
    from cg.game import battle_finish, battle_select, battle_start

    cards = {card.cardId: card for card in all_card_data()}
    attacks = {attack.attackId: attack for attack in all_attack()}
    agent_module = load_module("tempo_agent", args.agent.resolve())
    opponent_module = load_module("tempo_opponent", (args.opponent or args.agent).resolve())
    deck_ids = load_deck_ids(args.deck.resolve())

    attack_first: dict[str, dict[str, list[int]]] = {name: {"win": [], "loss": []} for name in args.attacks}
    active_first: dict[str, dict[str, list[int]]] = {name: {"win": [], "loss": []} for name in args.active}
    attack_uses: dict[str, Counter[str]] = {name: Counter() for name in args.attacks}
    wins = losses = other = 0
    errors: list[str] = []

    for game in range(args.games):
        my_seat = game % 2
        seats = [agent_module, opponent_module] if my_seat == 0 else [opponent_module, agent_module]
        random.seed(args.seed + game)
        observation, start_data = battle_start(deck_ids, deck_ids)
        if observation is None:
            errors.append(f"game {game + 1}: battle_start failed: {start_data}")
            continue
        first_attack_turn: dict[str, int] = {}
        first_active_turn: dict[str, int] = {}
        used: Counter[str] = Counter()
        result = None
        try:
            for _ in range(args.max_steps):
                parsed = to_observation_class(observation)
                if parsed.current is not None and parsed.current.result != -1:
                    result = parsed.current.result
                    break
                seat = parsed.current.yourIndex if parsed.current else 0
                module = seats[seat]
                module._MY_DECK = deck_ids
                choice = module.agent(observation)
                if seat == my_seat and parsed.current is not None:
                    turn = parsed.current.turn
                    player = parsed.current.players[parsed.current.yourIndex]
                    # active is a list that can hold a None slot between KO and replacement
                    if player.active and player.active[0] is not None:
                        name = getattr(cards.get(player.active[0].id), "name", None)
                        if name in active_first and name not in first_active_turn:
                            first_active_turn[name] = turn
                    selection = parsed.select
                    if selection is not None:
                        for index in choice:
                            if not 0 <= index < len(selection.option):
                                continue
                            attack_id = getattr(selection.option[index], "attackId", None)
                            if attack_id is None:
                                continue
                            name = getattr(attacks.get(attack_id), "name", None)
                            if name is None:
                                continue
                            used[name] += 1
                            if name in attack_first and name not in first_attack_turn:
                                first_attack_turn[name] = turn
                observation = battle_select(choice)
        except Exception as exc:
            errors.append(f"game {game + 1}: {type(exc).__name__}: {exc}")
        finally:
            battle_finish()

        if result == my_seat:
            outcome = "win"
            wins += 1
        elif result in (0, 1):
            outcome = "loss"
            losses += 1
        else:
            outcome = None
            other += 1
        if outcome is None:
            continue
        for name, turn in first_attack_turn.items():
            attack_first[name][outcome].append(turn)
        for name, turn in first_active_turn.items():
            active_first[name][outcome].append(turn)
        for name, count in used.items():
            if name in attack_uses:
                attack_uses[name][outcome] += count

    summary = {
        "agent": str(args.agent),
        "games": args.games,
        "seed": args.seed,
        "wins": wins,
        "losses": losses,
        "draws_or_timeouts": other,
        "first_attack_turn": {
            name: {"win": summarize(buckets["win"]), "loss": summarize(buckets["loss"])}
            for name, buckets in attack_first.items()
        },
        "first_active_turn": {
            name: {"win": summarize(buckets["win"]), "loss": summarize(buckets["loss"])}
            for name, buckets in active_first.items()
        },
        "attack_uses": {name: dict(counter) for name, counter in attack_uses.items()},
        "errors": errors[:20],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    if args.output:
        args.output.resolve().write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
