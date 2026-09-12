from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from plan1.data.trajectory import DecisionRecord, public_observation_from_dict
from plan1.game.actions import ActionCandidate
from plan1.model.features import FeatureEncoder, SparseVector


@dataclass(frozen=True, slots=True)
class PolicyValueExample:
    game_id: str
    decision_index: int
    observation_features: SparseVector
    action_features: tuple[SparseVector, ...]
    policy_target: tuple[float, ...]
    value_target: float
    chosen_index: int


class PolicyValueDataset:
    def __init__(self, examples: Iterable[PolicyValueExample]) -> None:
        self.examples = tuple(examples)
        if not self.examples:
            raise ValueError("policy-value dataset cannot be empty")

    def __len__(self) -> int:
        return len(self.examples)

    @classmethod
    def from_decisions(
        cls,
        decisions: Iterable[DecisionRecord],
        encoder: FeatureEncoder,
    ) -> "PolicyValueDataset":
        examples: list[PolicyValueExample] = []
        for decision in decisions:
            record = public_observation_from_dict(decision.observation)
            candidates = tuple(
                ActionCandidate(action.indices, action.option_mask, action.fingerprint)
                for action in decision.legal_actions
            )
            visits = [action.visits for action in decision.legal_actions]
            total_visits = sum(visits)
            if total_visits:
                target = tuple(value / total_visits for value in visits)
            else:
                target = tuple(
                    1.0 if action.fingerprint == decision.chosen_action_fingerprint else 0.0
                    for action in decision.legal_actions
                )
            chosen_index = next(
                index for index, action in enumerate(decision.legal_actions)
                if action.fingerprint == decision.chosen_action_fingerprint
            )
            examples.append(
                PolicyValueExample(
                    game_id=decision.game_id,
                    decision_index=decision.decision_index,
                    observation_features=encoder.value_observation(record, decision.player),
                    action_features=tuple(
                        encoder.action(record, candidate, decision.player) for candidate in candidates
                    ),
                    policy_target=target,
                    value_target=decision.value_target,
                    chosen_index=chosen_index,
                )
            )
        return cls(examples)
