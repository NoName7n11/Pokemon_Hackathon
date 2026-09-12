from __future__ import annotations

from typing import Sequence

from plan1.game.actions import ActionCandidate
from plan1.game.records import PublicObservationRecord
from plan1.model.features import FeatureEncoder
from plan1.model.policy_value import PolicyValueModel


class ModelInference:
    """Observation-limited policy/value inference used by PUCT."""

    def __init__(self, model: PolicyValueModel) -> None:
        self.model = model
        self.encoder = FeatureEncoder(model.config.feature_dimension)

    def policy(
        self,
        record: PublicObservationRecord,
        candidates: Sequence[ActionCandidate],
        perspective: int,
    ) -> tuple[float, ...]:
        features = [self.encoder.action(record, candidate, perspective) for candidate in candidates]
        return self.model.policy(features)

    def value(self, record: PublicObservationRecord, perspective: int) -> float:
        return self.model.value(self.encoder.value_observation(record, perspective))
