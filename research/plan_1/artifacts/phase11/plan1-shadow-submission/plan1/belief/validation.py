from __future__ import annotations

import importlib
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from plan1.belief.priors import DeckMixturePrior
from plan1.belief.sampler import BeliefSampler, MirrorFillSampler, OracleSampler, oracle_inputs_from_visualizer
from plan1.config import Plan1Config
from plan1.engine.api_loader import load_competition_api
from plan1.engine.conformance import read_deck
from plan1.evaluation.handcrafted import HandcraftedEvaluator
from plan1.game.catalog import CardCatalog
from plan1.game.records import PublicObservationRecord
from plan1.paths import ENGINE_PARENT
from plan1.reproducibility import sha256_file, write_json_atomic
from plan1.search.ismcts import ISMCTSResult, RootSampledISMCTS
from plan1.search.mcts import UCTSearch


def _load_game() -> Any:
    load_competition_api()
    return importlib.import_module("cg.game")


def _load_baseline() -> Any:
    engine_path = str(ENGINE_PARENT.resolve())
    if engine_path not in sys.path:
        sys.path.insert(0, engine_path)
    return importlib.import_module("main")


def _edge_value(result: ISMCTSResult) -> float | None:
    chosen = next((edge for edge in result.trace.edges if edge.action == result.action), None)
    return None if chosen is None else chosen.mean_value


def _mode_summary(results: Sequence[ISMCTSResult]) -> dict[str, Any]:
    timings = sorted(result.trace.elapsed_ms for result in results)
    sampled = sum(result.trace.sampled_determinizations for result in results)
    completed = sum(result.trace.completed_determinizations for result in results)
    unique = sum(result.trace.unique_determinizations for result in results)
    return {
        "decisions": len(results),
        "sampled_determinizations": sampled,
        "completed_determinizations": completed,
        "unique_determinizations": unique,
        "duplicate_determinizations": sum(result.trace.duplicate_determinizations for result in results),
        "belief_fallbacks": sum(result.trace.belief_fallbacks for result in results),
        "inner_search_fallbacks": sum(result.trace.inner_search_fallbacks for result in results),
        "search_fallbacks": sum(result.trace.fallback_used for result in results),
        "errors": sum(len(result.trace.errors) for result in results),
        "elapsed_ms_median": statistics.median(timings) if timings else None,
        "elapsed_ms_p95": timings[max(0, (len(timings) * 95 + 99) // 100 - 1)] if timings else None,
        "effective_diversity": unique / sampled if sampled else None,
        "completed_search_rate": completed / sampled if sampled else None,
    }


def run_phase5_suite(
    deck_paths: Sequence[Path],
    *,
    decisions: int,
    max_steps: int,
    determinizations: int,
    config: Plan1Config,
    report_path: Path,
) -> dict[str, Any]:
    if decisions < 1 or max_steps < 1 or determinizations < 1:
        raise ValueError("decisions, max_steps, and determinizations must be positive")
    api = load_competition_api()
    game = _load_game()
    baseline = _load_baseline()
    decks = tuple(read_deck(path) for path in deck_paths)
    if not decks:
        raise ValueError("at least one deck is required")
    catalog = CardCatalog.from_engine(api.all_card_data(), api.all_attack())
    basic_ids = tuple(card.card_id for card in catalog.cards if card.basic)
    evaluator = HandcraftedEvaluator(catalog)
    search_config = replace(config.search, horizon_turns=0)
    searcher = UCTSearch(
        api,
        evaluator,
        search_config,
        cleanup_reserve_ms=config.safety.cleanup_reserve_ms,
        rollout_policy=baseline._greedy_select,
    )
    prior = DeckMixturePrior(decks)
    results: dict[str, list[ISMCTSResult]] = {"mirror_fill": [], "generic": [], "oracle": []}
    samples: list[dict[str, Any]] = []
    faults: Counter[str] = Counter()
    started = time.perf_counter()
    game_index = 0
    while len(results["generic"]) < decisions and game_index < max(decisions * 2, len(decks)):
        pair = (decks[game_index % len(decks)], decks[(game_index + 1) % len(decks)])
        observation_dict, start_data = game.battle_start(list(pair[0]), list(pair[1]))
        if observation_dict is None:
            faults["battle_start"] += 1
            game_index += 1
            continue
        try:
            for step in range(max_steps):
                observation = api.to_observation_class(observation_dict)
                if observation.current is None or observation.current.result != -1 or observation.select is None:
                    break
                root = int(observation.current.yourIndex)
                own_deck, opposing_deck = pair[root], pair[1 - root]
                baseline._MY_DECK = list(own_deck)
                fallback = list(baseline.agent(observation_dict))
                searchable = bool(
                    observation.search_begin_input
                    and int(observation.select.type) == 0
                    and len(observation.select.option) >= 2
                    and all(not player.active or player.active[0] is not None for player in observation.current.players)
                )
                if searchable and len(results["generic"]) < decisions:
                    record = PublicObservationRecord.from_engine(observation)
                    oracle_inputs = oracle_inputs_from_visualizer(game.visualize_data(), root)
                    modes = {
                        "mirror_fill": MirrorFillSampler(
                            own_deck, opposing_deck, basic_pokemon_ids=basic_ids
                        ),
                        "generic": BeliefSampler(
                            own_deck, prior, basic_pokemon_ids=basic_ids
                        ),
                        "oracle": OracleSampler(oracle_inputs),
                    }
                    decision_results: dict[str, ISMCTSResult] = {}
                    base_seed = config.reproducibility.seed + game_index * 100_003 + step
                    for mode, sampler in modes.items():
                        count = determinizations if mode == "generic" else 1
                        decision_results[mode] = RootSampledISMCTS(
                            searcher, sampler, determinizations=count
                        ).search(observation, seed=base_seed, fallback_action=fallback)
                        results[mode].append(decision_results[mode])
                    samples.append(
                        {
                            "game_index": game_index,
                            "step": step,
                            "root_player": root,
                            "information_set_key": decision_results["generic"].trace.information_set_key,
                            "actions": {mode: list(result.action) for mode, result in decision_results.items()},
                            "values": {mode: _edge_value(result) for mode, result in decision_results.items()},
                            "generic_unique_determinizations": decision_results["generic"].trace.unique_determinizations,
                            "generic_errors": list(decision_results["generic"].trace.errors),
                            "public_fingerprint": record.fingerprint,
                        }
                    )
                observation_dict = game.battle_select(fallback)
            else:
                faults["game_timeout"] += 1
        except Exception as exc:
            faults[f"{type(exc).__name__}:{exc}"] += 1
        finally:
            game.battle_finish()
        game_index += 1

    captured = len(results["generic"])
    agreement = {}
    for left, right in (("generic", "mirror_fill"), ("generic", "oracle"), ("mirror_fill", "oracle")):
        matches = sum(a.action == b.action for a, b in zip(results[left], results[right]))
        agreement[f"{left}_vs_{right}"] = {
            "matches": matches,
            "total": captured,
            "rate": matches / captured if captured else None,
        }
    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase": 5,
        "mode": "belief_and_ismcts_validation",
        "requested_decisions": decisions,
        "captured_decisions": captured,
        "determinizations_per_generic_root": determinizations,
        "search_config": asdict(search_config),
        "decks": [
            {"path": str(path.resolve()), "sha256": sha256_file(path)} for path in deck_paths
        ],
        "modes": {mode: _mode_summary(mode_results) for mode, mode_results in results.items()},
        "action_agreement": agreement,
        "samples": samples,
        "faults": dict(sorted(faults.items())),
        "duration_seconds": time.perf_counter() - started,
    }
    generic = report["modes"]["generic"]
    report["passed"] = bool(
        captured == decisions
        and generic["sampled_determinizations"] == decisions * determinizations
        and generic["completed_determinizations"] > 0
        and generic["completed_search_rate"] is not None
        and generic["completed_search_rate"] >= 0.5
        and generic["errors"] == 0
        and generic["belief_fallbacks"] == 0
        and generic["effective_diversity"] is not None
        and generic["effective_diversity"] >= 0.5
        and report["modes"]["oracle"]["errors"] == 0
        and report["modes"]["mirror_fill"]["errors"] == 0
        and not faults
    )
    write_json_atomic(report_path, report)
    return report
