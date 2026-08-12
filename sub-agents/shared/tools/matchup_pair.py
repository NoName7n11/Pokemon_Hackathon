from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import ENGINE_PARENT, load_deck_ids, write_json_atomic


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Python module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "agent", None)):
        raise ValueError(f"{path} does not define callable agent()")
    return module


def wilson_interval(wins: int, total: int, z: float = 1.96) -> list[float]:
    if total == 0:
        return [0.0, 0.0]
    p = wins / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [center - half, center + half]


def head_to_head_z(wins: int, losses: int) -> tuple[float | None, float | None]:
    decisive = wins + losses
    if decisive == 0:
        return None, None
    z_score = (wins / decisive - 0.5) / math.sqrt(0.25 / decisive)
    return z_score, math.erfc(abs(z_score) / math.sqrt(2))


def new_timing() -> dict[str, float | int]:
    return {"total_ms": 0.0, "decisions": 0, "max_ms": 0.0}


def bound_agent(module, deck_ids: list[int], timing: dict[str, float | int]):
    def act(observation):
        module._MY_DECK = deck_ids
        started = time.perf_counter()
        selection = module.agent(observation)
        elapsed_ms = (time.perf_counter() - started) * 1000
        timing["total_ms"] += elapsed_ms
        timing["decisions"] += 1
        timing["max_ms"] = max(float(timing["max_ms"]), elapsed_ms)
        return selection

    return act


def play_one(
    module_a,
    module_b,
    deck_a: list[int],
    deck_b: list[int],
    a_first: bool,
    max_steps: int,
) -> dict[str, Any]:
    from cg.api import to_observation_class
    from cg.game import battle_finish, battle_select, battle_start

    timings = {"a": new_timing(), "b": new_timing()}
    agents_by_pair = {
        "a": bound_agent(module_a, deck_a, timings["a"]),
        "b": bound_agent(module_b, deck_b, timings["b"]),
    }
    seat_pairs = ["a", "b"] if a_first else ["b", "a"]
    seat_decks = [deck_a, deck_b] if a_first else [deck_b, deck_a]
    observation = None
    try:
        observation, start_data = battle_start(seat_decks[0], seat_decks[1])
        if observation is None:
            return {
                "outcome": "engine_crash",
                "steps": 0,
                "fault_pair": None,
                "fault_kind": "battle_start",
                "error": f"battle_start failed: {start_data}",
                "timings": timings,
            }

        for step in range(max_steps):
            current = to_observation_class(observation)
            if current.current is not None and current.current.result != -1:
                result = current.current.result
                outcome = f"{seat_pairs[result]}_win" if result in (0, 1) else "draw"
                return {
                    "outcome": outcome,
                    "steps": step,
                    "fault_pair": None,
                    "fault_kind": None,
                    "error": None,
                    "timings": timings,
                }

            player = current.current.yourIndex if current.current else 0
            pair = seat_pairs[player]
            try:
                selection = agents_by_pair[pair](observation)
            except Exception as exc:
                return {
                    "outcome": f"{'b' if pair == 'a' else 'a'}_win",
                    "steps": step,
                    "fault_pair": pair,
                    "fault_kind": "crash",
                    "error": f"seat {player}: {type(exc).__name__}: {exc}",
                    "timings": timings,
                }

            try:
                observation = battle_select(selection)
            except (IndexError, ValueError) as exc:
                return {
                    "outcome": f"{'b' if pair == 'a' else 'a'}_win",
                    "steps": step,
                    "fault_pair": pair,
                    "fault_kind": "illegal_action",
                    "error": f"seat {player}: {type(exc).__name__}: {exc}",
                    "timings": timings,
                }
            except Exception as exc:
                return {
                    "outcome": f"{'b' if pair == 'a' else 'a'}_win",
                    "steps": step,
                    "fault_pair": pair,
                    "fault_kind": "crash",
                    "error": f"seat {player}: {type(exc).__name__}: {exc}",
                    "timings": timings,
                }

        return {
            "outcome": "timeout",
            "steps": max_steps,
            "fault_pair": None,
            "fault_kind": None,
            "error": None,
            "timings": timings,
        }
    finally:
        if observation is not None:
            battle_finish()


def summarize_timing(timing: dict[str, float | int]) -> dict[str, float | int | None]:
    decisions = int(timing["decisions"])
    return {
        "decisions": decisions,
        "average_ms": float(timing["total_ms"]) / decisions if decisions else None,
        "max_ms": float(timing["max_ms"]) if decisions else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seat-balanced match between two complete deck-agent pairs.")
    parser.add_argument("--agent-a", required=True, type=Path)
    parser.add_argument("--deck-a", required=True, type=Path)
    parser.add_argument("--name-a", required=True)
    parser.add_argument("--version-a", required=True)
    parser.add_argument("--agent-b", required=True, type=Path)
    parser.add_argument("--deck-b", required=True, type=Path)
    parser.add_argument("--name-b", required=True)
    parser.add_argument("--version-b", required=True)
    parser.add_argument("--games-per-seat", required=True, type=int)
    parser.add_argument("--max-steps", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if args.games_per_seat <= 0 or args.max_steps <= 0:
        raise ValueError("games-per-seat and max-steps must be positive")
    if args.name_a == args.name_b:
        raise ValueError("pair names must be distinct")
    if not (ENGINE_PARENT / "cg").is_dir():
        raise RuntimeError(f"competition engine package not found: {ENGINE_PARENT / 'cg'}")
    sys.path.insert(0, str(ENGINE_PARENT))

    started_at = utc_now()
    started = time.perf_counter()
    random.seed(args.seed)
    module_a = load_module("plan2_tournament_a", args.agent_a.resolve())
    module_b = load_module("plan2_tournament_b", args.agent_b.resolve())
    deck_a = load_deck_ids(args.deck_a.resolve())
    deck_b = load_deck_ids(args.deck_b.resolve())

    counts = {"a_win": 0, "b_win": 0, "draw": 0, "timeout": 0, "engine_crash": 0}
    faults = {
        "a": {"crashes": 0, "illegal_actions": 0},
        "b": {"crashes": 0, "illegal_actions": 0},
    }
    orientations = {
        "a_first": {"games": 0, "a_wins": 0, "b_wins": 0, "draws": 0},
        "b_first": {"games": 0, "a_wins": 0, "b_wins": 0, "draws": 0},
    }
    aggregate_timing = {"a": new_timing(), "b": new_timing()}
    errors: list[str] = []
    total_steps = 0
    total_games = args.games_per_seat * 2

    for game_index in range(total_games):
        a_first = game_index % 2 == 0
        orientation = orientations["a_first" if a_first else "b_first"]
        outcome = play_one(module_a, module_b, deck_a, deck_b, a_first, args.max_steps)
        counts[outcome["outcome"]] += 1
        orientation["games"] += 1
        if outcome["outcome"] == "a_win":
            orientation["a_wins"] += 1
        elif outcome["outcome"] == "b_win":
            orientation["b_wins"] += 1
        else:
            orientation["draws"] += 1

        fault_pair = outcome["fault_pair"]
        fault_kind = outcome["fault_kind"]
        if fault_pair and fault_kind == "crash":
            faults[fault_pair]["crashes"] += 1
        elif fault_pair and fault_kind == "illegal_action":
            faults[fault_pair]["illegal_actions"] += 1

        total_steps += int(outcome["steps"])
        for pair in ("a", "b"):
            timing = outcome["timings"][pair]
            aggregate_timing[pair]["total_ms"] += float(timing["total_ms"])
            aggregate_timing[pair]["decisions"] += int(timing["decisions"])
            aggregate_timing[pair]["max_ms"] = max(
                float(aggregate_timing[pair]["max_ms"]), float(timing["max_ms"])
            )
        if outcome["error"] and len(errors) < 20:
            errors.append(f"game {game_index + 1}: {outcome['error']}")

    decisive = counts["a_win"] + counts["b_win"]
    neutral_draws = counts["draw"] + counts["timeout"] + counts["engine_crash"]
    z_score, p_value = head_to_head_z(counts["a_win"], counts["b_win"])
    result = {
        "schema_version": 1,
        "stage": "tournament",
        "pair_a": {
            "name": args.name_a,
            "version": args.version_a,
            "agent": str(args.agent_a.resolve()),
            "deck": str(args.deck_a.resolve()),
        },
        "pair_b": {
            "name": args.name_b,
            "version": args.version_b,
            "agent": str(args.agent_b.resolve()),
            "deck": str(args.deck_b.resolve()),
        },
        "seed_set": str(args.seed),
        "games_per_seat": args.games_per_seat,
        "games": total_games,
        "a_wins": counts["a_win"],
        "b_wins": counts["b_win"],
        "draws": neutral_draws,
        "timeouts": counts["timeout"],
        "engine_crashes": counts["engine_crash"],
        "faults": faults,
        "orientations": orientations,
        "a_win_rate": counts["a_win"] / total_games,
        "a_decisive_win_rate": counts["a_win"] / decisive if decisive else None,
        "a_confidence_interval": wilson_interval(counts["a_win"], decisive),
        "z_score": z_score,
        "p_value": p_value,
        "average_steps": total_steps / total_games,
        "decision_time": {
            "a": summarize_timing(aggregate_timing["a"]),
            "b": summarize_timing(aggregate_timing["b"]),
        },
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_seconds": time.perf_counter() - started,
        "errors": errors,
    }
    write_json_atomic(args.output.resolve(), result)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 1 if counts["engine_crash"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
