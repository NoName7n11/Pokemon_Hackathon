from __future__ import annotations

import json
import multiprocessing
import statistics
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from plan1.data.manifests import SplitPolicy
from plan1.data.replay_buffer import CorpusStore
from plan1.data.trajectory import GameTrajectory
from plan1.engine.conformance import read_deck
from plan1.model.features import FeatureEncoder
from plan1.model.inference import ModelInference
from plan1.model.policy_value import PolicyValueModel
from plan1.model.validation import evaluate_dataset, inference_benchmark
from plan1.paths import ARTIFACT_ROOT
from plan1.reproducibility import canonical_json_hash, derive_seed, sha256_file, write_json_atomic
from plan1.selfplay.config import ReinforcementConfig
from plan1.selfplay.evaluation import evaluate_candidate
from plan1.selfplay.replay import select_replay_window
from plan1.selfplay.worker import SelfPlayJob, SelfPlayResult, play_selfplay_job
from plan1.training.dataset import PolicyValueDataset
from plan1.training.learner import fit_value_calibration, train_model


SELFPLAY_SPLIT = SplitPolicy(75, 25, 0)


class ReinforcementCoordinator:
    def __init__(self, config: ReinforcementConfig, *, config_path: Path) -> None:
        self.config = config
        self.config_path = config_path.resolve()
        self.run_root = ARTIFACT_ROOT / "phase8" / config.run_id
        self.iteration_root = self.run_root / "iterations"
        self.checkpoint_root = self.run_root / "checkpoints"
        self.report_root = self.run_root / "reports"
        self.state_path = self.run_root / "state.json"
        self.stop_path = self.run_root / "STOP"
        self.corpus_root = ARTIFACT_ROOT / "trajectories" / "phase8-selfplay"
        for directory in (
            self.run_root, self.iteration_root, self.checkpoint_root, self.report_root
        ):
            directory.mkdir(parents=True, exist_ok=True)
        self.store = CorpusStore(self.corpus_root, "phase8-selfplay", SELFPLAY_SPLIT)
        self.bootstrap = CorpusStore(
            config.bootstrap_corpus, "phase7-bootstrap", SplitPolicy(70, 15, 15)
        )
        self.config_sha256 = sha256_file(self.config_path)
        self.state = self._load_or_initialize()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load_or_initialize(self) -> dict[str, Any]:
        if self.state_path.exists():
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            if state["run_id"] != self.config.run_id or state["config_sha256"] != self.config_sha256:
                raise ValueError("existing Phase 8 state belongs to a different run/config")
            if state["status"] in {"paused", "running"}:
                state["resume_count"] += 1
                state["history"].append({"at": self._now(), "event": "coordinator_resumed"})
            state["status"] = "running"
            state["updated_utc"] = self._now()
            write_json_atomic(self.state_path, state)
            return state
        initial = self.config.initial_checkpoint.resolve()
        if not initial.exists():
            raise FileNotFoundError(initial)
        state = {
            "schema_version": 1,
            "run_id": self.config.run_id,
            "config_path": str(self.config_path),
            "config_sha256": self.config_sha256,
            "status": "running",
            "created_utc": self._now(),
            "updated_utc": self._now(),
            "resume_count": 0,
            "champion_checkpoint": str(initial),
            "champion_sha256": sha256_file(initial),
            "iterations": [],
            "history": [{"at": self._now(), "event": "coordinator_initialized"}],
        }
        write_json_atomic(self.state_path, state)
        return state

    def _save(self, event: str, **detail: Any) -> None:
        self.state["updated_utc"] = self._now()
        self.state["history"].append({"at": self._now(), "event": event, **detail})
        write_json_atomic(self.state_path, self.state)

    def _iteration(self, index: int) -> dict[str, Any]:
        existing = next((item for item in self.state["iterations"] if item["index"] == index), None)
        if existing is not None:
            return existing
        item = {
            "index": index,
            "status": "pending",
            "champion_before": self.state["champion_checkpoint"],
            "champion_before_sha256": self.state["champion_sha256"],
            "stages": {},
        }
        self.state["iterations"].append(item)
        self._save("iteration_created", iteration=index)
        return item

    def _seed_group(self, iteration: int, ordinal: int, desired_split: str, deck_hash: str) -> str:
        nonce = 0
        while True:
            value = f"{self.config.run_id}-i{iteration:03d}-{desired_split}-{ordinal:04d}-{nonce:03d}"
            assigned = SELFPLAY_SPLIT.assign(
                purpose="training", seed_group=value, deck_hashes=(deck_hash, deck_hash)
            )
            if assigned == desired_split:
                return value
            nonce += 1

    def _jobs(self, iteration: int, champion: Path) -> list[SelfPlayJob]:
        decks = [(path.stem, tuple(read_deck(path))) for path in self.config.deck_paths]
        jobs: list[SelfPlayJob] = []
        validation_start = (
            self.config.selfplay_games_per_iteration - self.config.validation_games_per_iteration
        )
        for game_index in range(self.config.selfplay_games_per_iteration):
            name, deck = decks[game_index % len(decks)]
            desired = "validation" if game_index >= validation_start else "train"
            deck_hash = canonical_json_hash(list(deck))
            seed_group = self._seed_group(iteration, game_index, desired, deck_hash)
            job_id = f"{self.config.run_id}-i{iteration:03d}-g{game_index:04d}"
            jobs.append(
                SelfPlayJob(
                    job_id=job_id,
                    run_id=self.config.run_id,
                    iteration=iteration,
                    game_index=game_index,
                    seed=derive_seed(self.config.root_seed, iteration, game_index),
                    seed_group=seed_group,
                    deck_names=(name, name),
                    decks=(deck, deck),
                    checkpoints=(str(champion), str(champion)),
                    search_config=str(self.config.search_config),
                    max_steps=self.config.max_steps,
                    max_candidates=self.config.max_candidates,
                    temperature_turns=self.config.temperature_turns,
                    visit_temperature=self.config.visit_temperature,
                )
            )
        return jobs

    def _run_selfplay(self, iteration: int, champion: Path) -> dict[str, Any]:
        manifest = self.store.load_manifest()
        existing = {entry.game_id for entry in manifest.entries}
        jobs = [job for job in self._jobs(iteration, champion) if job.job_id not in existing]
        results: list[SelfPlayResult] = []
        if jobs:
            context = multiprocessing.get_context("spawn")
            with ProcessPoolExecutor(max_workers=self.config.workers, mp_context=context) as executor:
                futures = {executor.submit(play_selfplay_job, job): job for job in jobs}
                for future in as_completed(futures):
                    results.append(future.result())
        errors = [f"{result.job_id}:{result.error}" for result in results if result.error]
        if errors:
            raise RuntimeError("self-play workers failed: " + "; ".join(errors[:10]))
        committed = []
        for result in sorted(results, key=lambda item: item.job_id):
            if result.trajectory is None:
                raise RuntimeError(f"worker {result.job_id} returned no trajectory")
            entry = self.store.commit(GameTrajectory.from_dict(result.trajectory))
            committed.append(entry.game_id)
        expected_ids = {job.job_id for job in self._jobs(iteration, champion)}
        final_manifest = self.store.load_manifest()
        entries = [entry for entry in final_manifest.entries if entry.game_id in expected_ids]
        if len(entries) != self.config.selfplay_games_per_iteration:
            raise RuntimeError("self-play iteration is missing committed games")
        split_counts = {
            split: sum(entry.split == split for entry in entries)
            for split in ("train", "validation", "test", "evaluation")
        }
        if split_counts["validation"] != self.config.validation_games_per_iteration:
            raise RuntimeError("self-play validation split count differs from configuration")
        return {
            "expected_games": self.config.selfplay_games_per_iteration,
            "new_games": len(committed),
            "existing_games": len(entries) - len(committed),
            "decisions": sum(entry.decisions for entry in entries),
            "split_counts": split_counts,
            "game_ids": sorted(expected_ids),
            "manifest_sha256": final_manifest.fingerprint,
            "worker_errors": errors,
        }

    def _train(self, iteration: int, champion_path: Path) -> dict[str, Any]:
        train_window = select_replay_window(
            (self.bootstrap, self.store), split="train", max_games=self.config.replay_window_games
        )
        validation_window = select_replay_window(
            (self.bootstrap, self.store), split="validation", max_games=self.config.replay_window_games
        )
        encoder = FeatureEncoder(self.config.model.feature_dimension)
        train_data = PolicyValueDataset.from_decisions(train_window.decisions, encoder)
        validation_data = PolicyValueDataset.from_decisions(validation_window.decisions, encoder)
        champion = PolicyValueModel.load(champion_path)
        baseline_probability = statistics.mean(
            (example.value_target + 1.0) / 2.0 for example in train_data.examples
        )
        metadata = {
            "phase": 8,
            "run_id": self.config.run_id,
            "iteration": iteration,
            "parent_checkpoint": str(champion_path.resolve()),
            "parent_sha256": sha256_file(champion_path),
            "train_game_ids": list(train_window.game_ids),
            "validation_game_ids": list(validation_window.game_ids),
            "source_manifests": list(train_window.source_manifests),
        }
        candidate, training = train_model(
            train_data,
            self.config.model,
            metadata=metadata,
            initial_model=champion,
        )
        calibration = fit_value_calibration(
            candidate, validation_data, baseline_probability=baseline_probability
        )
        candidate_path = self.checkpoint_root / f"candidate-i{iteration:03d}.json"
        payload_sha = candidate.save(candidate_path)
        reloaded = PolicyValueModel.load(candidate_path)
        metrics = evaluate_dataset(
            reloaded, validation_data, baseline_value_probability=baseline_probability
        )
        champion_metrics = evaluate_dataset(
            champion, validation_data, baseline_value_probability=baseline_probability
        )
        inference = inference_benchmark(
            ModelInference(reloaded),
            validation_data,
            repeats=2,
        )
        report = {
            "iteration": iteration,
            "candidate_checkpoint": str(candidate_path.resolve()),
            "candidate_file_sha256": sha256_file(candidate_path),
            "candidate_payload_sha256": payload_sha,
            "parent_checkpoint": str(champion_path.resolve()),
            "parent_sha256": sha256_file(champion_path),
            "replay": {
                "train_games": list(train_window.game_ids),
                "train_decisions": len(train_data),
                "validation_games": list(validation_window.game_ids),
                "validation_decisions": len(validation_data),
                "source_manifests": list(train_window.source_manifests),
            },
            "training": training.to_dict(),
            "calibration": calibration,
            "candidate_validation": metrics,
            "champion_validation": champion_metrics,
            "inference": inference,
            "checkpoint_roundtrip": reloaded.fingerprint == candidate.fingerprint,
        }
        report_path = self.report_root / f"training-i{iteration:03d}.json"
        write_json_atomic(report_path, report)
        report["report_path"] = str(report_path.resolve())
        report["report_sha256"] = sha256_file(report_path)
        return report

    def _check_stop(self, iteration: int, stage: str, stop_after_stage: str | None) -> bool:
        return self.stop_path.exists() or stop_after_stage == stage

    def run(self, *, stop_after_stage: str | None = None) -> dict[str, Any]:
        for index in range(1, self.config.iterations + 1):
            item = self._iteration(index)
            if item["status"] == "complete":
                continue
            champion = Path(item["champion_before"])
            if "selfplay" not in item["stages"]:
                item["status"] = "running_selfplay"
                self._save("selfplay_started", iteration=index)
                item["stages"]["selfplay"] = self._run_selfplay(index, champion)
                self._save("selfplay_complete", iteration=index)
            if self._check_stop(index, "selfplay", stop_after_stage):
                self.state["status"] = "paused"
                self._save("coordinator_paused", iteration=index, stage="selfplay")
                return self.summary(paused=True)

            if "training" not in item["stages"]:
                item["status"] = "running_training"
                self._save("training_started", iteration=index)
                item["stages"]["training"] = self._train(index, champion)
                self._save("training_complete", iteration=index)
            if self._check_stop(index, "training", stop_after_stage):
                self.state["status"] = "paused"
                self._save("coordinator_paused", iteration=index, stage="training")
                return self.summary(paused=True)

            if "evaluation" not in item["stages"]:
                item["status"] = "running_evaluation"
                self._save("evaluation_started", iteration=index)
                candidate = Path(item["stages"]["training"]["candidate_checkpoint"])
                evaluation = evaluate_candidate(
                    candidate,
                    champion,
                    self.config.deck_paths[0],
                    self.config.search_config,
                    games=self.config.evaluation_games,
                    max_steps=self.config.max_steps,
                    minimum_win_rate=self.config.promotion_min_win_rate,
                    iteration=index,
                )
                evaluation_path = self.report_root / f"evaluation-i{index:03d}.json"
                write_json_atomic(evaluation_path, evaluation)
                evaluation["report_path"] = str(evaluation_path.resolve())
                evaluation["report_sha256"] = sha256_file(evaluation_path)
                item["stages"]["evaluation"] = evaluation
                self._save("evaluation_complete", iteration=index)

            evaluation = item["stages"]["evaluation"]
            promoted = bool(evaluation["promotion"]["promoted"])
            candidate_path = item["stages"]["training"]["candidate_checkpoint"]
            if promoted:
                self.state["champion_checkpoint"] = candidate_path
                self.state["champion_sha256"] = sha256_file(Path(candidate_path))
            item["decision"] = evaluation["promotion"]["decision"]
            item["champion_after"] = self.state["champion_checkpoint"]
            item["champion_after_sha256"] = self.state["champion_sha256"]
            item["status"] = "complete"
            iteration_report = {
                "schema_version": 1,
                "run_id": self.config.run_id,
                "iteration": index,
                "champion_before": item["champion_before"],
                "selfplay": item["stages"]["selfplay"],
                "training": item["stages"]["training"],
                "evaluation": item["stages"]["evaluation"],
                "decision": item["decision"],
                "champion_after": item["champion_after"],
            }
            iteration_report["report_identity"] = canonical_json_hash(iteration_report)
            iteration_path = self.iteration_root / f"iteration-{index:03d}.json"
            write_json_atomic(iteration_path, iteration_report)
            item["report_path"] = str(iteration_path.resolve())
            item["report_sha256"] = sha256_file(iteration_path)
            self._save("iteration_complete", iteration=index, decision=item["decision"])

        self.state["status"] = "complete"
        self._save("coordinator_complete")
        summary = self.summary(paused=False)
        summary_path = self.run_root / "phase8-suite.json"
        write_json_atomic(summary_path, summary)
        return summary

    def summary(self, *, paused: bool) -> dict[str, Any]:
        manifest = self.store.load_manifest()
        evaluation_ids = {
            outcome["evaluation_game_id"]
            for item in self.state["iterations"]
            for outcome in item.get("stages", {}).get("evaluation", {}).get("outcomes", [])
        }
        training_ids = {entry.game_id for entry in manifest.entries}
        completed = [item for item in self.state["iterations"] if item["status"] == "complete"]
        decisions = [item.get("decision") for item in completed]
        search_kinds: Counter[str] = Counter()
        searched_targets = multi_visit_targets = non_chosen_visit_targets = 0
        for entry in manifest.entries:
            game = self.store.read_entry(entry)
            for decision in game.decisions:
                kind = str(decision.search.get("kind", "unknown"))
                search_kinds[kind] += 1
                visits = [action.visits for action in decision.legal_actions]
                if kind == "policy_value_puct_selfplay":
                    searched_targets += 1
                    multi_visit_targets += int(sum(visits) > 1)
                    chosen = next(
                        action for action in decision.legal_actions
                        if action.fingerprint == decision.chosen_action_fingerprint
                    )
                    non_chosen_visit_targets += int(
                        any(action.visits > chosen.visits for action in decision.legal_actions)
                    )
        gates = {
            "three_iterations_complete": len(completed) >= 3,
            "resume_verified": self.state["resume_count"] >= 1,
            "all_iterations_decided": all(value in {"promoted", "rejected"} for value in decisions),
            "selfplay_corpus_valid": self.store.validate_all()["passed"],
            "no_evaluation_training_leakage": not (evaluation_ids & training_ids)
                and all(entry.purpose == "training" and entry.split != "evaluation" for entry in manifest.entries),
            "no_worker_errors": all(
                not item["stages"]["selfplay"]["worker_errors"] for item in completed
            ),
            "search_targets_present": searched_targets > 0 and multi_visit_targets > 0,
        }
        summary = {
            "schema_version": 1,
            "created_utc": self._now(),
            "phase": 8,
            "run_id": self.config.run_id,
            "status": "paused" if paused else self.state["status"],
            "config_path": str(self.config_path),
            "config_sha256": self.config_sha256,
            "resume_count": self.state["resume_count"],
            "iterations_requested": self.config.iterations,
            "iterations_complete": len(completed),
            "decisions": decisions,
            "final_champion": self.state["champion_checkpoint"],
            "final_champion_sha256": self.state["champion_sha256"],
            "training_corpus": {
                "root": str(self.corpus_root.resolve()),
                "manifest_sha256": manifest.fingerprint,
                "games": len(manifest.entries),
                "decisions": sum(entry.decisions for entry in manifest.entries),
                "evaluation_ids_intersection": sorted(evaluation_ids & training_ids),
                "search_kinds": dict(sorted(search_kinds.items())),
                "searched_policy_targets": searched_targets,
                "multi_visit_policy_targets": multi_visit_targets,
                "temperature_choices_not_visit_argmax": non_chosen_visit_targets,
            },
            "iterations": completed,
            "gates": gates,
            "passed": not paused and all(gates.values()),
        }
        summary["report_identity"] = canonical_json_hash(summary)
        return summary
