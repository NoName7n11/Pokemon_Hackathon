"""Census of the selection contexts an agent is actually asked, and which cards
it picks during setup.

`decision_trace.py` only records candidate-vs-baseline *differences*, so a
candidate whose setup hook silently no-ops looks identical to one that never
runs. This tool answers the prior question: does the context occur at all, what
is offered, and what does the agent choose?

Setup options (`SETUP_ACTIVE_POKEMON` / `SETUP_BENCH_POKEMON`) carry
`cardId is None`; they identify the card by `area=HAND` plus `index` into
`current.players[yourIndex].hand`. Any setup heuristic that reads `option.cardId`
is inert. That flaw sank PalSystem EXP-0007 and EXP-0008.

Hand entries are `Card(id=..., serial=..., playerIndex=...)` and expose ONLY
those three fields -- no `.name`, no `.cardId`. The printable name requires an
`all_card_data()` lookup keyed on `hand[index].id`. Reading `hand[i].name`
yields `None` and silently disables the heuristic; that flaw sank EXP-0010.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from collections import Counter
from pathlib import Path

from common import ENGINE_PARENT, load_deck_ids

SETUP_CONTEXTS = (1, 2)  # SETUP_ACTIVE_POKEMON, SETUP_BENCH_POKEMON


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Python module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "agent", None)):
        raise ValueError(f"{path} does not define callable agent()")
    return module


def enum_name(value, enum_type) -> str:
    try:
        return enum_type(value).name
    except (TypeError, ValueError):
        return str(value)


def card_name(card, cards) -> str:
    """Resolve a hand entry to a printable name.

    Hand entries carry only `id`; the name lives in the `all_card_data()` table.
    Deliberately does NOT try `card.name` first -- an earlier version did, which
    hid the fact that the attribute never exists and let an inert candidate look
    like a working one.
    """
    if card is None:
        return "None"
    card_id = getattr(card, "id", None)
    return getattr(cards.get(card_id), "name", f"card#{card_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Census selection contexts and setup picks for one agent.")
    parser.add_argument("--agent", required=True, type=Path)
    parser.add_argument("--deck", required=True, type=Path)
    parser.add_argument("--opponent", type=Path, help="defaults to --agent (mirror match)")
    parser.add_argument("--games", type=int, default=10)
    parser.add_argument("--seed", type=int, default=2026081550)
    parser.add_argument("--max-steps", type=int, default=3000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    sys.path.insert(0, str(ENGINE_PARENT))
    from cg.api import SelectContext, SelectType, all_card_data, to_observation_class
    from cg.game import battle_finish, battle_select, battle_start

    cards = {card.cardId: card for card in all_card_data()}
    agent_module = load_module("census_agent", args.agent.resolve())
    opponent_module = load_module("census_opponent", (args.opponent or args.agent).resolve())
    deck_ids = load_deck_ids(args.deck.resolve())

    seen: Counter[str] = Counter()
    offered: Counter[str] = Counter()
    picked: Counter[str] = Counter()
    setup_events = 0
    errors: list[str] = []

    for game in range(args.games):
        my_seat = game % 2
        seats = [agent_module, opponent_module] if my_seat == 0 else [opponent_module, agent_module]
        random.seed(args.seed + game)
        observation, start_data = battle_start(deck_ids, deck_ids)
        if observation is None:
            errors.append(f"game {game + 1}: battle_start failed: {start_data}")
            continue
        try:
            for step in range(args.max_steps):
                parsed = to_observation_class(observation)
                if parsed.current is not None and parsed.current.result != -1:
                    break
                seat = parsed.current.yourIndex if parsed.current else 0
                module = seats[seat]
                module._MY_DECK = deck_ids
                choice = module.agent(observation)
                selection = parsed.select
                if seat == my_seat and selection is not None:
                    seen[f"{enum_name(selection.type, SelectType)}/{enum_name(selection.context, SelectContext)}"] += 1
                    if selection.context in SETUP_CONTEXTS:
                        setup_events += 1
                        hand = parsed.current.players[parsed.current.yourIndex].hand
                        context = enum_name(selection.context, SelectContext)
                        for index, option in enumerate(selection.option):
                            in_hand = option.index is not None and option.index < len(hand)
                            key = f"{context}/{card_name(hand[option.index] if in_hand else None, cards)}"
                            offered[key] += 1
                            if index in choice:
                                picked[key] += 1
                observation = battle_select(choice)
        except Exception as exc:
            errors.append(f"game {game + 1}: {type(exc).__name__}: {exc}")
        finally:
            battle_finish()

    summary = {
        "agent": str(args.agent),
        "deck": str(args.deck),
        "games": args.games,
        "seed": args.seed,
        "setup_selection_events": setup_events,
        "contexts_seen": dict(seen.most_common()),
        "setup_offered": dict(offered.most_common()),
        "setup_picked": dict(picked.most_common()),
        "errors": errors[:20],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    if args.output:
        args.output.resolve().write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
