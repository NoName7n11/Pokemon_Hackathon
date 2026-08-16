"""Play census: which cards does the agent actually PLAY, and which Abilities does it use?

`tempo_census.py` answers "when does the attack land"; this answers "what did the
agent ever do with its 24 Trainers and its ability engine". It exists because the
baseline agent's `_best_play_index` scores every non-Basic-Pokemon card -1, so the
greedy ladder can never play a Trainer -- but the 1-ply lookahead can, and only a
census distinguishes "never played" from "played rarely".

Per game it records, from the acting seat only:
  * every PLAY option actually chosen, resolved to a card name
  * every ABILITY option actually chosen, resolved to a card name
  * whether each watched Pokemon ever reached play, and on which turn
  * the counts split by win and loss

Card-resolution trap (cost 440 games across PalSystem EXP-0007/0008/0010): PLAY and
ABILITY options carry `cardId is None`. They identify the card by `area` + `index`,
and hand entries are `Card(id, serial, playerIndex)` with NO `.name`. The name must
come from `all_card_data()` keyed on that `.id`. `_resolve_option_card` below is the
only correct way to do it; do not reintroduce a `getattr(card, "name", None)` path.
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

HAND = 2
ACTIVE = 4
BENCH = 5
PLAY = 7
ABILITY = 10


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Python module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "agent", None)):
        raise ValueError(f"{path} does not define callable agent()")
    return module


def _resolve_option_card(option, player) -> int | None:
    """Card id behind a PLAY/ABILITY option, via area+index (cardId is None here)."""
    card_id = getattr(option, "cardId", None)
    if card_id:
        return card_id
    area = getattr(option, "area", None)
    index = getattr(option, "index", None)
    if index is None or index < 0:
        return None
    if area == HAND or area is None:
        hand = getattr(player, "hand", None) or []
        if index < len(hand):
            return getattr(hand[index], "id", None)
        return None
    if area == ACTIVE:
        active = getattr(player, "active", None) or []
        if active and active[0] is not None:
            return getattr(active[0], "id", None)
        return None
    if area == BENCH:
        bench = getattr(player, "bench", None) or []
        if index < len(bench) and bench[index] is not None:
            return getattr(bench[index], "id", None)
    return None


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
    parser = argparse.ArgumentParser(description="Census of cards played and Abilities used.")
    parser.add_argument("--agent", required=True, type=Path)
    parser.add_argument("--deck", required=True, type=Path)
    parser.add_argument("--opponent", type=Path, help="defaults to --agent (mirror match)")
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2026081680)
    parser.add_argument("--max-steps", type=int, default=3000)
    parser.add_argument("--watch", nargs="*", default=[], help="Pokemon names to time to first in-play")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    sys.path.insert(0, str(ENGINE_PARENT))
    from cg.api import all_card_data, to_observation_class
    from cg.game import battle_finish, battle_select, battle_start

    cards = {card.cardId: card for card in all_card_data()}
    agent_module = load_module("census_agent", args.agent.resolve())
    opponent_module = load_module("census_opponent", (args.opponent or args.agent).resolve())
    deck_ids = load_deck_ids(args.deck.resolve())

    played: dict[str, Counter[str]] = {"win": Counter(), "loss": Counter()}
    abilities: dict[str, Counter[str]] = {"win": Counter(), "loss": Counter()}
    in_play_turn: dict[str, dict[str, list[int]]] = {n: {"win": [], "loss": []} for n in args.watch}
    per_game_plays: list[int] = []
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
        game_played: Counter[str] = Counter()
        game_abilities: Counter[str] = Counter()
        first_in_play: dict[str, int] = {}
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
                    player = parsed.current.players[parsed.current.yourIndex]
                    turn = parsed.current.turn
                    board = list(player.active or []) + list(player.bench or [])
                    for mon in board:
                        if mon is None:
                            continue
                        name = getattr(cards.get(mon.id), "name", None)
                        if name in in_play_turn and name not in first_in_play:
                            first_in_play[name] = turn
                    selection = parsed.select
                    if selection is not None:
                        for index in choice:
                            if not 0 <= index < len(selection.option):
                                continue
                            option = selection.option[index]
                            if option.type not in (PLAY, ABILITY):
                                continue
                            card_id = _resolve_option_card(option, player)
                            name = getattr(cards.get(card_id), "name", None) or f"cardId:{card_id}"
                            if option.type == PLAY:
                                game_played[name] += 1
                            else:
                                game_abilities[name] += 1
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
            other += 1
            continue
        played[outcome].update(game_played)
        abilities[outcome].update(game_abilities)
        per_game_plays.append(sum(game_played.values()))
        for name, turn in first_in_play.items():
            in_play_turn[name][outcome].append(turn)

    decisive = max(1, wins + losses)
    summary = {
        "agent": str(args.agent),
        "games": args.games,
        "seed": args.seed,
        "wins": wins,
        "losses": losses,
        "draws_or_timeouts": other,
        "plays_per_game": summarize(per_game_plays),
        "played": {outcome: dict(counter.most_common()) for outcome, counter in played.items()},
        "played_per_game": {
            name: round((played["win"][name] + played["loss"][name]) / decisive, 2)
            for name in sorted(set(played["win"]) | set(played["loss"]))
        },
        "abilities": {outcome: dict(counter.most_common()) for outcome, counter in abilities.items()},
        "abilities_per_game": {
            name: round((abilities["win"][name] + abilities["loss"][name]) / decisive, 2)
            for name in sorted(set(abilities["win"]) | set(abilities["loss"]))
        },
        "first_in_play_turn": {
            name: {
                "win": summarize(buckets["win"]),
                "loss": summarize(buckets["loss"]),
                "reached_rate": round((len(buckets["win"]) + len(buckets["loss"])) / decisive, 2),
            }
            for name, buckets in in_play_turn.items()
        },
        "errors": errors[:20],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    if args.output:
        args.output.resolve().write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
