from __future__ import annotations

import importlib
import json
import math
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from plan1.engine.api_loader import load_competition_api
from plan1.engine.conformance import conformance_action, read_deck, repeated_prediction_inputs
from plan1.engine.lifecycle import SearchSession
from plan1.game.actions import ActionGenerator, validate_action
from plan1.game.catalog import CardCatalog
from plan1.game.records import PublicObservationRecord
from plan1.game.vocabulary import CardVocabulary
from plan1.paths import ENGINE_PARENT
from plan1.reproducibility import sha256_file, write_json_atomic


GENERATION_P95_LIMIT_MS = 25.0
GENERATION_MAX_LIMIT_MS = 100.0


@dataclass
class DeckValidationResult:
    deck: str
    deck_sha256: str
    games: int
    completed_games: int
    timed_out_games: int
    decisions: int
    generated_candidates: int
    native_validated_candidates: int
    presearch_preferred_actions: int
    presearch_unvalidated_candidates: int
    exhaustive_decisions: int
    bounded_decisions: int
    max_candidates_at_decision: int
    max_total_action_count: int
    generation_ms_median: float
    generation_ms_p95: float
    generation_ms_max: float
    selection_pairs: dict[str, int]
    unknown_patterns: dict[str, int]
    errors: list[str]
    elapsed_seconds: float

    @property
    def passed(self) -> bool:
        return (
            self.completed_games == self.games
            and self.timed_out_games == 0
            and self.decisions > 0
            and self.generated_candidates > 0
            and self.native_validated_candidates > 0
            and self.presearch_unvalidated_candidates == 0
            and self.generation_ms_p95 <= GENERATION_P95_LIMIT_MS
            and self.generation_ms_max <= GENERATION_MAX_LIMIT_MS
            and not self.unknown_patterns
            and not self.errors
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["passed"] = self.passed
        return value


class FixtureStore:
    def __init__(self) -> None:
        self._records: dict[tuple[int, int], dict[str, Any]] = {}

    def add(self, record: PublicObservationRecord, deck: Path, game_index: int, decision_index: int) -> None:
        selection = record.selection
        if selection is None:
            return
        key = (selection.select_type, selection.context)
        self._records.setdefault(
            key,
            {
                "schema_version": 1,
                "deck": str(deck.resolve()),
                "game_index": game_index,
                "decision_index": decision_index,
                "observation": record.to_dict(),
            },
        )

    @property
    def count(self) -> int:
        return len(self._records)

    def write_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            for key in sorted(self._records):
                handle.write(json.dumps(self._records[key], ensure_ascii=True, separators=(",", ":")) + "\n")
        temporary.replace(path)


def _load_game() -> Any:
    load_competition_api()
    engine_text = str(ENGINE_PARENT.resolve())
    if engine_text not in sys.path:
        sys.path.insert(0, engine_text)
    return importlib.import_module("cg.game")


def _searchable(observation: Any) -> bool:
    return bool(observation.search_begin_input and observation.current is not None and observation.select is not None)


def validate_deck_games(
    deck_path: Path,
    *,
    games: int,
    max_steps: int,
    max_candidates: int,
    seed: int,
    fixtures: FixtureStore,
) -> DeckValidationResult:
    api = load_competition_api()
    game = _load_game()
    deck = read_deck(deck_path)
    generator = ActionGenerator(max_candidates=max_candidates)
    pair_counts: Counter[str] = Counter()
    unknown: Counter[str] = Counter()
    errors: list[str] = []
    completed = timed_out = decisions = generated = native_validated = presearch = unvalidated = 0
    exhaustive = bounded = max_at_decision = max_total = 0
    generation_times: list[float] = []
    started = time.perf_counter()

    for game_index in range(games):
        observation_dict, start_data = game.battle_start(deck, deck)
        if observation_dict is None:
            errors.append(f"game {game_index}: battle_start failed: {start_data}")
            continue
        try:
            for decision_index in range(max_steps):
                observation = api.to_observation_class(observation_dict)
                state = observation.current
                if state is not None and state.result != -1:
                    completed += 1
                    break
                if observation.select is None:
                    # Initial deck registration is a 60-card ID list, not a
                    # selection over option indices.
                    observation_dict = game.battle_select(deck)
                    continue

                record = PublicObservationRecord.from_engine(observation)
                if record.selection is None:
                    errors.append(f"game {game_index} decision {decision_index}: selection conversion lost data")
                    break
                fixtures.add(record, deck_path, game_index, decision_index)
                selection = record.selection
                pair = f"{selection.select_type}:{selection.context}"
                pair_counts[pair] += 1
                preferred = conformance_action(observation, api)
                generation_started = time.perf_counter()
                result = generator.generate(
                    selection,
                    preferred_indices=preferred,
                    seed=seed + game_index * max_steps + decision_index,
                )
                generation_times.append((time.perf_counter() - generation_started) * 1000)
                decisions += 1
                generated += len(result.candidates)
                exhaustive += int(result.exhaustive)
                bounded += int(not result.exhaustive)
                max_at_decision = max(max_at_decision, len(result.candidates))
                max_total = max(max_total, result.total_action_count)
                for issue in result.issues:
                    if issue.startswith("unknown_"):
                        unknown[issue] += 1
                for candidate in result.candidates:
                    validate_action(selection, candidate.indices)
                    if len(candidate.option_mask) != len(selection.options):
                        raise RuntimeError("candidate mask length does not match option count")

                if _searchable(observation):
                    inputs = repeated_prediction_inputs(observation, deck, deck)
                    with SearchSession(api, observation, inputs) as session:
                        root = session.root
                        for candidate in result.candidates:
                            child = session.step(root, candidate.indices)
                            native_validated += 1
                            session.release(child)
                else:
                    presearch += 1
                    # Only the preferred candidate is submitted to the live
                    # battle here. Do not count un-forkable alternatives as
                    # validated or leave them silently unclassified.
                    unvalidated += max(0, len(result.candidates) - 1)

                chosen = result.candidates[0].indices
                observation_dict = game.battle_select(list(chosen))
            else:
                timed_out += 1
        except Exception as exc:
            errors.append(f"game {game_index}: {type(exc).__name__}: {exc}")
        finally:
            game.battle_finish()

    ordered_times = sorted(generation_times)
    median = ordered_times[len(ordered_times) // 2] if ordered_times else float("inf")
    p95_index = max(0, math.ceil(len(ordered_times) * 0.95) - 1)
    p95 = ordered_times[p95_index] if ordered_times else float("inf")
    return DeckValidationResult(
        deck=str(deck_path.resolve()),
        deck_sha256=sha256_file(deck_path),
        games=games,
        completed_games=completed,
        timed_out_games=timed_out,
        decisions=decisions,
        generated_candidates=generated,
        native_validated_candidates=native_validated,
        presearch_preferred_actions=presearch,
        presearch_unvalidated_candidates=unvalidated,
        exhaustive_decisions=exhaustive,
        bounded_decisions=bounded,
        max_candidates_at_decision=max_at_decision,
        max_total_action_count=max_total,
        generation_ms_median=median,
        generation_ms_p95=p95,
        generation_ms_max=max(ordered_times) if ordered_times else float("inf"),
        selection_pairs=dict(sorted(pair_counts.items())),
        unknown_patterns=dict(sorted(unknown.items())),
        errors=errors[:50],
        elapsed_seconds=time.perf_counter() - started,
    )


def run_phase2_suite(
    deck_paths: Sequence[Path],
    *,
    games_per_deck: int,
    max_steps: int,
    max_candidates: int,
    seed: int,
    fixture_path: Path,
    vocabulary_path: Path,
    catalog_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    if games_per_deck < 1 or max_steps < 1 or max_candidates < 1 or seed < 0:
        raise ValueError("game, step, and candidate counts must be positive; seed must be non-negative")
    api = load_competition_api()
    card_data = api.all_card_data()
    attack_data = api.all_attack()
    vocabulary = CardVocabulary.from_card_data(card_data)
    catalog = CardCatalog.from_engine(card_data, attack_data)
    if vocabulary.card_ids != tuple(card.card_id for card in catalog.cards):
        raise RuntimeError("vocabulary and card catalog IDs differ")
    write_json_atomic(vocabulary_path, vocabulary.to_dict())
    write_json_atomic(catalog_path, catalog.to_dict())
    fixtures = FixtureStore()
    results = [
        validate_deck_games(
            deck_path,
            games=games_per_deck,
            max_steps=max_steps,
            max_candidates=max_candidates,
            seed=seed + index * 1_000_000,
            fixtures=fixtures,
        )
        for index, deck_path in enumerate(deck_paths)
    ]
    fixtures.write_jsonl(fixture_path)
    observed_pairs = sorted({pair for result in results for pair in result.selection_pairs})
    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "games_per_deck": games_per_deck,
        "max_steps": max_steps,
        "max_candidates": max_candidates,
        "generation_p95_limit_ms": GENERATION_P95_LIMIT_MS,
        "generation_max_limit_ms": GENERATION_MAX_LIMIT_MS,
        "seed": seed,
        "vocabulary_size": vocabulary.size,
        "card_count": len(vocabulary.card_ids),
        "vocabulary_sha256": vocabulary.fingerprint,
        "vocabulary_file_sha256": sha256_file(vocabulary_path),
        "catalog_card_count": len(catalog.cards),
        "catalog_attack_count": len(catalog.attacks),
        "catalog_sha256": catalog.fingerprint,
        "catalog_file_sha256": sha256_file(catalog_path),
        "fixture_path": str(fixture_path.resolve()),
        "fixture_count": fixtures.count,
        "fixture_sha256": sha256_file(fixture_path),
        "observed_selection_pairs": observed_pairs,
        "all_observed_pairs_have_fixture": fixtures.count == len(observed_pairs),
        "decks": [result.to_dict() for result in results],
    }
    report["totals"] = {
        "games": sum(result.games for result in results),
        "completed_games": sum(result.completed_games for result in results),
        "timed_out_games": sum(result.timed_out_games for result in results),
        "decisions": sum(result.decisions for result in results),
        "generated_candidates": sum(result.generated_candidates for result in results),
        "native_validated_candidates": sum(result.native_validated_candidates for result in results),
        "presearch_preferred_actions": sum(result.presearch_preferred_actions for result in results),
        "presearch_unvalidated_candidates": sum(result.presearch_unvalidated_candidates for result in results),
        "bounded_decisions": sum(result.bounded_decisions for result in results),
    }
    report["passed"] = all(result.passed for result in results) and report["all_observed_pairs_have_fixture"]
    write_json_atomic(report_path, report)
    return report
