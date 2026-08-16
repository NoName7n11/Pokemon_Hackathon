"""Prove a candidate is not inert in one specific selection context.

`decision_trace.py` records candidate-vs-baseline differences across all
contexts; if the intended context never differs it reports nothing, which looks
identical to a candidate that never runs. This tool asks both agents for a
choice on the *same* observation, restricted to one context, and reports how
often they agree -- plus the resolved card names on both sides.

Run this BEFORE smoke/screening. PalSystem EXP-0007, EXP-0008, and EXP-0010 all
passed validation, ran 220 games each, and were inert; each would have been
caught here in under a minute.
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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Python module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "agent", None)):
        raise ValueError(f"{path} does not define callable agent()")
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a candidate differs from baseline in one context.")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--deck", required=True, type=Path)
    parser.add_argument("--context", type=int, default=1, help="numeric SelectContext (1=SETUP_ACTIVE_POKEMON)")
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2026081560)
    parser.add_argument("--max-steps", type=int, default=3000)
    parser.add_argument("--examples", type=int, default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    sys.path.insert(0, str(ENGINE_PARENT))
    from cg.api import SelectContext, all_card_data, to_observation_class
    from cg.game import battle_finish, battle_select, battle_start

    cards = {card.cardId: card for card in all_card_data()}
    candidate = load_module("ab_candidate", args.candidate.resolve())
    baseline_shadow = load_module("ab_baseline", args.baseline.resolve())
    opponent = load_module("ab_opponent", args.baseline.resolve())
    deck_ids = load_deck_ids(args.deck.resolve())

    verdicts: Counter[str] = Counter()
    candidate_picks: Counter[str] = Counter()
    baseline_picks: Counter[str] = Counter()
    examples: list[dict] = []
    errors: list[str] = []

    for game in range(args.games):
        seat = game % 2
        seats = [candidate, opponent] if seat == 0 else [opponent, candidate]
        random.seed(args.seed + game)
        observation, start_data = battle_start(deck_ids, deck_ids)
        if observation is None:
            errors.append(f"game {game + 1}: battle_start failed: {start_data}")
            continue
        try:
            for _ in range(args.max_steps):
                parsed = to_observation_class(observation)
                if parsed.current is not None and parsed.current.result != -1:
                    break
                acting = parsed.current.yourIndex if parsed.current else 0
                module = seats[acting]
                module._MY_DECK = deck_ids
                choice = module.agent(observation)
                selection = parsed.select
                if acting == seat and selection is not None and selection.context == args.context:
                    baseline_shadow._MY_DECK = deck_ids
                    shadow = baseline_shadow.agent(observation)
                    hand = parsed.current.players[parsed.current.yourIndex].hand

                    def name_at(index: int) -> str:
                        option = selection.option[index]
                        if option.index is None or option.index >= len(hand):
                            return "UNRESOLVED"
                        return getattr(cards.get(hand[option.index].id), "name", "UNKNOWN")

                    verdicts["differs" if choice != shadow else "same"] += 1
                    for index in choice:
                        candidate_picks[name_at(index)] += 1
                    for index in shadow:
                        baseline_picks[name_at(index)] += 1
                    if len(examples) < args.examples:
                        examples.append({
                            "game": game + 1,
                            "offered": [name_at(i) for i in range(len(selection.option))],
                            "candidate": [name_at(i) for i in choice],
                            "baseline": [name_at(i) for i in shadow],
                        })
                observation = battle_select(choice)
        except Exception as exc:
            errors.append(f"game {game + 1}: {type(exc).__name__}: {exc}")
        finally:
            battle_finish()

    total = sum(verdicts.values())
    summary = {
        "candidate": str(args.candidate),
        "context": getattr(SelectContext(args.context), "name", str(args.context)),
        "games": args.games,
        "selections_in_context": total,
        "differs": verdicts["differs"],
        "same": verdicts["same"],
        "inert": total > 0 and verdicts["differs"] == 0,
        "no_observations": total == 0,
        "candidate_picked": dict(candidate_picks.most_common()),
        "baseline_picked": dict(baseline_picks.most_common()),
        "examples": examples,
        "errors": errors[:20],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    if args.output:
        args.output.resolve().write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 1 if summary["inert"] or summary["no_observations"] or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
