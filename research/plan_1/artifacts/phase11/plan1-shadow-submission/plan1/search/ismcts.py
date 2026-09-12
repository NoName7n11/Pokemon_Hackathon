from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Sequence

from plan1.belief.information_set import information_set_key
from plan1.belief.sampler import HiddenStateSampler
from plan1.game.records import PublicObservationRecord
from plan1.search.mcts import SearchResult, UCTSearch


ISMCTS_VERSION = "root-sampled-ismcts-v1"


@dataclass(frozen=True, slots=True)
class ISMCTSEdgeTrace:
    action: tuple[int, ...]
    fingerprint: str
    visits: int
    value_sum: float
    mean_value: float
    determinizations: int


@dataclass(frozen=True, slots=True)
class ISMCTSTrace:
    version: str
    seed: int
    information_set_key: str
    requested_determinizations: int
    sampled_determinizations: int
    completed_determinizations: int
    unique_determinizations: int
    duplicate_determinizations: int
    belief_fallbacks: int
    inner_search_fallbacks: int
    compatible_components_min: int | None
    elapsed_ms: float
    fallback_used: bool
    fallback_reason: str | None
    edges: tuple[ISMCTSEdgeTrace, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ISMCTSResult:
    action: tuple[int, ...]
    fallback_action: tuple[int, ...]
    trace: ISMCTSTrace


@dataclass(slots=True)
class _AggregateEdge:
    action: tuple[int, ...]
    fingerprint: str
    visits: int = 0
    value_sum: float = 0.0
    determinizations: int = 0

    @property
    def mean_value(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0


class RootSampledISMCTS:
    """Aggregate public-root action statistics over sampled hidden worlds.

    Each determinization owns a fresh native search session. Statistics are
    merged only under the public information-set key and action fingerprint;
    sampled hidden identities never become policy features or node keys.
    """

    def __init__(
        self,
        searcher: UCTSearch,
        sampler: HiddenStateSampler,
        *,
        determinizations: int,
    ) -> None:
        if determinizations < 1:
            raise ValueError("determinizations must be positive")
        self.searcher = searcher
        self.sampler = sampler
        self.determinizations = determinizations

    def search(
        self,
        observation: Any,
        *,
        seed: int,
        fallback_action: Sequence[int] | None = None,
    ) -> ISMCTSResult:
        started = time.perf_counter()
        record = PublicObservationRecord.from_engine(observation)
        root_key = information_set_key(record, record.state.acting_player if record.state is not None else 0)
        fallback = tuple(fallback_action) if fallback_action is not None else self.searcher._fallback(observation)
        aggregates: dict[str, _AggregateEdge] = {}
        sampled: set[str] = set()
        sampled_count = 0
        errors: list[str] = []
        completed = 0
        belief_fallbacks = 0
        inner_search_fallbacks = 0
        compatible_counts: list[int] = []

        for index in range(self.determinizations):
            rng = random.Random(seed + index * 1_000_003)
            try:
                sample = self.sampler.sample(record, rng)
                sampled_count += 1
                sampled.add(sample.fingerprint)
                belief_fallbacks += int(sample.fallback_used)
                compatible_counts.append(sample.compatible_components)
                result: SearchResult = self.searcher.search(
                    observation,
                    sample.inputs,
                    seed=seed + index * 7_919,
                    fallback_action=fallback,
                )
            except Exception as exc:
                if len(errors) < 25:
                    errors.append(f"determinization_{index}:{type(exc).__name__}:{exc}")
                continue
            if result.trace.fallback_used:
                inner_search_fallbacks += 1
                continue
            completed += 1
            for edge in result.trace.root_edges:
                aggregate = aggregates.setdefault(
                    edge.fingerprint,
                    _AggregateEdge(action=edge.action, fingerprint=edge.fingerprint),
                )
                aggregate.visits += edge.visits
                aggregate.value_sum += edge.value_sum
                aggregate.determinizations += 1

        reason = None
        if not aggregates:
            action = fallback
            reason = "no_completed_root_edge"
        else:
            chosen = min(
                aggregates.values(),
                key=lambda edge: (-edge.visits, -edge.mean_value, edge.fingerprint),
            )
            action = chosen.action
        edges = tuple(
            ISMCTSEdgeTrace(
                action=edge.action,
                fingerprint=edge.fingerprint,
                visits=edge.visits,
                value_sum=edge.value_sum,
                mean_value=edge.mean_value,
                determinizations=edge.determinizations,
            )
            for edge in sorted(aggregates.values(), key=lambda item: item.fingerprint)
        )
        return ISMCTSResult(
            action=action,
            fallback_action=fallback,
            trace=ISMCTSTrace(
                version=ISMCTS_VERSION,
                seed=seed,
                information_set_key=root_key,
                requested_determinizations=self.determinizations,
                sampled_determinizations=sampled_count,
                completed_determinizations=completed,
                unique_determinizations=len(sampled),
                duplicate_determinizations=max(0, sampled_count - len(sampled)),
                belief_fallbacks=belief_fallbacks,
                inner_search_fallbacks=inner_search_fallbacks,
                compatible_components_min=min(compatible_counts) if compatible_counts else None,
                elapsed_ms=(time.perf_counter() - started) * 1000,
                fallback_used=reason is not None,
                fallback_reason=reason,
                edges=edges,
                errors=tuple(errors),
            ),
        )
