from __future__ import annotations

import importlib
import math
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from plan1.engine.api_loader import load_competition_api
from plan1.engine.conformance import conformance_action, read_deck
from plan1.evaluation.handcrafted import EVALUATOR_VERSION, NONTERMINAL_BOUND, HandcraftedEvaluator
from plan1.evaluation.tactical import run_tactical_suite
from plan1.game.catalog import CardCatalog
from plan1.game.records import PublicObservationRecord
from plan1.paths import ENGINE_PARENT
from plan1.reproducibility import sha256_file, write_json_atomic


EVALUATION_MEDIAN_LIMIT_MS = 0.50
EVALUATION_P95_LIMIT_MS = 2.00
EVALUATION_MAX_LIMIT_MS = 20.00
PERSPECTIVE_TOLERANCE = 1e-9


@dataclass(slots=True)
class DeckEvaluationResult:
    deck: str
    deck_sha256: str
    games: int
    completed_games: int
    timed_out_games: int
    decisions: int
    observations_evaluated: int
    terminal_observations: int
    perspective_failures: int
    reconstruction_failures: int
    scalar_breakdown_mismatches: int
    nonfinite_scores: int
    out_of_bound_scores: int
    evaluator_ms_median: float
    evaluator_ms_p95: float
    evaluator_ms_max: float
    simulator_action_ms_median: float
    evaluator_to_simulator_median_ratio: float | None
    diagnostic_counts: dict[str, int]
    errors: list[str]
    elapsed_seconds: float

    @property
    def passed(self) -> bool:
        return (
            self.completed_games == self.games
            and self.timed_out_games == 0
            and self.decisions > 0
            and self.observations_evaluated > 0
            and self.perspective_failures == 0
            and self.reconstruction_failures == 0
            and self.scalar_breakdown_mismatches == 0
            and self.nonfinite_scores == 0
            and self.out_of_bound_scores == 0
            and self.evaluator_ms_median <= EVALUATION_MEDIAN_LIMIT_MS
            and self.evaluator_ms_p95 <= EVALUATION_P95_LIMIT_MS
            and self.evaluator_ms_max <= EVALUATION_MAX_LIMIT_MS
            and not self.errors
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["passed"] = self.passed
        return value


def _load_game() -> Any:
    load_competition_api()
    engine_text = str(ENGINE_PARENT.resolve())
    if engine_text not in sys.path:
        sys.path.insert(0, engine_text)
    return importlib.import_module("cg.game")


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return float("inf")
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * percentile) - 1)
    return ordered[index]


def validate_evaluator_on_deck(
    deck_path: Path,
    evaluator: HandcraftedEvaluator,
    *,
    games: int,
    max_steps: int,
) -> DeckEvaluationResult:
    api = load_competition_api()
    game = _load_game()
    deck = read_deck(deck_path)
    diagnostics: Counter[str] = Counter()
    errors: list[str] = []
    evaluator_times: list[float] = []
    simulator_times: list[float] = []
    completed = timed_out = decisions = evaluated = terminal = 0
    perspective_failures = reconstruction_failures = scalar_mismatches = nonfinite = out_of_bound = 0
    started = time.perf_counter()

    for game_index in range(games):
        observation_dict, start_data = game.battle_start(deck, deck)
        if observation_dict is None:
            errors.append(f"game {game_index}: battle_start failed: {start_data}")
            continue
        try:
            for decision_index in range(max_steps):
                observation = api.to_observation_class(observation_dict)
                record = PublicObservationRecord.from_engine(observation)
                if record.state is not None:
                    results = []
                    for perspective in (0, 1):
                        evaluation_started = time.perf_counter_ns()
                        scalar = evaluator.score(record, perspective)
                        evaluator_times.append((time.perf_counter_ns() - evaluation_started) / 1_000_000)
                        result = evaluator.evaluate(record, perspective)
                        results.append(result)
                        evaluated += 1
                        diagnostics.update(result.diagnostics)
                        if not math.isfinite(result.total):
                            nonfinite += 1
                        if not math.isclose(scalar, result.total, rel_tol=0.0, abs_tol=PERSPECTIVE_TOLERANCE):
                            scalar_mismatches += 1
                        if not result.terminal and abs(result.total) >= NONTERMINAL_BOUND:
                            out_of_bound += 1
                        if not result.terminal and not math.isclose(
                            result.total,
                            sum(component.value for component in result.components),
                            rel_tol=0.0,
                            abs_tol=PERSPECTIVE_TOLERANCE,
                        ):
                            reconstruction_failures += 1
                    if not math.isclose(
                        results[0].total,
                        -results[1].total,
                        rel_tol=0.0,
                        abs_tol=PERSPECTIVE_TOLERANCE,
                    ):
                        perspective_failures += 1

                state = observation.current
                if state is not None and state.result != -1:
                    completed += 1
                    terminal += 1
                    break
                if observation.select is None:
                    action = deck
                else:
                    action = conformance_action(observation, api)
                    decisions += 1
                step_started = time.perf_counter_ns()
                observation_dict = game.battle_select(action)
                simulator_times.append((time.perf_counter_ns() - step_started) / 1_000_000)
            else:
                timed_out += 1
        except Exception as exc:
            errors.append(f"game {game_index} decision {decision_index}: {type(exc).__name__}: {exc}")
        finally:
            game.battle_finish()

    evaluator_median = statistics.median(evaluator_times) if evaluator_times else float("inf")
    simulator_median = statistics.median(simulator_times) if simulator_times else float("inf")
    ratio = evaluator_median / simulator_median if simulator_median > 0 and math.isfinite(simulator_median) else None
    return DeckEvaluationResult(
        deck=str(deck_path.resolve()),
        deck_sha256=sha256_file(deck_path),
        games=games,
        completed_games=completed,
        timed_out_games=timed_out,
        decisions=decisions,
        observations_evaluated=evaluated,
        terminal_observations=terminal,
        perspective_failures=perspective_failures,
        reconstruction_failures=reconstruction_failures,
        scalar_breakdown_mismatches=scalar_mismatches,
        nonfinite_scores=nonfinite,
        out_of_bound_scores=out_of_bound,
        evaluator_ms_median=evaluator_median,
        evaluator_ms_p95=_percentile(evaluator_times, 0.95),
        evaluator_ms_max=max(evaluator_times) if evaluator_times else float("inf"),
        simulator_action_ms_median=simulator_median,
        evaluator_to_simulator_median_ratio=ratio,
        diagnostic_counts=dict(sorted(diagnostics.items())),
        errors=errors[:50],
        elapsed_seconds=time.perf_counter() - started,
    )


def run_phase3_suite(
    deck_paths: Sequence[Path],
    *,
    games_per_deck: int,
    max_steps: int,
    report_path: Path,
) -> dict[str, Any]:
    if games_per_deck < 1 or max_steps < 1:
        raise ValueError("games_per_deck and max_steps must be positive")
    api = load_competition_api()
    catalog = CardCatalog.from_engine(api.all_card_data(), api.all_attack())
    evaluator = HandcraftedEvaluator(catalog)
    tactical = run_tactical_suite()
    results = [
        validate_evaluator_on_deck(deck, evaluator, games=games_per_deck, max_steps=max_steps)
        for deck in deck_paths
    ]
    all_evaluator_times = [result.evaluator_ms_median for result in results]
    phase1_report = report_path.with_name("phase1-suite.json")
    phase1_step_medians: dict[str, float] = {}
    if phase1_report.exists():
        import json

        phase1 = json.loads(phase1_report.read_text(encoding="utf-8"))
        phase1_step_medians = {
            Path(deck["deck"]).name: float(deck["step_ms_median"])
            for deck in phase1.get("decks", ())
            if "deck" in deck and "step_ms_median" in deck
        }
    for result in results:
        baseline = phase1_step_medians.get(Path(result.deck).name)
        if baseline and baseline > 0:
            result.evaluator_to_simulator_median_ratio = result.evaluator_ms_median / baseline
    all_ratios = [
        result.evaluator_to_simulator_median_ratio
        for result in results
        if result.evaluator_to_simulator_median_ratio is not None
    ]
    report: dict[str, Any] = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "evaluator_version": EVALUATOR_VERSION,
        "catalog_sha256": catalog.fingerprint,
        "catalog_cards": len(catalog.cards),
        "catalog_attacks": len(catalog.attacks),
        "games_per_deck": games_per_deck,
        "max_steps": max_steps,
        "limits_ms": {
            "median": EVALUATION_MEDIAN_LIMIT_MS,
            "p95": EVALUATION_P95_LIMIT_MS,
            "max": EVALUATION_MAX_LIMIT_MS,
        },
        "performance_reference": "phase1 native search_step median when available; otherwise live battle_select median",
        "tactical": tactical,
        "decks": [result.to_dict() for result in results],
    }
    report["totals"] = {
        "games": sum(result.games for result in results),
        "completed_games": sum(result.completed_games for result in results),
        "timed_out_games": sum(result.timed_out_games for result in results),
        "decisions": sum(result.decisions for result in results),
        "observations_evaluated": sum(result.observations_evaluated for result in results),
        "terminal_observations": sum(result.terminal_observations for result in results),
        "perspective_failures": sum(result.perspective_failures for result in results),
        "reconstruction_failures": sum(result.reconstruction_failures for result in results),
        "scalar_breakdown_mismatches": sum(result.scalar_breakdown_mismatches for result in results),
        "nonfinite_scores": sum(result.nonfinite_scores for result in results),
        "out_of_bound_scores": sum(result.out_of_bound_scores for result in results),
        "deck_median_evaluator_ms": statistics.median(all_evaluator_times) if all_evaluator_times else None,
        "deck_median_evaluator_to_simulator_ratio": statistics.median(all_ratios) if all_ratios else None,
    }
    report["passed"] = bool(tactical["passed"]) and all(result.passed for result in results)
    write_json_atomic(report_path, report)
    return report
