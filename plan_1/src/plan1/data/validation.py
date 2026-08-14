from __future__ import annotations

import json
import shutil
import statistics
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from plan1.data.generator import HeuristicCorpusGenerator, deck_identity
from plan1.data.manifests import SplitPolicy
from plan1.data.replay_buffer import CorpusStore, ReplayReader, RetentionPolicy
from plan1.engine.conformance import read_deck
from plan1.reproducibility import sha256_directory, sha256_file, write_json_atomic


def _store_summary(store: CorpusStore) -> dict[str, Any]:
    manifest = store.load_manifest()
    split_counts = Counter(entry.split for entry in manifest.entries)
    purpose_counts = Counter(entry.purpose for entry in manifest.entries)
    total_bytes = sum(entry.bytes for entry in manifest.entries)
    total_decisions = sum(entry.decisions for entry in manifest.entries)
    raw_bytes = 0
    replay_hashes = []
    for entry in manifest.entries:
        trajectory = store.read_entry(entry)
        raw_bytes += len(
            (json.dumps(trajectory.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")
        )
        replay_hashes.append(trajectory.fingerprint == entry.content_sha256)
    return {
        "games": len(manifest.entries),
        "decisions": total_decisions,
        "compressed_bytes": total_bytes,
        "raw_json_bytes": raw_bytes,
        "compression_ratio": total_bytes / raw_bytes if raw_bytes else None,
        "bytes_per_game": total_bytes / len(manifest.entries) if manifest.entries else None,
        "bytes_per_decision": total_bytes / total_decisions if total_decisions else None,
        "splits": dict(sorted(split_counts.items())),
        "purposes": dict(sorted(purpose_counts.items())),
        "manifest_revision": manifest.revision,
        "manifest_fingerprint": manifest.fingerprint,
        "exact_content_replay": all(replay_hashes),
    }


def run_phase6_suite(
    deck_paths: Sequence[Path],
    *,
    corpus_root: Path,
    run_id: str,
    games: int,
    evaluation_games: int,
    root_seed: int,
    max_steps: int,
    max_candidates: int,
    report_path: Path,
    scratch_root: Path,
) -> dict[str, Any]:
    if games < 4 or evaluation_games < 1:
        raise ValueError("Phase 6 suite requires at least four training and one evaluation game")
    decks = tuple(deck_identity(path.stem, read_deck(path)) for path in deck_paths)
    if not decks:
        raise ValueError("at least one deck is required")
    policy = SplitPolicy(60, 20, 20)
    started = time.perf_counter()

    store = CorpusStore(corpus_root, "phase6-bootstrap", policy)
    first_target = games // 2
    first = HeuristicCorpusGenerator(
        store, decks, run_id=run_id, root_seed=root_seed, purpose="training",
        max_candidates=max_candidates, max_steps=max_steps,
    ).generate(first_target)
    reopened = CorpusStore(corpus_root, "phase6-bootstrap", policy)
    second = HeuristicCorpusGenerator(
        reopened, decks, run_id=run_id, root_seed=root_seed, purpose="training",
        max_candidates=max_candidates, max_steps=max_steps,
    ).generate(games)
    no_op = HeuristicCorpusGenerator(
        CorpusStore(corpus_root, "phase6-bootstrap", policy), decks,
        run_id=run_id, root_seed=root_seed, purpose="training",
        max_candidates=max_candidates, max_steps=max_steps,
    ).generate(games)
    evaluation = HeuristicCorpusGenerator(
        CorpusStore(corpus_root, "phase6-bootstrap", policy), decks,
        run_id=f"{run_id}-evaluation", root_seed=root_seed + 10_000, purpose="evaluation",
        max_candidates=max_candidates, max_steps=max_steps,
    ).generate(evaluation_games)

    store = CorpusStore(corpus_root, "phase6-bootstrap", policy)
    validation = store.validate_all()
    summary = _store_summary(store)
    training_reader = ReplayReader(store, ("train", "validation", "test"))
    training_games = list(training_reader.games())
    evaluation_ids = {
        entry.game_id for entry in store.load_manifest().entries if entry.purpose == "evaluation"
    }
    reader_ids = {game.game_id for game in training_games}
    distributions = training_reader.distribution()

    scratch = scratch_root.resolve()
    if scratch.exists():
        shutil.rmtree(scratch)
    shutil.copytree(corpus_root, scratch)
    corrupt_store = CorpusStore(scratch, "phase6-bootstrap", policy)
    corrupt_entry = next(entry for entry in corrupt_store.load_manifest().entries if entry.purpose == "training")
    corrupt_path = scratch / corrupt_entry.relative_path
    corrupt_path.write_bytes(corrupt_path.read_bytes()[:32])
    pre_repair = corrupt_store.validate_all()
    repair = corrupt_store.repair()
    post_repair = corrupt_store.validate_all()
    retention = corrupt_store.apply_retention(RetentionPolicy(max_games=max(1, len(corrupt_store.load_manifest().entries) - 1)))
    post_retention = corrupt_store.validate_all()

    generation_seconds = first.elapsed_seconds + second.elapsed_seconds + evaluation.elapsed_seconds
    generated_games = first.generated_games + second.generated_games + evaluation.generated_games
    generated_decisions = first.decisions + second.decisions + evaluation.decisions
    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase": 6,
        "mode": "trajectory_pipeline_validation",
        "configuration": {
            "run_id": run_id, "games": games, "evaluation_games": evaluation_games,
            "root_seed": root_seed, "max_steps": max_steps, "max_candidates": max_candidates,
            "split_policy": asdict(policy),
        },
        "decks": [
            {"path": str(path.resolve()), "file_sha256": sha256_file(path), "deck_sha256": deck.sha256}
            for path, deck in zip(deck_paths, decks)
        ],
        "resume": {
            "initial": asdict(first), "extension": asdict(second), "no_op": asdict(no_op),
            "initial_target": first_target,
            "passed": bool(
                first.completed_games == first_target
                and second.existing_games == first_target
                and second.completed_games == games - first_target
                and no_op.existing_games == games
                and no_op.generated_games == 0
                and not first.errors and not second.errors and not no_op.errors
            ),
        },
        "evaluation_generation": asdict(evaluation),
        "corpus": summary,
        "validation": validation,
        "replay": {
            "mode": "canonical_record_replay",
            "native_resimulation_supported": False,
            "native_resimulation_reason": "local battle_start exposes no seed input",
            "training_reader_games": len(training_games),
            "evaluation_ids_in_training_reader": sorted(evaluation_ids & reader_ids),
            "distribution": distributions,
            "passed": summary["exact_content_replay"] and not (evaluation_ids & reader_ids),
        },
        "corruption_recovery": {
            "pre_repair": pre_repair, "repair": repair, "post_repair": post_repair,
            "passed": bool(not pre_repair["passed"] and repair["changed"] and post_repair["passed"]),
        },
        "retention": {
            "result": retention, "post_retention": post_retention,
            "passed": bool(retention["limits_met"] and post_retention["passed"]),
        },
        "performance": {
            "generation_seconds": generation_seconds,
            "generated_games": generated_games,
            "generated_decisions": generated_decisions,
            "games_per_second": generated_games / generation_seconds if generation_seconds else None,
            "decisions_per_second": generated_decisions / generation_seconds if generation_seconds else None,
        },
        "corpus_directory_sha256": sha256_directory(corpus_root),
        "duration_seconds": time.perf_counter() - started,
    }
    manifest_entries = store.load_manifest().entries
    seed_groups = [entry.seed_group for entry in manifest_entries]
    report["split_isolation"] = {
        "game_level_only": len({entry.game_id for entry in manifest_entries}) == len(manifest_entries),
        "seed_groups_unique": len(seed_groups) == len(set(seed_groups)),
        "evaluation_separate": not (evaluation_ids & reader_ids),
    }
    report["passed"] = bool(
        report["resume"]["passed"]
        and evaluation.completed_games == evaluation_games and not evaluation.errors
        and validation["passed"]
        and report["replay"]["passed"]
        and report["corruption_recovery"]["passed"]
        and report["retention"]["passed"]
        and all(report["split_isolation"].values())
        and summary["games"] == games + evaluation_games
    )
    write_json_atomic(report_path, report)
    return report
