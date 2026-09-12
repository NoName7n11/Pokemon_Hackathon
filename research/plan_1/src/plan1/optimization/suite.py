from __future__ import annotations

import gzip
import io
import itertools
import json
import math
import os
import statistics
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from plan1.config import load_config
from plan1.data.manifests import SplitPolicy
from plan1.data.replay_buffer import CorpusStore, ReplayReader
from plan1.engine.api_loader import load_competition_api
from plan1.engine.conformance import read_deck
from plan1.model.features import FeatureEncoder
from plan1.model.inference import ModelInference
from plan1.model.policy_value import ModelConfig, PolicyValueModel
from plan1.model.validation import evaluate_dataset, inference_benchmark
from plan1.optimization.config import OptimizationConfig, SearchVariant
from plan1.paths import ARTIFACT_ROOT
from plan1.reproducibility import canonical_json_hash, sha256_file, write_json_atomic
from plan1.search.agent import Plan1MCTSAgent
from plan1.search.validation import BoundAgent, TimingSamples, TraceCollector, _load_game, _load_heuristic_module, play_game
from plan1.training.dataset import PolicyValueDataset
from plan1.training.learner import fit_value_calibration, train_model


def _head_to_head_statistics(wins: int, losses: int) -> dict[str, Any]:
    decisive = wins + losses
    if decisive == 0:
        return {"wilson_95": None, "z_score": None, "p_value_two_sided": None}
    rate = wins / decisive
    z = 1.96
    denominator = 1.0 + z * z / decisive
    center = (rate + z * z / (2.0 * decisive)) / denominator
    half = z * math.sqrt(
        (rate * (1.0 - rate) + z * z / (4.0 * decisive)) / decisive
    ) / denominator
    z_score = (rate - 0.5) / math.sqrt(0.25 / decisive)
    return {
        "wilson_95": [center - half, center + half],
        "z_score": z_score,
        "p_value_two_sided": math.erfc(abs(z_score) / math.sqrt(2.0)),
    }


def _bind_variant(
    api: Any,
    variant: SearchVariant,
    checkpoint: Path,
    deck: Sequence[int],
    opponent_deck: Sequence[int],
    module_name: str,
) -> tuple[BoundAgent, Any, TraceCollector]:
    module = _load_heuristic_module(module_name, deck)
    traces = TraceCollector(sample_limit=5)
    agent = Plan1MCTSAgent(
        api,
        deck,
        load_config(variant.config_path),
        opponent_deck=opponent_deck,
        fallback_policy=module._greedy_select,
        rollout_policy=module._greedy_select,
        action_observer=module._record_if_ability,
        trace_sink=traces,
        policy_value=ModelInference(PolicyValueModel.load(checkpoint)),
        puct_constant=1.0,
        learned_value_mix=0.10,
    )
    return BoundAgent(agent.act), module, traces


def _search_match(
    config: OptimizationConfig,
    left_variant: SearchVariant,
    right_variant: SearchVariant,
    deck_path: Path,
    matchup_id: str,
) -> dict[str, Any]:
    api = load_competition_api()
    game = _load_game()
    deck = tuple(read_deck(deck_path))
    left, left_module, left_traces = _bind_variant(
        api, left_variant, config.checkpoint, deck, deck, f"{matchup_id}_left"
    )
    right, right_module, right_traces = _bind_variant(
        api, right_variant, config.checkpoint, deck, deck, f"{matchup_id}_right"
    )
    left_wins = right_wins = draws = 0
    faults: Counter[str] = Counter()
    errors: list[str] = []
    outcomes = []
    left_timing = TimingSamples()
    right_timing = TimingSamples()
    started = time.perf_counter()
    for game_index in range(config.games_per_pair):
        left_first = game_index % 2 == 0
        agents = (left, right) if left_first else (right, left)
        modules = (left_module, right_module) if left_first else (right_module, left_module)
        outcome = play_game(game, api, agents, modules, (deck, deck), max_steps=config.max_steps)
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
        "matchup_id": matchup_id,
        "deck": deck_path.stem,
        "deck_path": str(deck_path.resolve()),
        "deck_sha256": sha256_file(deck_path),
        "left_variant": left_variant.name,
        "right_variant": right_variant.name,
        "games": config.games_per_pair,
        "left_wins": left_wins,
        "right_wins": right_wins,
        "draws": draws,
        "left_timing": left_timing.summary(),
        "right_timing": right_timing.summary(),
        "left_search": left_traces.summary(),
        "right_search": right_traces.summary(),
        "faults": dict(sorted(faults.items())),
        "errors": errors,
        "outcomes": outcomes,
        "duration_seconds": time.perf_counter() - started,
    }


def _variant_perspective(match: dict[str, Any], name: str) -> tuple[int, int, dict[str, Any], dict[str, Any]]:
    if match["left_variant"] == name:
        return match["left_wins"], match["right_wins"], match["left_search"], match["left_timing"]
    if match["right_variant"] == name:
        return match["right_wins"], match["left_wins"], match["right_search"], match["right_timing"]
    raise ValueError(f"variant {name} absent from {match['matchup_id']}")


def _search_analysis(config: OptimizationConfig, matches: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = config.search_gates.baseline_name
    table = {}
    for variant in config.search_variants:
        relevant = [
            match for match in matches
            if variant.name in {match["left_variant"], match["right_variant"]}
        ]
        wins = losses = draws = searched = full = changed = overruns = 0
        fallbacks: Counter[str] = Counter()
        p95_values = []
        for match in relevant:
            won, lost, search, timing = _variant_perspective(match, variant.name)
            wins += won
            losses += lost
            draws += match["draws"]
            searched += search["searched_decisions"]
            full += search["full_root_coverage"]
            changed += search["chose_non_fallback"]
            overruns += search["hard_deadline_overruns"]
            fallbacks.update(search["fallback_reasons"])
            if timing["p95_ms"] is not None:
                p95_values.append(timing["p95_ms"])
        direct = [
            match for match in relevant
            if baseline in {match["left_variant"], match["right_variant"]}
            and variant.name != baseline
        ]
        direct_wins = direct_losses = direct_draws = 0
        for match in direct:
            won, lost, _, _ = _variant_perspective(match, variant.name)
            direct_wins += won
            direct_losses += lost
            direct_draws += match["draws"]
        decisive = direct_wins + direct_losses
        direct_summary = None
        if variant.name != baseline:
            direct_summary = {
                "games": direct_wins + direct_losses + direct_draws,
                "wins": direct_wins,
                "losses": direct_losses,
                "draws": direct_draws,
                "decisive_games": decisive,
                "decisive_win_rate": direct_wins / decisive if decisive else None,
                **_head_to_head_statistics(direct_wins, direct_losses),
            }
        table[variant.name] = {
            "games": wins + losses + draws,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "field_decisive_win_rate": wins / (wins + losses) if wins + losses else None,
            "vs_baseline": direct_summary,
            "search": {
                "searched_decisions": searched,
                "full_root_coverage_rate": full / searched if searched else None,
                "nonfallback_choice_rate": changed / searched if searched else None,
                "hard_deadline_overrun_rate": overruns / searched if searched else None,
                "fallback_reasons": dict(sorted(fallbacks.items())),
            },
            "maximum_match_p95_ms": max(p95_values) if p95_values else None,
        }
    eligible = []
    for variant in config.search_variants:
        if variant.name == baseline:
            continue
        item = table[variant.name]
        direct = item["vs_baseline"]
        safety = all(
            not match["faults"] and not match["errors"]
            for match in matches
            if variant.name in {match["left_variant"], match["right_variant"]}
        )
        passes = bool(
            safety
            and direct["decisive_games"] >= config.search_gates.minimum_decisive_games
            and direct["decisive_win_rate"] is not None
            and direct["decisive_win_rate"] >= config.search_gates.minimum_baseline_win_rate
            and item["search"]["nonfallback_choice_rate"] is not None
            and item["search"]["nonfallback_choice_rate"] >= config.search_gates.minimum_nonfallback_rate
            and item["search"]["hard_deadline_overrun_rate"] is not None
            and item["search"]["hard_deadline_overrun_rate"] <= config.search_gates.maximum_hard_overrun_rate
            and item["maximum_match_p95_ms"] is not None
            and item["maximum_match_p95_ms"] <= config.search_gates.maximum_match_p95_ms
        )
        item["screen_gate"] = {"safety_passed": safety, "passed": passes}
        if passes:
            eligible.append(variant.name)
    recommended = max(
        eligible,
        key=lambda name: (
            table[name]["vs_baseline"]["decisive_win_rate"],
            table[name]["search"]["nonfallback_choice_rate"],
            -table[name]["maximum_match_p95_ms"],
        ),
        default=None,
    )
    return {
        "baseline": baseline,
        "table": table,
        "eligible_variants": eligible,
        "recommended_research_variant": recommended,
        "decision": "recommend_for_phase9_rescreen" if recommended else "keep_baseline",
    }


def _gzip_export(source: Path, destination: Path) -> dict[str, Any]:
    payload = source.read_bytes()
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, compresslevel=9, mtime=0) as handle:
        handle.write(payload)
    compressed = output.getvalue()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(compressed)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    with gzip.open(destination, "rb") as handle:
        restored = handle.read(len(payload) + 1)
    return {
        "json_path": str(source.resolve()),
        "json_sha256": sha256_file(source),
        "json_bytes": len(payload),
        "gzip_path": str(destination.resolve()),
        "gzip_sha256": sha256_file(destination),
        "gzip_bytes": len(compressed),
        "compression_ratio": len(compressed) / len(payload),
        "roundtrip_exact": restored == payload,
    }


def _model_ablation(config: OptimizationConfig, checkpoint_root: Path) -> dict[str, Any]:
    settings = config.model_ablation
    store = CorpusStore(settings.corpus_root, "phase7-bootstrap", SplitPolicy(70, 15, 15))
    train_decisions = tuple(ReplayReader(store, ("train",)).decisions())
    validation_decisions = tuple(ReplayReader(store, ("validation",)).decisions())
    test_decisions = tuple(ReplayReader(store, ("test",)).decisions())
    train_mean = statistics.mean(
        (decision.value_target + 1.0) / 2.0 for decision in train_decisions
    )
    results = []
    for dimension in settings.dimensions:
        encoder = FeatureEncoder(dimension)
        train = PolicyValueDataset.from_decisions(train_decisions, encoder)
        validation = PolicyValueDataset.from_decisions(validation_decisions, encoder)
        heldout = PolicyValueDataset.from_decisions(test_decisions, encoder)
        model_config = ModelConfig(
            feature_dimension=dimension,
            learning_rate=settings.learning_rate,
            value_learning_rate=settings.value_learning_rate,
            l2=settings.l2,
            epochs=settings.epochs,
            value_epochs=settings.value_epochs,
            seed=settings.seed,
        )
        started = time.perf_counter()
        model, training = train_model(
            train,
            model_config,
            metadata={"phase": 10, "run_id": config.run_id, "dimension": dimension},
        )
        calibration = fit_value_calibration(model, validation, baseline_probability=train_mean)
        checkpoint = checkpoint_root / f"model-{dimension}.json"
        payload_sha256 = model.save(checkpoint)
        metrics = evaluate_dataset(model, heldout, baseline_value_probability=train_mean)
        inference = inference_benchmark(ModelInference(model), heldout, repeats=3)
        export = _gzip_export(checkpoint, checkpoint.with_suffix(".json.gz"))
        results.append({
            "dimension": dimension,
            "training": training.to_dict(),
            "calibration": calibration,
            "heldout": metrics,
            "inference": inference,
            "checkpoint_payload_sha256": payload_sha256,
            "export": export,
            "duration_seconds": time.perf_counter() - started,
        })
    baseline = next(item for item in results if item["dimension"] == max(settings.dimensions))
    eligible = [
        item for item in results
        if item["heldout"]["policy_log_loss"]
        <= baseline["heldout"]["policy_log_loss"] * settings.maximum_policy_loss_ratio
        and item["heldout"]["value_brier"]
        <= baseline["heldout"]["value_brier"] * settings.maximum_value_brier_ratio
        and item["inference"]["passed"]
        and item["export"]["roundtrip_exact"]
    ]
    selected = min(eligible, key=lambda item: item["export"]["gzip_bytes"], default=baseline)
    return {
        "frozen_corpus_manifest": store.load_manifest().fingerprint,
        "train_decisions": len(train_decisions),
        "validation_decisions": len(validation_decisions),
        "test_decisions": len(test_decisions),
        "results": results,
        "baseline_dimension": baseline["dimension"],
        "selected_dimension": selected["dimension"],
        "selection_is_deployment_recommendation_only": True,
    }


def run_optimization_suite(
    config: OptimizationConfig,
    *,
    config_path: Path,
    output: Path,
    include_model: bool = True,
) -> dict[str, Any]:
    run_root = ARTIFACT_ROOT / "phase10" / config.run_id
    match_root = run_root / "matches"
    checkpoint_root = run_root / "checkpoints"
    match_root.mkdir(parents=True, exist_ok=True)
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    config_sha256 = sha256_file(config_path)
    schedule = []
    for deck_path in config.deck_paths:
        for left, right in itertools.combinations(config.search_variants, 2):
            schedule.append((deck_path, left, right))
    matches = []
    resumed = 0
    started = time.perf_counter()
    for index, (deck_path, left, right) in enumerate(schedule):
        matchup_id = f"phase10-m{index:03d}"
        path = match_root / f"{matchup_id}.json"
        if path.exists():
            match = json.loads(path.read_text(encoding="utf-8"))
            expected = (deck_path.stem, left.name, right.name, config.games_per_pair, config_sha256)
            actual = (
                match.get("deck"), match.get("left_variant"), match.get("right_variant"),
                match.get("games"), match.get("config_sha256"),
            )
            if actual != expected:
                raise ValueError(f"stale Phase 10 matchup artifact: {path}")
            resumed += 1
        else:
            match = _search_match(config, left, right, deck_path, matchup_id)
            match["config_sha256"] = config_sha256
            write_json_atomic(path, match)
        matches.append(match)
    search = _search_analysis(config, matches)
    model = _model_ablation(config, checkpoint_root) if include_model else None
    report = {
        "schema_version": 1,
        "phase": 10,
        "run_id": config.run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": str(config_path.resolve()),
        "config_sha256": config_sha256,
        "checkpoint": str(config.checkpoint.resolve()),
        "checkpoint_sha256": sha256_file(config.checkpoint),
        "search_schedule": {
            "matchups": len(schedule),
            "games": len(schedule) * config.games_per_pair,
            "games_per_pair": config.games_per_pair,
            "seat_balanced": True,
            "resumed_matchups": resumed,
        },
        "matches": matches,
        "search_analysis": search,
        "model_ablation": model,
        "duration_seconds": time.perf_counter() - started,
    }
    report["report_identity"] = canonical_json_hash(report)
    write_json_atomic(output, report)
    return report
