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
    """Normal approximation to the two-sided 50% head-to-head null.

    Draws and timeouts are excluded because neither agent won that game.
    """
    decisive = wins + losses
    if decisive == 0:
        return None, None
    z_score = (wins / decisive - 0.5) / math.sqrt(0.25 / decisive)
    p_value = math.erfc(abs(z_score) / math.sqrt(2))
    return z_score, p_value


def bound_agent(module, deck_ids: list[int], timing: dict[str, float | int]):
    def act(observation):
        module._MY_DECK = deck_ids
        started = time.perf_counter()
        selection = module.agent(observation)
        elapsed_ms = (time.perf_counter() - started) * 1000
        timing["total_ms"] += elapsed_ms
        timing["decisions"] += 1
        timing["max_ms"] = max(timing["max_ms"], elapsed_ms)
        return selection

    return act


def play_one(candidate, baseline, deck_ids, candidate_first: bool, max_steps: int):
    from cg.api import to_observation_class
    from cg.game import battle_finish, battle_select, battle_start

    candidate_timing = {"total_ms": 0.0, "decisions": 0, "max_ms": 0.0}
    baseline_timing = {"total_ms": 0.0, "decisions": 0, "max_ms": 0.0}
    candidate_agent = bound_agent(candidate, deck_ids, candidate_timing)
    baseline_agent = bound_agent(baseline, deck_ids, baseline_timing)
    agents = [candidate_agent, baseline_agent] if candidate_first else [baseline_agent, candidate_agent]

    observation, start_data = battle_start(deck_ids, deck_ids)
    if observation is None:
        return "crash", 0, candidate_timing, f"battle_start failed: {start_data}"
    try:
        for step in range(max_steps):
            current = to_observation_class(observation)
            if current.current is not None and current.current.result != -1:
                winner = current.current.result
                candidate_seat = 0 if candidate_first else 1
                return ("win" if winner == candidate_seat else "loss"), step, candidate_timing, None
            player = current.current.yourIndex if current.current else 0
            try:
                selection = agents[player](observation)
            except Exception as exc:
                candidate_seat = 0 if candidate_first else 1
                classification = "crash" if player == candidate_seat else "win"
                return classification, step, candidate_timing, f"seat {player}: {type(exc).__name__}: {exc}"
            try:
                observation = battle_select(selection)
            except (IndexError, ValueError) as exc:
                candidate_seat = 0 if candidate_first else 1
                classification = "illegal_action" if player == candidate_seat else "win"
                return classification, step, candidate_timing, f"seat {player}: {type(exc).__name__}: {exc}"
            except Exception as exc:
                candidate_seat = 0 if candidate_first else 1
                classification = "crash" if player == candidate_seat else "win"
                return classification, step, candidate_timing, f"seat {player}: {type(exc).__name__}: {exc}"
        return "timeout", max_steps, candidate_timing, None
    finally:
        battle_finish()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seat-balanced benchmark of a candidate and baseline agent.")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--deck", required=True, type=Path)
    parser.add_argument("--games", required=True, type=int)
    parser.add_argument("--max-steps", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--specialist", required=True)
    parser.add_argument("--candidate-version", required=True)
    parser.add_argument("--baseline-version", required=True)
    parser.add_argument("--stage", required=True, choices=("smoke", "screening", "main", "confirmation"))
    args = parser.parse_args()

    if args.games <= 0 or args.max_steps <= 0:
        raise ValueError("games and max-steps must be positive")
    if not (ENGINE_PARENT / "cg").is_dir():
        raise RuntimeError(f"competition engine package not found: {ENGINE_PARENT / 'cg'}")
    sys.path.insert(0, str(ENGINE_PARENT))

    started_at = utc_now()
    started = time.perf_counter()
    random.seed(args.seed)
    candidate = load_module("plan2_candidate", args.candidate.resolve())
    baseline = load_module("plan2_baseline", args.baseline.resolve())
    deck_ids = load_deck_ids(args.deck.resolve())

    counts = {"win": 0, "loss": 0, "timeout": 0, "illegal_action": 0, "crash": 0}
    errors: list[str] = []
    total_steps = 0
    total_decision_ms = 0.0
    total_decisions = 0
    max_decision_ms = 0.0
    for game_index in range(args.games):
        outcome, steps, timing, error = play_one(
            candidate,
            baseline,
            deck_ids,
            candidate_first=game_index % 2 == 0,
            max_steps=args.max_steps,
        )
        counts[outcome] += 1
        total_steps += steps
        total_decision_ms += float(timing["total_ms"])
        total_decisions += int(timing["decisions"])
        max_decision_ms = max(max_decision_ms, float(timing["max_ms"]))
        if error and len(errors) < 10:
            errors.append(f"game {game_index + 1}: {error}")

    draws = counts["timeout"] + counts["illegal_action"] + counts["crash"]
    z_score, p_value = head_to_head_z(counts["win"], counts["loss"])
    result = {
        "specialist": args.specialist,
        "candidate_version": args.candidate_version,
        "baseline_version": args.baseline_version,
        "opponent": "specialist_previous",
        "stage": args.stage,
        "seed_set": str(args.seed),
        "games": args.games,
        "wins": counts["win"],
        "losses": counts["loss"],
        "draws": draws,
        "timeouts": counts["timeout"],
        "illegal_actions": counts["illegal_action"],
        "crashes": counts["crash"],
        "average_steps": total_steps / args.games,
        "average_decision_time_ms": total_decision_ms / total_decisions if total_decisions else None,
        "max_decision_time_ms": max_decision_ms if total_decisions else None,
        "win_rate": counts["win"] / args.games,
        "confidence_interval": wilson_interval(counts["win"], args.games),
        "z_score": z_score,
        "p_value": p_value,
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_seconds": time.perf_counter() - started,
        "errors": errors,
    }
    write_json_atomic(args.output.resolve(), result)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if not counts["crash"] and not counts["illegal_action"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
