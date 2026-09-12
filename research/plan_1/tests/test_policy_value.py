from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401

from plan1.model.features import FeatureEncoder
from plan1.model.inference import ModelInference
from plan1.model.policy_value import ModelConfig, PolicyValueModel
from plan1.training.dataset import PolicyValueDataset
from plan1.training.learner import fit_value_calibration, train_model

from test_trajectory import fixture_game


class PolicyValueTests(unittest.TestCase):
    def test_dataset_masks_legal_actions_and_training_reduces_losses(self) -> None:
        game = fixture_game()
        encoder = FeatureEncoder(256)
        dataset = PolicyValueDataset.from_decisions(game.decisions, encoder)
        model, report = train_model(
            dataset,
            ModelConfig(feature_dimension=256, epochs=12, learning_rate=0.1, value_learning_rate=0.1),
        )
        self.assertEqual(len(dataset.examples[0].action_features), len(game.decisions[0].legal_actions))
        self.assertLess(report.final_policy_loss, report.initial_policy_loss)
        self.assertLess(report.final_value_loss, report.initial_value_loss)
        self.assertAlmostEqual(sum(model.policy(dataset.examples[0].action_features)), 1.0)

    def test_checkpoint_round_trip_and_tamper_detection(self) -> None:
        model = PolicyValueModel(ModelConfig(feature_dimension=128, epochs=1))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "model.json"
            model.save(path)
            loaded = PolicyValueModel.load(path)
            self.assertEqual(loaded.fingerprint, model.fingerprint)
            path.write_text(path.read_text(encoding="utf-8").replace("0.0", "0.1", 1), encoding="utf-8")
            with self.assertRaises(ValueError):
                PolicyValueModel.load(path)

    def test_live_inference_returns_one_prior_per_legal_action(self) -> None:
        game = fixture_game()
        decision = game.decisions[0]
        from plan1.data.trajectory import public_observation_from_dict
        from plan1.game.actions import ActionCandidate

        record = public_observation_from_dict(decision.observation)
        candidates = tuple(
            ActionCandidate(action.indices, action.option_mask, action.fingerprint)
            for action in decision.legal_actions
        )
        inference = ModelInference(PolicyValueModel(ModelConfig(feature_dimension=128, epochs=1)))
        priors = inference.policy(record, candidates, 0)
        self.assertEqual(len(priors), len(candidates))
        self.assertAlmostEqual(sum(priors), 1.0)
        self.assertGreaterEqual(inference.value(record, 0), -1.0)
        self.assertLessEqual(inference.value(record, 0), 1.0)

    def test_value_calibration_is_checkpointed(self) -> None:
        game = fixture_game()
        encoder = FeatureEncoder(128)
        dataset = PolicyValueDataset.from_decisions(game.decisions, encoder)
        model, _ = train_model(
            dataset,
            ModelConfig(feature_dimension=128, epochs=2, value_epochs=1),
        )
        calibration = fit_value_calibration(model, dataset, baseline_probability=0.5)
        self.assertIn("value_calibration", model.metadata)
        self.assertGreaterEqual(calibration["scale"], 0.0)
        self.assertLessEqual(calibration["scale"], 1.0)


if __name__ == "__main__":
    unittest.main()
