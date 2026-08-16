"""Dump raw selection payloads for one SelectContext, with the board state around them.

Written because the baseline routes ENERGY/SKILL/SPECIAL_CONDITION selections to a
blind `range(minCount)` default, and you cannot write a real policy for a context
whose option fields you have never seen. Prints, for the first N selections matching
the requested type/context: every option's fields, plus the acting player's board
(active/bench with hp and attached energy) so the right answer is checkable by eye.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path

from common import ENGINE_PARENT, load_deck_ids


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Python module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mon(cards, mon):
    if mon is None:
        return None
    return {
        "name": getattr(cards.get(mon.id), "name", None),
        "id": mon.id,
        "hp": mon.hp,
        "maxHp": mon.maxHp,
        "energies": list(getattr(mon, "energies", []) or []),
        "energyCards": [getattr(c, "id", None) for c in (getattr(mon, "energyCards", None) or [])],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump raw options for one selection context.")
    parser.add_argument("--agent", required=True, type=Path)
    parser.add_argument("--deck", required=True, type=Path)
    parser.add_argument("--select-type", type=int, help="cg.api.SelectType value")
    parser.add_argument("--context", type=int, help="cg.api.SelectContext value")
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--seed", type=int, default=2026081690)
    parser.add_argument("--max-steps", type=int, default=3000)
    args = parser.parse_args()

    sys.path.insert(0, str(ENGINE_PARENT))
    from cg.api import SelectContext, SelectType, all_card_data, to_observation_class
    from cg.game import battle_finish, battle_select, battle_start

    cards = {card.cardId: card for card in all_card_data()}
    module = load_module("dump_agent", args.agent.resolve())
    deck_ids = load_deck_ids(args.deck.resolve())

    samples: list[dict] = []
    for game in range(args.games):
        if len(samples) >= args.samples:
            break
        random.seed(args.seed + game)
        observation, _ = battle_start(deck_ids, deck_ids)
        if observation is None:
            continue
        try:
            for _ in range(args.max_steps):
                parsed = to_observation_class(observation)
                if parsed.current is not None and parsed.current.result != -1:
                    break
                module._MY_DECK = deck_ids
                choice = module.agent(observation)
                sel = parsed.select
                if (
                    sel is not None
                    and parsed.current is not None
                    and len(samples) < args.samples
                    and (args.select_type is None or sel.type == args.select_type)
                    and (args.context is None or sel.context == args.context)
                ):
                    me = parsed.current.players[parsed.current.yourIndex]
                    samples.append({
                        "turn": parsed.current.turn,
                        "type": f"{SelectType(sel.type).name}({sel.type})",
                        "context": f"{SelectContext(sel.context).name}({sel.context})",
                        "minCount": sel.minCount,
                        "maxCount": sel.maxCount,
                        "chosen": list(choice),
                        "options": [
                            {k: v for k, v in vars(opt).items() if v is not None}
                            for opt in sel.option
                        ],
                        "my_active": _mon(cards, me.active[0] if me.active else None),
                        "my_bench": [_mon(cards, m) for m in (me.bench or [])],
                        "my_hand_ids": [getattr(c, "id", None) for c in (me.hand or [])],
                    })
                observation = battle_select(choice)
        except Exception as exc:  # a dump tool must never mask the sample it already has
            samples.append({"error": f"{type(exc).__name__}: {exc}"})
        finally:
            battle_finish()

    print(json.dumps(samples, indent=2, ensure_ascii=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
