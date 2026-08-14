from __future__ import annotations

import math
import statistics
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from plan1.config import load_config
from plan1.data.generator import HeuristicCorpusGenerator, deck_identity
from plan1.data.manifests import SplitPolicy
from plan1.data.replay_buffer import CorpusStore, ReplayReader
from plan1.engine.api_loader import load_competition_api
from plan1.engine.conformance import read_deck
from plan1.model.features import FeatureEncoder
from plan1.model.inference import ModelInference
from plan1.model.policy_value import ModelConfig, PolicyValueModel
from plan1.paths import CONFIG_ROOT
from plan1.reproducibility import canonical_json_hash, sha256_file, write_json_atomic
from plan1.search.agent import Plan1MCTSAgent
from plan1.search.validation import (
    BoundAgent,
    TimingSamples,
    TraceCollector,
    _load_game,
    _load_heuristic_module,
    play_game,
)
from plan1.training.dataset import PolicyValueDataset
from plan1.training.learner import fit_value_calibration, train_model


POLICY_EPSILON = 1e-12
INFERENCE_P95_LIMIT_MS = 5.0
NONINFERIORITY_MARGIN = 0.20


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def evaluate_dataset(
    model: PolicyValueModel,
    dataset: PolicyValueDataset,
    *,
    baseline_value_probability: float,
) -> dict[str, Any]:
    policy_loss = uniform_loss = value_brier = baseline_brier = 0.0
    correct = 0
    uniform_expected_correct = 0.0
    calibration = [dict(count=0, confidence=0.0, outcome=0.0) for _ in range(10)]
    for example in dataset.examples:
        probabilities = model.policy(example.action_features)
        policy_loss -= sum(
            target * math.log(max(probability, POLICY_EPSILON))
            for target, probability in zip(example.policy_target, probabilities)
        )
        uniform_loss += math.log(len(example.action_features))
        predicted_index = min(range(len(probabilities)), key=lambda index: (-probabilities[index], index))
        correct += int(predicted_index == example.chosen_index)
        uniform_expected_correct += 1.0 / len(probabilities)

        value_probability = (model.value(example.observation_features) + 1.0) / 2.0
        target_probability = (example.value_target + 1.0) / 2.0
        value_brier += (value_probability - target_probability) ** 2
        baseline_brier += (baseline_value_probability - target_probability) ** 2
        bucket = min(9, int(value_probability * 10))
        calibration[bucket]["count"] += 1
        calibration[bucket]["confidence"] += value_probability
        calibration[bucket]["outcome"] += target_probability
    count = len(dataset)
    expected_calibration_error = 0.0
    bins: list[dict[str, Any]] = []
    for index, item in enumerate(calibration):
        if not item["count"]:
            continue
        confidence = item["confidence"] / item["count"]
        outcome = item["outcome"] / item["count"]
        expected_calibration_error += item["count"] / count * abs(confidence - outcome)
        bins.append(
            {
                "bin": index,
                "count": item["count"],
                "mean_confidence": confidence,
                "outcome_rate": outcome,
            }
        )
    return {
        "examples": count,
        "games": len({example.game_id for example in dataset.examples}),
        "policy_log_loss": policy_loss / count,
        "uniform_policy_log_loss": uniform_loss / count,
        "policy_top1_accuracy": correct / count,
        "uniform_expected_top1_accuracy": uniform_expected_correct / count,
        "value_brier": value_brier / count,
        "constant_value_brier": baseline_brier / count,
        "value_ece": expected_calibration_error,
        "calibration_bins": bins,
    }


def inference_benchmark(
    inference: ModelInference,
    dataset: PolicyValueDataset,
    *,
    repeats: int = 5,
) -> dict[str, Any]:
    samples: list[float] = []
    examples = dataset.examples[: min(250, len(dataset.examples))]
    for _ in range(repeats):
        for example in examples:
            started = time.perf_counter_ns()
            inference.model.policy(example.action_features)
            inference.model.value(example.observation_features)
            samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return {
        "calls": len(samples),
        "median_ms": statistics.median(samples) if samples else None,
        "p95_ms": _percentile(samples, 0.95),
        "max_ms": max(samples) if samples else None,
        "p95_limit_ms": INFERENCE_P95_LIMIT_MS,
        "passed": bool(samples and _percentile(samples, 0.95) <= INFERENCE_P95_LIMIT_MS),
    }


def _search_agent(
    api: Any,
    deck: Sequence[int],
    module_name: str,
    traces: TraceCollector,
    inference: ModelInference | None,
) -> tuple[BoundAgent, Any]:
    module = _load_heuristic_module(module_name, deck)
    config = load_config(CONFIG_ROOT / "mcts_baseline.json")
    agent = Plan1MCTSAgent(
        api,
        deck,
        config,
        opponent_deck=deck,
        fallback_policy=module._greedy_select,
        rollout_policy=module._greedy_select,
        action_observer=module._record_if_ability,
        trace_sink=traces,
        policy_value=inference,
        puct_constant=1.0,
        learned_value_mix=0.10,
    )
    return BoundAgent(agent.act), module


def _noninferiority(wins: int, losses: int, margin: float = NONINFERIORITY_MARGIN) -> dict[str, Any]:
    decisive = wins + losses
    if decisive == 0:
        return {"decisive_games": 0, "z_score": None, "p_value_one_sided": None, "passed": True}
    rate = wins / decisive
    null_rate = 0.5 - margin
    standard_error = math.sqrt(max(1e-12, null_rate * (1.0 - null_rate) / decisive))
    z_score = (rate - null_rate) / standard_error
    p_value = 0.5 * math.erfc(z_score / math.sqrt(2.0))
    return {
        "decisive_games": decisive,
        "candidate_decisive_win_rate": rate,
        "margin": margin,
        "null_win_rate": null_rate,
        "z_score": z_score,
        "p_value_one_sided": p_value,
        "passed": p_value < 0.05,
    }


def run_search_screen(
    model: PolicyValueModel,
    deck_path: Path,
    *,
    games: int,
    max_steps: int,
) -> dict[str, Any]:
    if games < 2 or games % 2:
        raise ValueError("search screen games must be a positive even number")
    api = load_competition_api()
    game = _load_game()
    deck = read_deck(deck_path)
    puct_traces = TraceCollector()
    uct_traces = TraceCollector()
    candidate, candidate_module = _search_agent(
        api, deck, "phase7_puct", puct_traces, ModelInference(model)
    )
    baseline, baseline_module = _search_agent(api, deck, "phase7_uct", uct_traces, None)
    candidate_wins = baseline_wins = draws = 0
    faults: Counter[str] = Counter()
    errors: list[str] = []
    candidate_timing = TimingSamples()
    baseline_timing = TimingSamples()
    started = time.perf_counter()
    for game_index in range(games):
        candidate_first = game_index % 2 == 0
        agents = (candidate, baseline) if candidate_first else (baseline, candidate)
        modules = (
            (candidate_module, baseline_module)
            if candidate_first else (baseline_module, candidate_module)
        )
        outcome = play_game(game, api, agents, modules, (deck, deck), max_steps=max_steps)
        candidate.drain_into(candidate_timing)
        baseline.drain_into(baseline_timing)
        if outcome["fault"]:
            faults[outcome["fault"]] += 1
        if outcome["error"] and len(errors) < 50:
            errors.append(f"game {game_index}: {outcome['error']}")
        if outcome["result"] not in (0, 1):
            draws += 1
        elif (outcome["result"] == 0) == candidate_first:
            candidate_wins += 1
        else:
            baseline_wins += 1
    noninferiority = _noninferiority(candidate_wins, baseline_wins)
    safety_passed = not faults and not errors
    return {
        "deck": str(deck_path.resolve()),
        "deck_sha256": sha256_file(deck_path),
        "games": games,
        "candidate": "policy-value-puct",
        "baseline": "heuristic-uct",
        "candidate_wins": candidate_wins,
        "baseline_wins": baseline_wins,
        "draws": draws,
        "noninferiority": noninferiority,
        "candidate_timing": candidate_timing.summary(),
        "baseline_timing": baseline_timing.summary(),
        "candidate_search": puct_traces.summary(),
        "baseline_search": uct_traces.summary(),
        "faults": dict(sorted(faults.items())),
        "errors": errors,
        "safety_passed": safety_passed,
        "passed": safety_passed and noninferiority["passed"],
        "duration_seconds": time.perf_counter() - started,
    }


def run_phase7_suite(
    deck_paths: Sequence[Path],
    *,
    corpus_root: Path,
    corpus_games: int,
    run_id: str,
    root_seed: int,
    checkpoint_path: Path,
    report_path: Path,
    screen_deck: Path,
    screen_games: int,
    max_steps: int,
    model_config: ModelConfig | None = None,
) -> dict[str, Any]:
    if len(deck_paths) < 2 or corpus_games < 12:
        raise ValueError("Phase 7 requires at least two decks and 12 corpus games")
    split_policy = SplitPolicy(70, 15, 15)
    store = CorpusStore(corpus_root, "phase7-bootstrap", split_policy)
    identities = [deck_identity(path.stem, read_deck(path)) for path in deck_paths]
    generation = HeuristicCorpusGenerator(
        store,
        identities,
        run_id=run_id,
        root_seed=root_seed,
        max_candidates=64,
        max_steps=max_steps,
    ).generate(corpus_games)
    validation = store.validate_all()
    encoder = FeatureEncoder((model_config or ModelConfig()).feature_dimension)
    train = PolicyValueDataset.from_decisions(ReplayReader(store, ("train",)).decisions(), encoder)
    present_splits = {
        entry.split for entry in store.load_manifest().entries if entry.purpose == "training"
    }
    if not {"validation", "test"} <= present_splits:
        raise RuntimeError("Phase 7 corpus requires separate validation and test games")
    calibration_set = PolicyValueDataset.from_decisions(
        ReplayReader(store, ("validation",)).decisions(), encoder
    )
    heldout = PolicyValueDataset.from_decisions(
        ReplayReader(store, ("test",)).decisions(), encoder
    )
    config = model_config or ModelConfig()
    train_value_probability = statistics.mean(
        (example.value_target + 1.0) / 2.0 for example in train.examples
    )
    manifest = store.load_manifest()
    metadata = {
        "run_id": run_id,
        "corpus_id": manifest.corpus_id,
        "manifest_sha256": manifest.fingerprint,
        "train_games": len({example.game_id for example in train.examples}),
        "train_examples": len(train),
        "calibration_split": "validation",
        "heldout_split": "test",
        "deck_sha256": [identity.sha256 for identity in identities],
    }
    model, training = train_model(train, config, metadata=metadata)
    calibration = fit_value_calibration(
        model, calibration_set, baseline_probability=train_value_probability
    )
    checkpoint_sha256 = model.save(checkpoint_path)
    reloaded = PolicyValueModel.load(checkpoint_path)
    checkpoint_roundtrip = (
        reloaded.fingerprint == model.fingerprint
        and reloaded.policy(train.examples[0].action_features)
        == model.policy(train.examples[0].action_features)
        and reloaded.value(train.examples[0].observation_features)
        == model.value(train.examples[0].observation_features)
    )
    train_metrics = evaluate_dataset(
        model, train, baseline_value_probability=train_value_probability
    )
    calibration_metrics = evaluate_dataset(
        model, calibration_set, baseline_value_probability=train_value_probability
    )
    heldout_metrics = evaluate_dataset(
        model, heldout, baseline_value_probability=train_value_probability
    )
    inference = inference_benchmark(ModelInference(reloaded), heldout)
    search_screen = run_search_screen(
        reloaded, screen_deck, games=screen_games, max_steps=max_steps
    )
    policy_passed = (
        heldout_metrics["policy_log_loss"] < heldout_metrics["uniform_policy_log_loss"]
        and heldout_metrics["policy_top1_accuracy"]
        > heldout_metrics["uniform_expected_top1_accuracy"]
    )
    value_passed = heldout_metrics["value_brier"] < heldout_metrics["constant_value_brier"]
    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase": 7,
        "model_version": model.payload()["model_version"],
        "configuration": {
            "decks": [str(path.resolve()) for path in deck_paths],
            "corpus_root": str(corpus_root.resolve()),
            "corpus_games": corpus_games,
            "run_id": run_id,
            "root_seed": root_seed,
            "model": asdict(config),
            "screen_deck": str(screen_deck.resolve()),
            "screen_games": screen_games,
            "max_steps": max_steps,
        },
        "generation": asdict(generation),
        "corpus_validation": validation,
        "split_distribution": {
            split: ReplayReader(store, (split,)).distribution()
            for split in ("train", "validation", "test")
            if any(entry.split == split for entry in manifest.entries)
        },
        "training": training.to_dict(),
        "value_calibration": calibration,
        "train_metrics": train_metrics,
        "validation_metrics": calibration_metrics,
        "heldout_metrics": heldout_metrics,
        "checkpoint": {
            "path": str(checkpoint_path.resolve()),
            "payload_sha256": checkpoint_sha256,
            "file_sha256": sha256_file(checkpoint_path),
            "roundtrip_exact": checkpoint_roundtrip,
            "bytes": checkpoint_path.stat().st_size,
        },
        "inference": inference,
        "search_screen": search_screen,
        "gates": {
            "corpus_valid": validation["passed"] and not generation.errors,
            "policy_beats_uniform": policy_passed,
            "value_beats_constant": value_passed,
            "checkpoint_roundtrip": checkpoint_roundtrip,
            "cpu_inference": inference["passed"],
            "search_noninferior_screen": search_screen["passed"],
        },
    }
    report["passed"] = all(report["gates"].values())
    report["report_identity"] = canonical_json_hash(report)
    write_json_atomic(report_path, report)
    return report
