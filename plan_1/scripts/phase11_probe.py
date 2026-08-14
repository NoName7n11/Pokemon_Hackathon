from __future__ import annotations

import argparse
import importlib.util
import json
import math
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


def _load(path: Path, name: str) -> tuple[Any, float]:
    started = time.perf_counter_ns()
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, (time.perf_counter_ns() - started) / 1_000_000


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def _prepare_package(source: Path, fault: str) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if fault == "none":
        return source, None
    temporary = tempfile.TemporaryDirectory(prefix="plan1-phase11-")
    destination = Path(temporary.name) / "submission"
    shutil.copytree(source, destination)
    model = destination / "model.json"
    if fault == "missing":
        model.unlink()
    elif fault == "corrupt":
        model.write_text("{not-json", encoding="utf-8")
    else:
        raise ValueError(f"unknown fault mode: {fault}")
    return destination, temporary


def _smoke(module: Any, import_ms: float) -> dict[str, Any]:
    deck = module.agent({"select": None})
    started = time.perf_counter_ns()
    status = module.deployment_status(initialize=True)
    initialize_ms = (time.perf_counter_ns() - started) / 1_000_000
    minimal = module.agent({"select": {"option": [{}], "minCount": 1, "maxCount": 1}})
    return {
        "mode": "smoke",
        "import_ms": import_ms,
        "initialize_ms": initialize_ms,
        "deck_count": len(deck),
        "deck_valid": len(deck) == 60 and all(isinstance(card_id, int) and card_id > 0 for card_id in deck),
        "minimal_fallback_action": minimal,
        "status": status,
        "passed": len(deck) == 60 and minimal == [0] and status["agent_status"].startswith("ready_"),
    }


def _reset_fallback(module: Any, deck: list[int]) -> None:
    fallback = module._fallback_module()
    fallback._MY_DECK = list(deck)
    fallback._live_ability_count = {}
    fallback._last_seen_turn = -1


def _games(module: Any, engine_root: Path, games: int, max_steps: int, import_ms: float) -> dict[str, Any]:
    import importlib

    api = importlib.import_module("cg.api")
    game = importlib.import_module("cg.game")
    opponent, _ = _load(engine_root / "main.py", "phase11_active_opponent")
    deck = module.read_deck_csv()
    opponent._MY_DECK = list(deck)
    outcomes = []
    decision_ms: list[float] = []
    faults: dict[str, int] = {}
    for game_index in range(games):
        package_seat = game_index % 2
        _reset_fallback(module, deck)
        opponent._MY_DECK = list(deck)
        opponent._live_ability_count = {}
        opponent._last_seen_turn = -1
        observation, error = game.battle_start(deck, deck)
        if observation is None:
            faults["battle_start"] = faults.get("battle_start", 0) + 1
            outcomes.append({"game": game_index, "result": 2, "steps": 0, "error": str(error)})
            continue
        result = 2
        fault = None
        try:
            for step in range(max_steps):
                current = api.to_observation_class(observation)
                if current.current is not None and current.current.result != -1:
                    result = int(current.current.result)
                    break
                seat = current.current.yourIndex if current.current is not None else 0
                if current.select is None:
                    action = deck
                elif seat == package_seat:
                    started = time.perf_counter_ns()
                    action = module.agent(observation)
                    decision_ms.append((time.perf_counter_ns() - started) / 1_000_000)
                else:
                    action = opponent.agent(observation)
                try:
                    observation = game.battle_select(action)
                except Exception as exc:
                    fault = f"battle_select:{type(exc).__name__}:{exc}"
                    result = 1 - seat
                    break
            else:
                fault = "step_limit"
            outcomes.append({"game": game_index, "package_seat": package_seat, "result": result, "steps": step + 1, "fault": fault})
            if fault:
                faults[fault] = faults.get(fault, 0) + 1
        finally:
            game.battle_finish()
    timing = {
        "count": len(decision_ms),
        "median_ms": statistics.median(decision_ms) if decision_ms else None,
        "p95_ms": _percentile(decision_ms, 0.95),
        "max_ms": max(decision_ms) if decision_ms else None,
    }
    return {
        "mode": "games",
        "import_ms": import_ms,
        "games": games,
        "completed_games": sum(item.get("fault") is None for item in outcomes),
        "faults": faults,
        "decision_timing": timing,
        "status": module.deployment_status(),
        "outcomes": outcomes,
        "passed": len(outcomes) == games and not faults and bool(decision_ms),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("engine_root", type=Path)
    parser.add_argument("--fault", choices=("none", "missing", "corrupt"), default="none")
    parser.add_argument("--games", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=3000)
    args = parser.parse_args()
    package, temporary = _prepare_package(args.package.resolve(), args.fault)
    try:
        sys.path.insert(0, str(args.engine_root.resolve()))
        sys.path.insert(0, str(package))
        module, import_ms = _load(package / "main.py", f"phase11_package_{args.fault}")
        result = (
            _games(module, args.engine_root.resolve(), args.games, args.max_steps, import_ms)
            if args.games
            else _smoke(module, import_ms)
        )
        result["fault_injection"] = args.fault
        print(json.dumps(result, separators=(",", ":")))
        return 0 if result["passed"] else 1
    finally:
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
