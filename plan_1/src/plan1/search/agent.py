from __future__ import annotations

import gc
from dataclasses import replace
from typing import Any, Callable, Sequence

from plan1.config import Plan1Config
from plan1.engine.conformance import conformance_action, repeated_prediction_inputs
from plan1.evaluation.handcrafted import HandcraftedEvaluator
from plan1.game.actions import validate_action
from plan1.game.catalog import CardCatalog
from plan1.game.records import PublicObservationRecord
from plan1.search.mcts import SearchResult, UCTSearch


ObservationPolicy = Callable[[Any], Sequence[int]]
TraceSink = Callable[[SearchResult], None]
ActionObserver = Callable[[Any, Sequence[int]], None]


class Plan1MCTSAgent:
    """Live-game facade around UCT with strict legal fallback behavior."""

    def __init__(
        self,
        api: Any,
        deck: Sequence[int],
        config: Plan1Config,
        *,
        opponent_deck: Sequence[int] | None = None,
        fallback_policy: ObservationPolicy | None = None,
        rollout_policy: ObservationPolicy | None = None,
        trace_sink: TraceSink | None = None,
        action_observer: ActionObserver | None = None,
        horizon_turns: int | None = None,
        search_select_types: frozenset[int] = frozenset({0}),
    ) -> None:
        if len(deck) != 60:
            raise ValueError("Plan1MCTSAgent requires a 60-card deck")
        self.api = api
        self.deck = tuple(int(card_id) for card_id in deck)
        self.opponent_deck = tuple(int(card_id) for card_id in (opponent_deck or deck))
        self.config = config
        self.fallback_policy = fallback_policy or (lambda observation: conformance_action(observation, api))
        self.rollout_policy = rollout_policy or (lambda observation: conformance_action(observation, api))
        self.trace_sink = trace_sink
        self.action_observer = action_observer
        self.search_select_types = search_select_types
        catalog = CardCatalog.from_engine(api.all_card_data(), api.all_attack())
        search_config = config.search
        if horizon_turns is not None:
            search_config = replace(search_config, horizon_turns=horizon_turns)
        self.searcher = UCTSearch(
            api,
            HandcraftedEvaluator(catalog),
            search_config,
            cleanup_reserve_ms=config.safety.cleanup_reserve_ms,
            rollout_policy=self.rollout_policy,
        )

    def act(self, observation_dict: dict[str, Any]) -> list[int]:
        observation = self.api.to_observation_class(observation_dict)
        if observation.select is None:
            return list(self.deck)
        fallback = self._fallback(observation)
        if not observation.select.option:
            return self._return(observation, fallback)
        current = observation.current
        if (
            current is None
            or current.result != -1
            or not observation.search_begin_input
            or int(observation.select.type) not in self.search_select_types
        ):
            return self._return(observation, fallback)
        record = PublicObservationRecord.from_engine(observation)
        if record.selection is None:
            return self._return(observation, fallback)
        seed = self.config.reproducibility.seed ^ int(record.fingerprint[:16], 16)
        try:
            inputs = repeated_prediction_inputs(observation, self.deck, self.opponent_deck)
            gc_was_enabled = gc.isenabled()
            if gc_was_enabled:
                gc.disable()
            try:
                result = self.searcher.search(observation, inputs, seed=seed, fallback_action=fallback)
            finally:
                if gc_was_enabled:
                    gc.enable()
            validate_action(record.selection, result.action)
        except Exception:
            if not self.config.safety.fallback_on_error:
                raise
            return self._return(observation, fallback)
        if self.trace_sink is not None:
            self.trace_sink(result)
        return self._return(observation, result.action)

    def _return(self, observation: Any, action: Sequence[int]) -> list[int]:
        result = list(action)
        if self.action_observer is not None:
            self.action_observer(observation, result)
        return result

    def _fallback(self, observation: Any) -> list[int]:
        try:
            result = list(self.fallback_policy(observation))
        except Exception:
            selection = observation.select
            return list(range(min(int(selection.minCount), len(selection.option))))
        record = PublicObservationRecord.from_engine(observation)
        if record.selection is None:
            return result
        try:
            return list(validate_action(record.selection, result))
        except Exception:
            selection = observation.select
            return list(range(min(int(selection.minCount), len(selection.option))))
