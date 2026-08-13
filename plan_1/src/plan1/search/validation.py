from __future__ import annotations

import importlib
import importlib.util
import math
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from plan1.config import Plan1Config, load_config
from plan1.engine.api_loader import load_competition_api
from plan1.engine.conformance import read_deck
from plan1.paths import CONFIG_ROOT, ENGINE_PARENT
from plan1.reproducibility import sha256_file, write_json_atomic
from plan1.search.agent import Plan1MCTSAgent
from plan1.search.mcts import SearchResult


@dataclass(slots=True)
class TimingSamples:
    values_ms: list[float]

    def __init__(self) -> None:
        self.values_ms = []

    def add(self, elapsed_ms: float) -> None:
        self.values_ms.append(elapsed_ms)

    def summary(self) -> dict[str, float | int | None]:
        if not self.values_ms:
            return {"count": 0, "median_ms": None, "p95_ms": None, "max_ms": None}
        ordered = sorted(self.values_ms)
        p95 = ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]
        return {
            "count": len(ordered),
            "median_ms": statistics.median(ordered),
            "p95_ms": p95,
            "max_ms": ordered[-1],
        }


class TraceCollector:
    def __init__(self, sample_limit: int = 25) -> None:
        self.search_times = TimingSamples()
        self.stops: Counter[str] = Counter()
        self.fallbacks: Counter[str] = Counter()
        self.errors: Counter[str] = Counter()
        self.simulations = 0
        self.completed_simulations = 0
        self.native_steps = 0
        self.max_depth = 0
        self.searched_decisions = 0
        self.full_root_coverage = 0
        self.chose_non_fallback = 0
        self.hard_deadline_overruns = 0
        self.samples: list[dict[str, Any]] = []
        self.sample_limit = sample_limit

    def __call__(self, result: SearchResult) -> None:
        trace = result.trace
        self.searched_decisions += 1
        self.search_times.add(trace.elapsed_ms)
        self.stops[trace.stopped_reason] += 1
        if trace.fallback_used:
            self.fallbacks[trace.fallback_reason or "unknown"] += 1
        self.errors.update(trace.errors)
        self.simulations += trace.simulations
        self.completed_simulations += trace.completed_simulations
        self.native_steps += trace.native_steps
        self.max_depth = max(self.max_depth, trace.max_depth_reached)
        self.full_root_coverage += int(
            trace.generated_root_actions > 0 and len(trace.root_edges) == trace.generated_root_actions
        )
        self.chose_non_fallback += int(result.action != result.fallback_action)
        self.hard_deadline_overruns += int(trace.hard_deadline_exceeded)
        if len(self.samples) < self.sample_limit:
            self.samples.append(asdict(trace))

    def summary(self) -> dict[str, Any]:
        return {
            "searched_decisions": self.searched_decisions,
            "timing": self.search_times.summary(),
            "stopped_reasons": dict(sorted(self.stops.items())),
            "fallback_reasons": dict(sorted(self.fallbacks.items())),
            "trace_errors": dict(sorted(self.errors.items())),
            "simulations": self.simulations,
            "completed_simulations": self.completed_simulations,
            "native_steps": self.native_steps,
            "max_depth_reached": self.max_depth,
            "full_root_coverage": self.full_root_coverage,
            "full_root_coverage_rate": self.full_root_coverage / self.searched_decisions if self.searched_decisions else None,
            "chose_non_fallback": self.chose_non_fallback,
            "chose_non_fallback_rate": self.chose_non_fallback / self.searched_decisions if self.searched_decisions else None,
            "hard_deadline_overruns": self.hard_deadline_overruns,
            "hard_deadline_overrun_rate": (
                self.hard_deadline_overruns / self.searched_decisions
                if self.searched_decisions
                else None
            ),
            "samples": self.samples,
        }


class BoundAgent:
    def __init__(self, act: Callable[[dict[str, Any]], list[int]]) -> None:
        self.act = act
        self.timing = TimingSamples()

    def __call__(self, observation: dict[str, Any]) -> list[int]:
        started = time.perf_counter_ns()
        action = self.act(observation)
        self.timing.add((time.perf_counter_ns() - started) / 1_000_000)
        return action

    def drain_into(self, target: TimingSamples) -> None:
        target.values_ms.extend(self.timing.values_ms)
        self.timing.values_ms.clear()


def _load_heuristic_module(name: str, deck: Sequence[int]) -> Any:
    path = ENGINE_PARENT / "main.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load heuristic module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._MY_DECK = list(deck)
    return module


def _reset_heuristic(module: Any, deck: Sequence[int]) -> None:
    module._MY_DECK = list(deck)
    module._live_ability_count = {}
    module._last_seen_turn = -1


def _mcts_agent(
    api: Any,
    deck: Sequence[int],
    config: Plan1Config,
    *,
    horizon_turns: int,
    module_name: str,
    traces: TraceCollector,
) -> tuple[BoundAgent, Any]:
    module = _load_heuristic_module(module_name, deck)
    agent = Plan1MCTSAgent(
        api,
        deck,
        config,
        opponent_deck=deck,
        fallback_policy=module._greedy_select,
        rollout_policy=module._greedy_select,
        action_observer=module._record_if_ability,
        trace_sink=traces,
        horizon_turns=horizon_turns,
    )
    return BoundAgent(agent.act), module


def _baseline_agent(deck: Sequence[int], module_name: str) -> tuple[BoundAgent, Any]:
    module = _load_heuristic_module(module_name, deck)

    def act(observation: dict[str, Any]) -> list[int]:
        module._MY_DECK = list(deck)
        return list(module.agent(observation))

    return BoundAgent(act), module


def _load_game() -> Any:
    load_competition_api()
    engine_text = str(ENGINE_PARENT.resolve())
    if engine_text not in sys.path:
        sys.path.insert(0, engine_text)
    return importlib.import_module("cg.game")


def play_game(
    game: Any,
    api: Any,
    agents: Sequence[BoundAgent],
    modules: Sequence[Any],
    decks: Sequence[Sequence[int]],
    *,
    max_steps: int,
) -> dict[str, Any]:
    for module, deck in zip(modules, decks):
        _reset_heuristic(module, deck)
    observation, start_data = game.battle_start(list(decks[0]), list(decks[1]))
    if observation is None:
        return {"result": 2, "steps": 0, "fault": "battle_start", "error": str(start_data)}
    try:
        for step in range(max_steps):
            current = api.to_observation_class(observation)
            if current.current is not None and current.current.result != -1:
                return {"result": int(current.current.result), "steps": step, "fault": None, "error": None}
            actor = current.current.yourIndex if current.current is not None else 0
            try:
                action = list(decks[actor]) if current.select is None else agents[actor](observation)
            except Exception as exc:
                return {
                    "result": 1 - actor,
                    "steps": step,
                    "fault": f"agent_crash:{actor}",
                    "error": f"{type(exc).__name__}:{exc}",
                }
            try:
                observation = game.battle_select(action)
            except (IndexError, ValueError) as exc:
                return {
                    "result": 1 - actor,
                    "steps": step,
                    "fault": f"illegal_action:{actor}",
                    "error": f"{type(exc).__name__}:{exc}",
                }
            except Exception as exc:
                return {
                    "result": 1 - actor,
                    "steps": step,
                    "fault": f"engine_or_agent:{actor}",
                    "error": f"{type(exc).__name__}:{exc}",
                }
        final = api.to_observation_class(observation)
        if final.current is not None and final.current.result != -1:
            return {
                "result": int(final.current.result),
                "steps": max_steps,
                "fault": None,
                "error": None,
            }
        return {"result": 2, "steps": max_steps, "fault": "timeout", "error": None}
    finally:
        game.battle_finish()


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


def validation_config(
    base: Plan1Config,
    *,
    time_budget_ms: int,
    cleanup_reserve_ms: int,
    simulations: int,
    nodes: int,
    candidates: int,
) -> Plan1Config:
    return replace(
        base,
        search=replace(
            base.search,
            time_budget_ms=time_budget_ms,
            max_simulations=simulations,
            max_nodes=nodes,
            max_candidates=candidates,
        ),
        safety=replace(base.safety, cleanup_reserve_ms=cleanup_reserve_ms),
    )


def run_soak(
    deck_paths: Sequence[Path],
    *,
    total_games: int,
    max_steps: int,
    config: Plan1Config,
    horizon_turns: int,
    p95_limit_ms: float,
    max_limit_ms: float,
    hard_overrun_rate_limit: float,
    report_path: Path,
) -> dict[str, Any]:
    if total_games < len(deck_paths) or max_steps < 1:
        raise ValueError("total_games must cover every deck and max_steps must be positive")
    if not 0 <= hard_overrun_rate_limit <= 1:
        raise ValueError("hard_overrun_rate_limit must be in [0, 1]")
    api = load_competition_api()
    game = _load_game()
    decks = [(path, read_deck(path)) for path in deck_paths]
    traces = TraceCollector()
    results: list[dict[str, Any]] = []
    agent_timings = TimingSamples()
    faults: Counter[str] = Counter()
    errors: list[str] = []
    started = time.perf_counter()
    agent_pairs: dict[str, tuple[BoundAgent, Any, BoundAgent, Any]] = {}
    for deck_path, deck in decks:
        key = deck_path.name
        first, module0 = _mcts_agent(
            api, deck, config, horizon_turns=horizon_turns, module_name=f"plan1_soak_a_{key}", traces=traces
        )
        second, module1 = _mcts_agent(
            api, deck, config, horizon_turns=horizon_turns, module_name=f"plan1_soak_b_{key}", traces=traces
        )
        agent_pairs[key] = (first, module0, second, module1)
    for game_index in range(total_games):
        deck_path, deck = decks[game_index % len(decks)]
        first, module0, second, module1 = agent_pairs[deck_path.name]
        outcome = play_game(game, api, (first, second), (module0, module1), (deck, deck), max_steps=max_steps)
        first.drain_into(agent_timings)
        second.drain_into(agent_timings)
        if outcome["fault"]:
            faults[outcome["fault"]] += 1
        if outcome["error"] and len(errors) < 50:
            errors.append(f"game {game_index} {deck_path.name}: {outcome['error']}")
        results.append({"game_index": game_index, "deck": deck_path.name, **outcome})
    timing = agent_timings.summary()
    trace_summary = traces.summary()
    completed = sum(result["fault"] is None for result in results)
    deck_results = {
        deck_path.name: {
            "games": sum(result["deck"] == deck_path.name for result in results),
            "completed_games": sum(
                result["deck"] == deck_path.name and result["fault"] is None for result in results
            ),
            "faults": dict(
                sorted(
                    Counter(
                        result["fault"]
                        for result in results
                        if result["deck"] == deck_path.name and result["fault"] is not None
                    ).items()
                )
            ),
        }
        for deck_path, _ in decks
    }
    passed = (
        completed == total_games
        and not faults
        and not errors
        and traces.searched_decisions > 0
        and not traces.errors
        and traces.hard_deadline_overruns / traces.searched_decisions <= hard_overrun_rate_limit
        and timing["p95_ms"] is not None
        and timing["p95_ms"] <= p95_limit_ms
        and timing["max_ms"] is not None
        and timing["max_ms"] <= max_limit_ms
    )
    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "soak",
        "games": total_games,
        "completed_games": completed,
        "max_steps": max_steps,
        "horizon_turns": horizon_turns,
        "runtime_limits_ms": {"p95": p95_limit_ms, "max": max_limit_ms},
        "hard_overrun_rate_limit": hard_overrun_rate_limit,
        "config": asdict(config),
        "decks": [{"path": str(path.resolve()), "sha256": sha256_file(path)} for path, _ in decks],
        "deck_results": deck_results,
        "timeout_samples": [
            {
                "game_index": result["game_index"],
                "deck": result["deck"],
                "steps": result["steps"],
            }
            for result in results
            if result["fault"] == "timeout"
        ][:25],
        "agent_timing": timing,
        "search": trace_summary,
        "faults": dict(sorted(faults.items())),
        "errors": errors,
        "duration_seconds": time.perf_counter() - started,
        "passed": passed,
    }
    write_json_atomic(report_path, report)
    return report


def run_horizon_ablation(
    deck_path: Path,
    *,
    games: int,
    max_steps: int,
    config: Plan1Config,
    report_path: Path,
) -> dict[str, Any]:
    if games < 2 or games % 2:
        raise ValueError("horizon ablation games must be a positive even number")
    api = load_competition_api()
    game = _load_game()
    deck = read_deck(deck_path)
    traces_a = TraceCollector()
    traces_b = TraceCollector()
    stage_a, module_a = _mcts_agent(
        api, deck, config, horizon_turns=0, module_name="plan1_horizon_a", traces=traces_a
    )
    stage_b, module_b = _mcts_agent(
        api, deck, config, horizon_turns=1, module_name="plan1_horizon_b", traces=traces_b
    )
    stage_a_wins = stage_b_wins = draws = 0
    faults: Counter[str] = Counter()
    errors: list[str] = []
    timing_a = TimingSamples()
    timing_b = TimingSamples()
    started = time.perf_counter()
    for game_index in range(games):
        a_first = game_index % 2 == 0
        agents = (stage_a, stage_b) if a_first else (stage_b, stage_a)
        modules = (module_a, module_b) if a_first else (module_b, module_a)
        outcome = play_game(game, api, agents, modules, (deck, deck), max_steps=max_steps)
        stage_a.drain_into(timing_a)
        stage_b.drain_into(timing_b)
        if outcome["fault"]:
            faults[outcome["fault"]] += 1
        if outcome["error"] and len(errors) < 50:
            errors.append(f"game {game_index}: {outcome['error']}")
        if outcome["result"] not in (0, 1):
            draws += 1
        elif (outcome["result"] == 0) == a_first:
            stage_a_wins += 1
        else:
            stage_b_wins += 1
    decisive = stage_a_wins + stage_b_wins
    z_score, p_value = head_to_head_z(stage_b_wins, stage_a_wins)
    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "horizon_ablation",
        "deck": str(deck_path.resolve()),
        "deck_sha256": sha256_file(deck_path),
        "games": games,
        "stage_a_horizon_turns": 0,
        "stage_b_horizon_turns": 1,
        "stage_a_wins": stage_a_wins,
        "stage_b_wins": stage_b_wins,
        "draws": draws,
        "stage_b_decisive_win_rate": stage_b_wins / decisive if decisive else None,
        "stage_b_wilson_95": wilson_interval(stage_b_wins, decisive),
        "z_score": z_score,
        "p_value": p_value,
        "config": asdict(config),
        "stage_a_timing": timing_a.summary(),
        "stage_b_timing": timing_b.summary(),
        "stage_a_search": traces_a.summary(),
        "stage_b_search": traces_b.summary(),
        "faults": dict(sorted(faults.items())),
        "errors": errors,
        "duration_seconds": time.perf_counter() - started,
        "passed_safety": not faults and not errors and not traces_a.errors and not traces_b.errors,
        "stage_b_improved": bool(
            decisive and stage_b_wins > stage_a_wins and p_value is not None and p_value < 0.05
        ),
    }
    write_json_atomic(report_path, report)
    return report


def run_ablation(
    deck_path: Path,
    *,
    games: int,
    max_steps: int,
    config: Plan1Config,
    horizon_turns: int,
    report_path: Path,
) -> dict[str, Any]:
    if games < 2 or games % 2:
        raise ValueError("ablation games must be a positive even number")
    api = load_competition_api()
    game = _load_game()
    deck = read_deck(deck_path)
    traces = TraceCollector()
    mcts_wins = baseline_wins = draws = 0
    faults: Counter[str] = Counter()
    errors: list[str] = []
    mcts_timing = TimingSamples()
    baseline_timing = TimingSamples()
    started = time.perf_counter()
    mcts, mcts_module = _mcts_agent(
        api, deck, config, horizon_turns=horizon_turns, module_name="plan1_ablate_m", traces=traces
    )
    baseline, baseline_module = _baseline_agent(deck, "plan1_ablate_b")
    for game_index in range(games):
        mcts_first = game_index % 2 == 0
        agents = (mcts, baseline) if mcts_first else (baseline, mcts)
        modules = (mcts_module, baseline_module) if mcts_first else (baseline_module, mcts_module)
        outcome = play_game(game, api, agents, modules, (deck, deck), max_steps=max_steps)
        mcts.drain_into(mcts_timing)
        baseline.drain_into(baseline_timing)
        if outcome["fault"]:
            faults[outcome["fault"]] += 1
        if outcome["error"] and len(errors) < 50:
            errors.append(f"game {game_index}: {outcome['error']}")
        if outcome["result"] not in (0, 1):
            draws += 1
        elif (outcome["result"] == 0) == mcts_first:
            mcts_wins += 1
        else:
            baseline_wins += 1
    decisive = mcts_wins + baseline_wins
    z_score, p_value = head_to_head_z(mcts_wins, baseline_wins)
    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "ablation",
        "deck": str(deck_path.resolve()),
        "deck_sha256": sha256_file(deck_path),
        "games": games,
        "horizon_turns": horizon_turns,
        "mcts_wins": mcts_wins,
        "baseline_wins": baseline_wins,
        "draws": draws,
        "mcts_decisive_win_rate": mcts_wins / decisive if decisive else None,
        "mcts_wilson_95": wilson_interval(mcts_wins, decisive),
        "z_score": z_score,
        "p_value": p_value,
        "config": asdict(config),
        "mcts_timing": mcts_timing.summary(),
        "baseline_timing": baseline_timing.summary(),
        "search": traces.summary(),
        "faults": dict(sorted(faults.items())),
        "errors": errors,
        "duration_seconds": time.perf_counter() - started,
        "passed_safety": not faults and not errors,
        "improved": bool(decisive and mcts_wins > baseline_wins and p_value is not None and p_value < 0.05),
    }
    write_json_atomic(report_path, report)
    return report


def load_baseline_config() -> Plan1Config:
    return load_config(CONFIG_ROOT / "mcts_baseline.json")
