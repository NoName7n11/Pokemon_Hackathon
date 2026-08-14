from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from plan1.model.features import SparseVector
from plan1.reproducibility import canonical_json_hash, write_json_atomic


MODEL_SCHEMA_VERSION = 1
MODEL_VERSION = "hashed-linear-policy-value-v1"


@dataclass(frozen=True, slots=True)
class ModelConfig:
    feature_dimension: int = 8192
    learning_rate: float = 0.08
    value_learning_rate: float = 0.005
    l2: float = 1e-6
    epochs: int = 30
    value_epochs: int = 5
    seed: int = 20260814

    def validate(self) -> None:
        if self.feature_dimension < 128 or self.feature_dimension & (self.feature_dimension - 1):
            raise ValueError("feature_dimension must be a power of two >= 128")
        if self.learning_rate <= 0 or self.value_learning_rate <= 0 or self.l2 < 0:
            raise ValueError("learning rates must be positive and l2 non-negative")
        if self.epochs < 1 or self.value_epochs < 1 or self.seed < 0:
            raise ValueError("epochs and value_epochs must be positive and seed non-negative")


def dot(weights: Sequence[float], features: SparseVector) -> float:
    return sum(weights[index] * value for index, value in features)


def softmax(logits: Sequence[float]) -> tuple[float, ...]:
    if not logits:
        raise ValueError("softmax requires at least one logit")
    maximum = max(logits)
    exponents = [math.exp(max(-60.0, min(60.0, value - maximum))) for value in logits]
    total = sum(exponents)
    return tuple(value / total for value in exponents)


class PolicyValueModel:
    def __init__(
        self,
        config: ModelConfig,
        *,
        policy_weights: Sequence[float] | None = None,
        value_weights: Sequence[float] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        config.validate()
        self.config = config
        size = config.feature_dimension
        self.policy_weights = list(policy_weights) if policy_weights is not None else [0.0] * size
        self.value_weights = list(value_weights) if value_weights is not None else [0.0] * size
        if len(self.policy_weights) != size or len(self.value_weights) != size:
            raise ValueError("checkpoint weight dimensions differ from model config")
        if not all(math.isfinite(value) for value in self.policy_weights + self.value_weights):
            raise ValueError("model weights must be finite")
        self.metadata = dict(metadata or {})

    def policy_logits(self, action_features: Sequence[SparseVector]) -> tuple[float, ...]:
        return tuple(dot(self.policy_weights, features) for features in action_features)

    def policy(self, action_features: Sequence[SparseVector]) -> tuple[float, ...]:
        return softmax(self.policy_logits(action_features))

    def raw_value_logit(self, observation_features: SparseVector) -> float:
        return dot(self.value_weights, observation_features)

    def value(self, observation_features: SparseVector) -> float:
        raw = self.raw_value_logit(observation_features)
        calibration = self.metadata.get("value_calibration")
        if calibration is not None:
            raw = float(calibration["scale"]) * raw + float(calibration["bias"])
        return math.tanh(raw)

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": MODEL_SCHEMA_VERSION,
            "model_version": MODEL_VERSION,
            "config": asdict(self.config),
            "policy_weights": self.policy_weights,
            "value_weights": self.value_weights,
            "metadata": self.metadata,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_json_hash(self.payload())

    def save(self, path: Path) -> str:
        payload = self.payload()
        payload["payload_sha256"] = canonical_json_hash(payload)
        write_json_atomic(path, payload)
        return payload["payload_sha256"]

    @classmethod
    def load(cls, path: Path) -> "PolicyValueModel":
        data = json.loads(path.read_text(encoding="utf-8"))
        expected = {
            "schema_version", "model_version", "config", "policy_weights",
            "value_weights", "metadata", "payload_sha256",
        }
        if set(data) != expected:
            raise ValueError("checkpoint keys differ from the strict schema")
        checksum = data.pop("payload_sha256")
        if canonical_json_hash(data) != checksum:
            raise ValueError("checkpoint checksum mismatch")
        if data["schema_version"] != MODEL_SCHEMA_VERSION or data["model_version"] != MODEL_VERSION:
            raise ValueError("unsupported checkpoint version")
        config_data = data["config"]
        if set(config_data) != set(ModelConfig.__dataclass_fields__):
            raise ValueError("checkpoint model config keys differ")
        return cls(
            ModelConfig(**config_data),
            policy_weights=data["policy_weights"],
            value_weights=data["value_weights"],
            metadata=data["metadata"],
        )
