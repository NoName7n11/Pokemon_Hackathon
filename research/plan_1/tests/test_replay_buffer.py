from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import _path  # noqa: F401

from plan1.data.manifests import ManifestError, SplitPolicy, validate_split_isolation
from plan1.data.replay_buffer import CorpusStore, ReplayReader, RetentionPolicy
from plan1.data.trajectory import TrajectoryError
from plan1.reproducibility import sha256_file

from test_trajectory import fixture_game


class ReplayBufferTests(unittest.TestCase):
    def test_atomic_round_trip_manifest_chain_and_idempotent_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CorpusStore(Path(temporary), "corpus")
            game = fixture_game()
            first = store.commit(game)
            repeated = store.commit(game)
            self.assertEqual(first, repeated)
            manifest = store.load_manifest()
            self.assertEqual(manifest.revision, 1)
            self.assertEqual(len(manifest.entries), 1)
            previous = store.manifests / "manifest-000000.json"
            self.assertEqual(manifest.previous_manifest_sha256, sha256_file(previous))
            self.assertEqual(store.read_entry(first), game)
            self.assertTrue(store.validate_all()["passed"])

    def test_same_game_id_with_different_content_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CorpusStore(Path(temporary), "corpus")
            store.commit(fixture_game())
            conflicting = replace(fixture_game(), run_id="other-run")
            with self.assertRaises(ManifestError):
                store.commit(conflicting)

    def test_evaluation_games_are_never_returned_by_training_reader(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CorpusStore(Path(temporary), "corpus", SplitPolicy(100, 0, 0))
            store.commit(fixture_game("train-game", purpose="training", seed_group="train-group"))
            store.commit(fixture_game("eval-game", purpose="evaluation", seed=11, seed_group="eval-group"))
            games = list(ReplayReader(store, ("train",)).games())
            self.assertEqual([game.game_id for game in games], ["train-game"])
            self.assertEqual(store.load_manifest().entries[1].split, "evaluation")
            with self.assertRaises(ValueError):
                ReplayReader(store, ("evaluation",))

    def test_seed_group_cannot_cross_splits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CorpusStore(Path(temporary), "corpus", SplitPolicy(100, 0, 0))
            training = store.commit(fixture_game("train", seed_group="shared"))
            evaluation_game = replace(fixture_game("eval", purpose="evaluation", seed_group="shared"), purpose="evaluation")
            evaluation = replace(training, game_id="eval", purpose="evaluation", split="evaluation")
            with self.assertRaises(ManifestError):
                validate_split_isolation((training, evaluation))

    def test_corruption_is_detected_and_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CorpusStore(Path(temporary), "corpus")
            entry = store.commit(fixture_game())
            path = store.root / entry.relative_path
            path.write_bytes(path.read_bytes()[:20])
            self.assertFalse(store.validate_all()["passed"])
            repaired = store.repair()
            self.assertTrue(repaired["changed"])
            self.assertEqual(len(store.load_manifest().entries), 0)
            self.assertEqual(len(list(store.quarantine.glob("*.json.gz"))), 1)

    def test_complete_manifest_chain_is_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CorpusStore(Path(temporary), "corpus", SplitPolicy(100, 0, 0))
            store.commit(fixture_game("one", seed=1, seed_group="one"))
            store.commit(fixture_game("two", seed=2, seed_group="two"))
            revision_zero = store.manifests / "manifest-000000.json"
            payload = json.loads(revision_zero.read_text(encoding="utf-8"))
            payload["created_utc"] = "2026-01-01T00:00:00+00:00"
            revision_zero.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ManifestError):
                store.load_manifest()

    def test_interrupted_temporary_file_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CorpusStore(Path(temporary), "corpus")
            (store.games / ".partial.tmp").write_bytes(b"partial")
            self.assertTrue(store.validate_all()["passed"])
            self.assertEqual(len(store.load_manifest().entries), 0)

    def test_retention_is_recoverable_and_never_retires_evaluation_first(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CorpusStore(Path(temporary), "corpus", SplitPolicy(100, 0, 0))
            store.commit(fixture_game("old", seed=1, seed_group="a", created_utc="2026-01-01T00:00:00+00:00"))
            store.commit(fixture_game("new", seed=2, seed_group="b", created_utc="2026-01-02T00:00:00+00:00"))
            store.commit(fixture_game("eval", purpose="evaluation", seed=3, seed_group="c", created_utc="2025-01-01T00:00:00+00:00"))
            result = store.apply_retention(RetentionPolicy(max_games=2))
            self.assertEqual(result["retired"], ["old"])
            self.assertEqual(len(list(store.retired.glob("old-*.json.gz"))), 1)
            self.assertEqual({entry.game_id for entry in store.load_manifest().entries}, {"new", "eval"})


if __name__ == "__main__":
    unittest.main()
