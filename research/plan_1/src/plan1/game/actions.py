from __future__ import annotations

import itertools
import math
import random
from dataclasses import asdict, dataclass
from typing import Iterable, Sequence

from plan1.game.records import SelectionRecord
from plan1.reproducibility import canonical_json_hash


SKILL_ORDER_CONTEXT = 34
KNOWN_SELECT_TYPES = frozenset(range(0, 11))
KNOWN_SELECT_CONTEXTS = frozenset(range(0, 49))


class ActionGenerationError(ValueError):
    """Raised when selection bounds cannot describe a legal complete action."""


@dataclass(frozen=True, slots=True)
class ActionCandidate:
    indices: tuple[int, ...]
    option_mask: tuple[bool, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class GenerationResult:
    candidates: tuple[ActionCandidate, ...]
    ordered: bool
    exhaustive: bool
    total_action_count: int
    issues: tuple[str, ...]


def _action_count(option_count: int, minimum: int, maximum: int, ordered: bool) -> int:
    if ordered:
        return sum(math.perm(option_count, count) for count in range(minimum, maximum + 1))
    return sum(math.comb(option_count, count) for count in range(minimum, maximum + 1))


def _canonical_indices(indices: Iterable[int], *, ordered: bool) -> tuple[int, ...]:
    values = tuple(indices)
    return values if ordered else tuple(sorted(values))


def validate_action(selection: SelectionRecord, indices: Sequence[int]) -> tuple[int, ...]:
    if not isinstance(indices, (list, tuple)):
        raise ActionGenerationError("action indices must be a list or tuple")
    if not all(isinstance(index, int) and not isinstance(index, bool) for index in indices):
        raise ActionGenerationError("action indices must be integers")
    if len(indices) < selection.min_count or len(indices) > selection.max_count:
        raise ActionGenerationError("action count is outside selection bounds")
    if len(set(indices)) != len(indices):
        raise ActionGenerationError("action contains duplicate option indices")
    if any(index < 0 or index >= len(selection.options) for index in indices):
        raise ActionGenerationError("action index is outside the option range")
    return tuple(indices)


class ActionGenerator:
    def __init__(self, max_candidates: int = 128, prefix_fraction: float = 0.75):
        if max_candidates < 1:
            raise ValueError("max_candidates must be positive")
        if not 0 < prefix_fraction <= 1:
            raise ValueError("prefix_fraction must be in (0, 1]")
        self.max_candidates = max_candidates
        self.prefix_fraction = prefix_fraction

    def generate(
        self,
        selection: SelectionRecord,
        *,
        preferred_indices: Sequence[int] | None = None,
        seed: int = 0,
    ) -> GenerationResult:
        option_count = len(selection.options)
        if not 0 <= selection.min_count <= selection.max_count <= option_count:
            raise ActionGenerationError(
                "selection must satisfy 0 <= min_count <= max_count <= option_count"
            )
        ordered = selection.context == SKILL_ORDER_CONTEXT
        issues: list[str] = []
        if selection.select_type not in KNOWN_SELECT_TYPES:
            issues.append(f"unknown_select_type:{selection.select_type}")
        if selection.context not in KNOWN_SELECT_CONTEXTS:
            issues.append(f"unknown_select_context:{selection.context}")

        total = _action_count(option_count, selection.min_count, selection.max_count, ordered)
        if total == 0:
            raise ActionGenerationError("selection describes no legal actions")
        exhaustive = total <= self.max_candidates
        raw: list[tuple[int, ...]] = []
        seen: set[tuple[int, ...]] = set()

        def add(values: Iterable[int]) -> None:
            canonical = _canonical_indices(values, ordered=ordered)
            validate_action(selection, canonical)
            if canonical not in seen and len(raw) < self.max_candidates:
                seen.add(canonical)
                raw.append(canonical)

        if preferred_indices is not None:
            preferred = _canonical_indices(preferred_indices, ordered=ordered)
            try:
                add(preferred)
            except ActionGenerationError:
                issues.append("preferred_action_invalid")

        iterator = self._enumerate(option_count, selection.min_count, selection.max_count, ordered)
        prefix_limit = self.max_candidates if exhaustive else max(1, int(self.max_candidates * self.prefix_fraction))
        for values in iterator:
            add(values)
            if len(raw) >= prefix_limit:
                break

        if not exhaustive and len(raw) < self.max_candidates:
            rng = random.Random(seed ^ int(selection.fingerprint[:16], 16))
            attempts = 0
            attempt_limit = self.max_candidates * 100
            counts = list(range(selection.min_count, selection.max_count + 1))
            while len(raw) < self.max_candidates and attempts < attempt_limit:
                count = counts[rng.randrange(len(counts))]
                values = rng.sample(range(option_count), count)
                if not ordered:
                    values.sort()
                add(values)
                attempts += 1
            if len(raw) < self.max_candidates:
                issues.append("candidate_sampling_saturated")

        if not raw:
            # This is reachable only if a supplied preferred action was invalid
            # and enumeration unexpectedly failed; fail rather than emit nonsense.
            raise ActionGenerationError("no legal action candidate was generated")

        selection_fingerprint = selection.fingerprint
        candidates = tuple(
            self._candidate(selection, indices, ordered, selection_fingerprint)
            for indices in raw
        )
        if len({candidate.fingerprint for candidate in candidates}) != len(candidates):
            raise ActionGenerationError("duplicate action fingerprints generated")
        return GenerationResult(
            candidates=candidates,
            ordered=ordered,
            exhaustive=exhaustive,
            total_action_count=total,
            issues=tuple(issues),
        )

    @staticmethod
    def _enumerate(option_count: int, minimum: int, maximum: int, ordered: bool):
        indices = range(option_count)
        for count in range(minimum, maximum + 1):
            yield from (itertools.permutations(indices, count) if ordered else itertools.combinations(indices, count))

    @staticmethod
    def _candidate(
        selection: SelectionRecord,
        indices: tuple[int, ...],
        ordered: bool,
        selection_fingerprint: str,
    ) -> ActionCandidate:
        selected = [
            {"index": index, "option": asdict(selection.options[index])}
            for index in indices
        ]
        payload = {
            "selection": selection_fingerprint,
            "ordered": ordered,
            "selected": selected,
        }
        selected_set = set(indices)
        return ActionCandidate(
            indices=indices,
            option_mask=tuple(index in selected_set for index in range(len(selection.options))),
            fingerprint=canonical_json_hash(payload),
        )
