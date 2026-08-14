from __future__ import annotations

import importlib.util
import itertools
import json
import multiprocessing
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from plan1.config import load_config
from plan1.engine.api_loader import load_competition_api
from plan1.engine.conformance import read_deck
from plan1.league.analysis import analyze_league
from plan1.league.config import DeckSpec, LeagueConfig, PolicySpec
from plan1.model.inference import ModelInference
from plan1.model.policy_value import PolicyValueModel
from plan1.paths import ARTIFACT_ROOT
from plan1.reproducibility import sha256_file, write_json_atomic
from plan1.search.agent import Plan1MCTSAgent
from plan1.search.validation import (
    BoundAgent,
    TimingSamples,
    TraceCollector,
    _load_game,
    _load_heuristic_module,
    play_game,
)


def _load_module(path: Path, name: str, deck: Sequence[int]) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load specialist module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._MY_DECK = list(deck)
    return module


def _bind_policy(
    api: Any,
    policy: PolicySpec,
    deck: Sequence[int],
    opponent_deck: Sequence[int],
    search_config: Path,
    module_name: str,
) -> tuple[BoundAgent, Any, TraceCollector | None]:
    if policy.kind == "module":
        module = _load_module(policy.path, module_name, deck)

        def act(observation: dict[str, Any]) -> list[int]:
            module._MY_DECK = list(deck)
            return list(module.agent(observation))

        return BoundAgent(act), module, None
    module = _load_heuristic_module(module_name, deck)
    traces = TraceCollector(sample_limit=5)
    agent = Plan1MCTSAgent(
        api,
        deck,
        load_config(search_config),
        opponent_deck=opponent_deck,
        fallback_policy=module._greedy_select,
        rollout_policy=module._greedy_select,
        action_observer=module._record_if_ability,
        trace_sink=traces,
        policy_value=ModelInference(PolicyValueModel.load(policy.path)),
        puct_constant=1.0,
        learned_value_mix=0.10,
    )
    return BoundAgent(agent.act), module, traces


def build_schedule(config: LeagueConfig) -> list[dict[str, Any]]:
    checkpoints = [policy for policy in config.policies if policy.kind == "checkpoint"]
    candidate = next(policy for policy in config.policies if policy.role == "candidate")
    modules = [policy for policy in config.policies if policy.kind == "module"]
    decks = {deck.name: deck for deck in config.decks}
    schedule: list[dict[str, Any]] = []
    for deck in config.decks:
        for left, right in itertools.combinations(checkpoints, 2):
            schedule.append({
                "category": "checkpoint_round_robin",
                "split": deck.split,
                "left_policy": left.name,
                "right_policy": right.name,
                "left_deck": deck.name,
                "right_deck": deck.name,
            })
    for left_deck in config.decks:
        for specialist in modules:
            right_deck = decks[specialist.preferred_deck or ""]
            schedule.append({
                "category": (
                    "specialist_same_deck"
                    if left_deck.name == right_deck.name
                    else "cross_deck_specialist"
                ),
                "split": (
                    "heldout"
                    if "heldout" in {left_deck.split, right_deck.split}
                    else "development"
                ),
                "left_policy": candidate.name,
                "right_policy": specialist.name,
                "left_deck": left_deck.name,
                "right_deck": right_deck.name,
            })
    for index, item in enumerate(schedule):
        item["matchup_id"] = f"phase9-m{index:04d}"
    return schedule


def _run_matchup(
    config: LeagueConfig,
    item: dict[str, Any],
    policies: dict[str, PolicySpec],
    decks: dict[str, tuple[DeckSpec, tuple[int, ...]]],
) -> dict[str, Any]:
    api = load_competition_api()
    game = _load_game()
    left_policy = policies[item["left_policy"]]
    right_policy = policies[item["right_policy"]]
    left_spec, left_deck = decks[item["left_deck"]]
    right_spec, right_deck = decks[item["right_deck"]]
    left, left_module, left_traces = _bind_policy(
        api, left_policy, left_deck, right_deck, config.search_config,
        f"{config.run_id}_{item['matchup_id']}_left",
    )
    right, right_module, right_traces = _bind_policy(
        api, right_policy, right_deck, left_deck, config.search_config,
        f"{config.run_id}_{item['matchup_id']}_right",
    )
    left_wins = right_wins = draws = 0
    faults: Counter[str] = Counter()
    errors: list[str] = []
    outcomes = []
    left_timing = TimingSamples()
    right_timing = TimingSamples()
    started = time.perf_counter()
    for game_index in range(config.games_per_matchup):
        left_first = game_index % 2 == 0
        agents = (left, right) if left_first else (right, left)
        modules = (left_module, right_module) if left_first else (right_module, left_module)
        game_decks = (left_deck, right_deck) if left_first else (right_deck, left_deck)
        outcome = play_game(game, api, agents, modules, game_decks, max_steps=config.max_steps)
        left.drain_into(left_timing)
        right.drain_into(right_timing)
        if outcome["fault"]:
            faults[outcome["fault"]] += 1
        if outcome["error"] and len(errors) < 25:
            errors.append(f"game {game_index}: {outcome['error']}")
        if outcome["result"] not in (0, 1):
            draws += 1
        elif (outcome["result"] == 0) == left_first:
            left_wins += 1
        else:
            right_wins += 1
        outcomes.append({"game_index": game_index, "left_first": left_first, **outcome})
    return {
        **item,
        "games": config.games_per_matchup,
        "left_wins": left_wins,
        "right_wins": right_wins,
        "draws": draws,
        "left_deck_path": str(left_spec.path),
        "left_deck_sha256": sha256_file(left_spec.path),
        "right_deck_path": str(right_spec.path),
        "right_deck_sha256": sha256_file(right_spec.path),
        "left_policy_sha256": sha256_file(left_policy.path),
        "right_policy_sha256": sha256_file(right_policy.path),
        "left_timing": left_timing.summary(),
        "right_timing": right_timing.summary(),
        "left_search": None if left_traces is None else left_traces.summary(),
        "right_search": None if right_traces is None else right_traces.summary(),
        "faults": dict(sorted(faults.items())),
        "errors": errors,
        "outcomes": outcomes,
        "duration_seconds": time.perf_counter() - started,
    }


def run_league(
    config: LeagueConfig,
    *,
    config_path: Path,
    output: Path,
    workers: int = 1,
) -> dict[str, Any]:
    if workers < 1:
        raise ValueError("league workers must be positive")
    policies = {policy.name: policy for policy in config.policies}
    decks = {
        deck.name: (deck, tuple(read_deck(deck.path)))
        for deck in config.decks
    }
    schedule = build_schedule(config)
    config_sha256 = sha256_file(config_path)
    match_root = ARTIFACT_ROOT / "phase9" / config.run_id / "matches"
    match_root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    matches_by_id: dict[str, dict[str, Any]] = {}
    resumed_matchups = 0
    pending = []
    for item in schedule:
        match_path = match_root / f"{item['matchup_id']}.json"
        if match_path.exists():
            match = json.loads(match_path.read_text(encoding="utf-8"))
            expected = {
                key: item[key]
                for key in (
                    "matchup_id", "category", "split", "left_policy",
                    "right_policy", "left_deck", "right_deck",
                )
            }
            if any(match.get(key) != value for key, value in expected.items()):
                raise ValueError(f"stale Phase 9 matchup artifact: {match_path}")
            if match.get("games") != config.games_per_matchup:
                raise ValueError(f"Phase 9 matchup game count changed: {match_path}")
            if match.get("config_sha256") != config_sha256:
                raise ValueError(f"Phase 9 matchup config identity changed: {match_path}")
            resumed_matchups += 1
            matches_by_id[item["matchup_id"]] = match
        else:
            pending.append(item)
    if workers == 1:
        for item in pending:
            match = _run_matchup(config, item, policies, decks)
            match["config_sha256"] = config_sha256
            write_json_atomic(match_root / f"{item['matchup_id']}.json", match)
            matches_by_id[item["matchup_id"]] = match
    elif pending:
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=workers, mp_context=context) as executor:
            futures = {
                executor.submit(_run_matchup, config, item, policies, decks): item
                for item in pending
            }
            for future in as_completed(futures):
                item = futures[future]
                match = future.result()
                match["config_sha256"] = config_sha256
                write_json_atomic(match_root / f"{item['matchup_id']}.json", match)
                matches_by_id[item["matchup_id"]] = match
    matches = [matches_by_id[item["matchup_id"]] for item in schedule]
    analysis = analyze_league(config, matches)
    report = {
        "schema_version": 1,
        "run_id": config.run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": str(config_path.resolve()),
        "config_sha256": config_sha256,
        "schedule": {
            "matchups": len(schedule),
            "games_per_matchup": config.games_per_matchup,
            "total_games": len(schedule) * config.games_per_matchup,
            "seat_balanced": True,
            "native_engine_seed_control": False,
            "resumed_matchups": resumed_matchups,
            "workers": workers,
        },
        "decks": [
            {**asdict(deck), "path": str(deck.path), "sha256": sha256_file(deck.path)}
            for deck in config.decks
        ],
        "policies": [
            {**asdict(policy), "path": str(policy.path), "sha256": sha256_file(policy.path)}
            for policy in config.policies
        ],
        "matches": matches,
        "analysis": analysis,
        "duration_seconds": time.perf_counter() - started,
    }
    write_json_atomic(output, report)
    return report
