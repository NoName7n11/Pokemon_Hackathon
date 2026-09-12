from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from typing import Any

from plan1.model.policy_value import ModelConfig, PolicyValueModel, dot, softmax
from plan1.training.dataset import PolicyValueDataset


@dataclass(frozen=True, slots=True)
class TrainingReport:
    epochs: int
    examples: int
    initial_policy_loss: float
    final_policy_loss: float
    initial_value_loss: float
    final_value_loss: float
    epoch_metrics: tuple[dict[str, float], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _losses(model: PolicyValueModel, dataset: PolicyValueDataset) -> tuple[float, float]:
    policy_loss = value_loss = 0.0
    for example in dataset.examples:
        probabilities = model.policy(example.action_features)
        policy_loss -= sum(
            target * math.log(max(probability, 1e-12))
            for target, probability in zip(example.policy_target, probabilities)
        )
        prediction = model.value(example.observation_features)
        value_loss += (prediction - example.value_target) ** 2
    count = len(dataset)
    return policy_loss / count, value_loss / count


def train_model(
    dataset: PolicyValueDataset,
    config: ModelConfig,
    *,
    metadata: dict[str, Any] | None = None,
    initial_model: PolicyValueModel | None = None,
) -> tuple[PolicyValueModel, TrainingReport]:
    if initial_model is not None and initial_model.config.feature_dimension != config.feature_dimension:
        raise ValueError("initial model feature dimension differs from training config")
    model = PolicyValueModel(
        config,
        policy_weights=None if initial_model is None else initial_model.policy_weights,
        value_weights=None if initial_model is None else initial_model.value_weights,
        metadata=metadata,
    )
    initial_policy, initial_value = _losses(model, dataset)
    policy_accumulator = [1e-8] * config.feature_dimension
    value_accumulator = [1e-8] * config.feature_dimension
    rng = random.Random(config.seed)
    epoch_metrics: list[dict[str, float]] = []
    order = list(range(len(dataset)))
    for epoch in range(config.epochs):
        rng.shuffle(order)
        for example_index in order:
            example = dataset.examples[example_index]
            logits = [dot(model.policy_weights, features) for features in example.action_features]
            probabilities = softmax(logits)
            policy_gradient: dict[int, float] = {}
            for probability, target, features in zip(
                probabilities, example.policy_target, example.action_features
            ):
                coefficient = probability - target
                for index, value in features:
                    policy_gradient[index] = policy_gradient.get(index, 0.0) + coefficient * value
            for index, gradient in policy_gradient.items():
                gradient += config.l2 * model.policy_weights[index]
                policy_accumulator[index] += gradient * gradient
                model.policy_weights[index] -= (
                    config.learning_rate * gradient / math.sqrt(policy_accumulator[index])
                )

            if epoch < config.value_epochs:
                raw_value = dot(model.value_weights, example.observation_features)
                prediction = math.tanh(raw_value)
                coefficient = 2.0 * (prediction - example.value_target) * (1.0 - prediction * prediction)
                for index, value in example.observation_features:
                    gradient = coefficient * value + config.l2 * model.value_weights[index]
                    value_accumulator[index] += gradient * gradient
                    model.value_weights[index] -= (
                        config.value_learning_rate * gradient / math.sqrt(value_accumulator[index])
                    )
        policy_loss, value_loss = _losses(model, dataset)
        epoch_metrics.append(
            {"epoch": float(epoch + 1), "policy_loss": policy_loss, "value_loss": value_loss}
        )
    final_policy, final_value = _losses(model, dataset)
    return model, TrainingReport(
        epochs=config.epochs,
        examples=len(dataset),
        initial_policy_loss=initial_policy,
        final_policy_loss=final_policy,
        initial_value_loss=initial_value,
        final_value_loss=final_value,
        epoch_metrics=tuple(epoch_metrics),
    )


def fit_value_calibration(
    model: PolicyValueModel,
    validation: PolicyValueDataset,
    *,
    baseline_probability: float,
) -> dict[str, float | int]:
    """Fit affine tanh calibration on validation games only."""
    clipped = max(1e-6, min(1.0 - 1e-6, baseline_probability))
    center_bias = math.atanh(2.0 * clipped - 1.0)
    by_game: dict[str, list[tuple[float, float]]] = {}
    for example in validation.examples:
        by_game.setdefault(example.game_id, []).append(
            (
                model.raw_value_logit(example.observation_features),
                (example.value_target + 1.0) / 2.0,
            )
        )

    def score(scale: float, bias: float) -> float:
        game_losses = []
        for samples in by_game.values():
            loss = 0.0
            for raw, target in samples:
                prediction = (math.tanh(scale * raw + bias) + 1.0) / 2.0
                loss += (prediction - target) ** 2
            game_losses.append(loss / len(samples))
        return sum(game_losses) / len(game_losses)

    best_scale = 0.0
    best_bias = center_bias
    best_loss = score(best_scale, best_bias)
    for scale_step in range(41):
        scale = scale_step / 40.0
        for bias_step in range(-20, 21):
            bias = center_bias + bias_step / 40.0
            loss = score(scale, bias)
            candidate = (loss, scale, abs(bias - center_bias), bias)
            current = (best_loss, best_scale, abs(best_bias - center_bias), best_bias)
            if candidate < current:
                best_loss, best_scale, best_bias = loss, scale, bias
    model.metadata["value_calibration"] = {
        "kind": "affine-tanh-v1",
        "scale": best_scale,
        "bias": best_bias,
        "validation_game_balanced_brier": best_loss,
        "validation_games": len(by_game),
    }
    return {
        "scale": best_scale,
        "bias": best_bias,
        "game_balanced_brier": best_loss,
        "games": len(by_game),
        "examples": len(validation),
    }
