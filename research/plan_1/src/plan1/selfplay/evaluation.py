from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from plan1.config import load_config
from plan1.engine.api_loader import load_competition_api
from plan1.engine.conformance import read_deck
from plan1.model.inference import ModelInference
from plan1.model.policy_value import PolicyValueModel
from plan1.reproducibility import sha256_file
from plan1.search.agent import Plan1MCTSAgent
from plan1.search.validation import (
    BoundAgent,
    TimingSamples,
    TraceCollector,
    _load_game,
    _load_heuristic_module,
    play_game,
)


def promotion_decision(
    candidate_wins: int,
    champion_wins: int,
    draws: int,
    *,
    minimum_win_rate: float,
    safety_passed: bool,
) -> dict[str, Any]:
    decisive = candidate_wins + champion_wins
    rate = candidate_wins / decisive if decisive else None
    promoted = bool(
        safety_passed and decisive and candidate_wins > champion_wins
        and rate is not None and rate >= minimum_win_rate
    )
    return {
        "rule": "safety && candidate_wins > champion_wins && decisive_win_rate >= minimum",
        "minimum_decisive_win_rate": minimum_win_rate,
        "candidate_wins": candidate_wins,
        "champion_wins": champion_wins,
        "draws": draws,
        "decisive_games": decisive,
        "candidate_decisive_win_rate": rate,
        "safety_passed": safety_passed,
        "decision": "promoted" if promoted else "rejected",
        "promoted": promoted,
    }


def _agent(
    api: Any,
    deck: Sequence[int],
    opponent_deck: Sequence[int],
    checkpoint: Path,
    search_config: Path,
    name: str,
    traces: TraceCollector,
) -> tuple[BoundAgent, Any]:
    module = _load_heuristic_module(name, deck)
    agent = Plan1MCTSAgent(
        api,
        deck,
        load_config(search_config),
        opponent_deck=opponent_deck,
        fallback_policy=module._greedy_select,
        rollout_policy=module._greedy_select,
        action_observer=module._record_if_ability,
        trace_sink=traces,
        policy_value=ModelInference(PolicyValueModel.load(checkpoint)),
        puct_constant=1.0,
        learned_value_mix=0.10,
    )
    return BoundAgent(agent.act), module


def evaluate_candidate(
    candidate_checkpoint: Path,
    champion_checkpoint: Path,
    deck_path: Path,
    search_config: Path,
    *,
    games: int,
    max_steps: int,
    minimum_win_rate: float,
    iteration: int,
) -> dict[str, Any]:
    if games < 2 or games % 2:
        raise ValueError("candidate evaluation requires a positive even game count")
    api = load_competition_api()
    game = _load_game()
    deck = read_deck(deck_path)
    candidate_traces = TraceCollector()
    champion_traces = TraceCollector()
    candidate, candidate_module = _agent(
        api, deck, deck, candidate_checkpoint, search_config,
        f"phase8_i{iteration}_candidate", candidate_traces,
    )
    champion, champion_module = _agent(
        api, deck, deck, champion_checkpoint, search_config,
        f"phase8_i{iteration}_champion", champion_traces,
    )
    candidate_wins = champion_wins = draws = 0
    faults: Counter[str] = Counter()
    errors: list[str] = []
    outcomes: list[dict[str, Any]] = []
    candidate_timing = TimingSamples()
    champion_timing = TimingSamples()
    started = time.perf_counter()
    for game_index in range(games):
        candidate_first = game_index % 2 == 0
        agents = (candidate, champion) if candidate_first else (champion, candidate)
        modules = (
            (candidate_module, champion_module)
            if candidate_first else (champion_module, candidate_module)
        )
        outcome = play_game(game, api, agents, modules, (deck, deck), max_steps=max_steps)
        candidate.drain_into(candidate_timing)
        champion.drain_into(champion_timing)
        if outcome["fault"]:
            faults[outcome["fault"]] += 1
        if outcome["error"] and len(errors) < 50:
            errors.append(f"evaluation game {game_index}: {outcome['error']}")
        if outcome["result"] not in (0, 1):
            draws += 1
        elif (outcome["result"] == 0) == candidate_first:
            candidate_wins += 1
        else:
            champion_wins += 1
        outcomes.append({
            "evaluation_game_id": f"phase8-eval-i{iteration:03d}-g{game_index:04d}",
            "candidate_first": candidate_first,
            **outcome,
        })
    safety = not faults and not errors
    decision = promotion_decision(
        candidate_wins, champion_wins, draws,
        minimum_win_rate=minimum_win_rate,
        safety_passed=safety,
    )
    return {
        "iteration": iteration,
        "candidate_checkpoint": str(candidate_checkpoint.resolve()),
        "candidate_sha256": sha256_file(candidate_checkpoint),
        "champion_checkpoint": str(champion_checkpoint.resolve()),
        "champion_sha256": sha256_file(champion_checkpoint),
        "deck": str(deck_path.resolve()),
        "deck_sha256": sha256_file(deck_path),
        "games": games,
        "candidate_wins": candidate_wins,
        "champion_wins": champion_wins,
        "draws": draws,
        "candidate_timing": candidate_timing.summary(),
        "champion_timing": champion_timing.summary(),
        "candidate_search": candidate_traces.summary(),
        "champion_search": champion_traces.summary(),
        "faults": dict(sorted(faults.items())),
        "errors": errors,
        "outcomes": outcomes,
        "promotion": decision,
        "duration_seconds": time.perf_counter() - started,
    }
