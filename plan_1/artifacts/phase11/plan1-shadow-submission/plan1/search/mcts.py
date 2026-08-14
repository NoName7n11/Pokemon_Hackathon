from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Sequence

from plan1.config import SearchConfig
from plan1.engine.conformance import conformance_action
from plan1.engine.lifecycle import SearchInputs, SearchSession
from plan1.evaluation.handcrafted import TERMINAL_SCORE, HandcraftedEvaluator
from plan1.game.actions import ActionCandidate, ActionGenerator, GenerationResult
from plan1.game.records import PublicObservationRecord
from plan1.reproducibility import canonical_json_hash


MCTS_VERSION = "uct-v1"
Clock = Callable[[], int]
RolloutPolicy = Callable[[Any], Sequence[int]]


class PolicyValueInference(Protocol):
    def policy(
        self,
        record: PublicObservationRecord,
        candidates: Sequence[ActionCandidate],
        perspective: int,
    ) -> tuple[float, ...]: ...

    def value(self, record: PublicObservationRecord, perspective: int) -> float: ...


def search_fingerprint(record: PublicObservationRecord) -> str:
    """Fingerprint rule-relevant public state while ignoring action-count churn."""
    payload = record.to_dict()
    payload["logs"] = []
    state = payload.get("state")
    if state is not None:
        state["turn_action_count"] = 0
    return canonical_json_hash(payload)


@dataclass(frozen=True, slots=True)
class EdgeTrace:
    action: tuple[int, ...]
    fingerprint: str
    visits: int
    value_sum: float
    mean_value: float
    immediate_reward: float
    terminal: bool
    expansion_failures: int
    sampled_determinizations: int
    prior: float


@dataclass(frozen=True, slots=True)
class SearchTrace:
    version: str
    seed: int
    root_player: int | None
    root_turn: int | None
    horizon_turns: int
    simulations: int
    completed_simulations: int
    tree_nodes: int
    native_steps: int
    max_depth_reached: int
    loop_cutoffs: int
    horizon_cutoffs: int
    depth_cutoffs: int
    time_cutoffs: int
    hard_deadline_exceeded: bool
    expansion_failures: int
    elapsed_ms: float
    stopped_reason: str
    fallback_used: bool
    fallback_reason: str | None
    generation_exhaustive: bool
    total_root_actions: int
    generated_root_actions: int
    root_edges: tuple[EdgeTrace, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SearchResult:
    action: tuple[int, ...]
    fallback_action: tuple[int, ...]
    trace: SearchTrace


class TimeManager:
    def __init__(self, budget_ms: int, cleanup_reserve_ms: int, *, clock: Clock = time.perf_counter_ns):
        if budget_ms <= 0 or cleanup_reserve_ms <= 0 or cleanup_reserve_ms >= budget_ms:
            raise ValueError("time budget must exceed a positive cleanup reserve")
        self._clock = clock
        self.started_ns = clock()
        self.search_deadline_ns = self.started_ns + (budget_ms - cleanup_reserve_ms) * 1_000_000
        self.hard_deadline_ns = self.started_ns + budget_ms * 1_000_000

    def search_expired(self) -> bool:
        return self._clock() >= self.search_deadline_ns

    def hard_expired(self) -> bool:
        return self._clock() >= self.hard_deadline_ns

    def elapsed_ms(self) -> float:
        return (self._clock() - self.started_ns) / 1_000_000


@dataclass(slots=True)
class _Edge:
    action: ActionCandidate
    child: "_Node"
    visits: int = 0
    value_sum: float = 0.0
    immediate_reward: float = 0.0
    terminal: bool = False
    expansion_failures: int = 0
    sampled_determinizations: int = 1
    prior: float = 0.0

    @property
    def mean_value(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0


@dataclass(slots=True)
class _Node:
    state: Any
    record: PublicObservationRecord
    fingerprint: str
    depth: int
    actor: int | None
    visits: int = 0
    value_sum: float = 0.0
    generation: GenerationResult | None = None
    priors: tuple[float, ...] = ()
    children: list[_Edge] = field(default_factory=list)
    next_unexpanded: int = 0


@dataclass(slots=True)
class _Counters:
    simulations: int = 0
    completed_simulations: int = 0
    tree_nodes: int = 1
    native_steps: int = 0
    max_depth: int = 0
    loops: int = 0
    horizons: int = 0
    depths: int = 0
    time_cutoffs: int = 0
    expansion_failures: int = 0


class UCTSearch:
    """Deterministic UCT over the native simulator's public search states."""

    def __init__(
        self,
        backend: Any,
        evaluator: HandcraftedEvaluator,
        config: SearchConfig,
        *,
        cleanup_reserve_ms: int,
        action_generator: ActionGenerator | None = None,
        rollout_policy: RolloutPolicy | None = None,
        policy_value: PolicyValueInference | None = None,
        puct_constant: float = 1.25,
        learned_value_mix: float = 0.25,
        clock: Clock = time.perf_counter_ns,
    ) -> None:
        if cleanup_reserve_ms >= config.time_budget_ms:
            raise ValueError("cleanup reserve must be smaller than the search budget")
        self.backend = backend
        self.evaluator = evaluator
        self.config = config
        self.cleanup_reserve_ms = cleanup_reserve_ms
        self.generator = action_generator or ActionGenerator(max_candidates=config.max_candidates)
        self.rollout_policy = rollout_policy or (lambda observation: conformance_action(observation, backend))
        if puct_constant <= 0 or not 0.0 <= learned_value_mix <= 1.0:
            raise ValueError("PUCT constant must be positive and learned value mix must be in [0, 1]")
        self.policy_value = policy_value
        self.puct_constant = puct_constant
        self.learned_value_mix = learned_value_mix
        self.clock = clock

    def search(
        self,
        observation: Any,
        inputs: SearchInputs,
        *,
        seed: int,
        fallback_action: Sequence[int] | None = None,
    ) -> SearchResult:
        timer = TimeManager(self.config.time_budget_ms, self.cleanup_reserve_ms, clock=self.clock)
        fallback = tuple(fallback_action) if fallback_action is not None else self._fallback(observation)
        record = PublicObservationRecord.from_engine(observation)
        state = record.state
        selection = record.selection
        root_player = state.acting_player if state is not None else None
        root_turn = state.turn if state is not None else None
        errors: list[str] = []
        if state is None or selection is None:
            return self._fallback_result(
                fallback, timer, seed, root_player, root_turn, "unsearchable_observation", errors
            )

        try:
            root_generation = self.generator.generate(selection, preferred_indices=fallback, seed=seed)
            root_generation, root_priors = self._rank_generation(record, root_generation, root_player)
        except Exception as exc:
            errors.append(f"root_generation:{type(exc).__name__}:{exc}")
            return self._fallback_result(fallback, timer, seed, root_player, root_turn, "generation_error", errors)
        if len(root_generation.candidates) == 1:
            return self._fallback_result(
                root_generation.candidates[0].indices,
                timer,
                seed,
                root_player,
                root_turn,
                "forced_action",
                errors,
                generation=root_generation,
                fallback_used=False,
            )
        if timer.search_expired():
            return self._fallback_result(
                fallback,
                timer,
                seed,
                root_player,
                root_turn,
                "budget_before_begin",
                errors,
                generation=root_generation,
            )

        counters = _Counters()
        root: _Node | None = None
        stopped_reason = "simulation_limit"
        try:
            with SearchSession(self.backend, observation, inputs) as session:
                root = _Node(
                    state=session.root,
                    record=record,
                    fingerprint=search_fingerprint(record),
                    depth=0,
                    actor=root_player,
                    generation=root_generation,
                    priors=root_priors,
                )
                while counters.simulations < self.config.max_simulations:
                    if timer.search_expired():
                        stopped_reason = "time_limit"
                        break
                    if counters.native_steps >= self.config.max_nodes:
                        stopped_reason = "node_limit"
                        break
                    counters.simulations += 1
                    value, nodes, edges = self._simulate(
                        session,
                        root,
                        root_player,
                        root_turn,
                        seed + counters.simulations,
                        timer,
                        counters,
                    )
                    self._backup(nodes, edges, value)
                    counters.completed_simulations += 1
                else:
                    stopped_reason = "simulation_limit"
        except Exception as exc:
            errors.append(f"search:{type(exc).__name__}:{exc}")
            return self._fallback_result(
                fallback,
                timer,
                seed,
                root_player,
                root_turn,
                "search_error",
                errors,
                generation=root_generation,
                counters=counters,
                root=root,
            )

        if root is None or not root.children or counters.completed_simulations == 0:
            return self._fallback_result(
                fallback,
                timer,
                seed,
                root_player,
                root_turn,
                "no_completed_simulation",
                errors,
                generation=root_generation,
                counters=counters,
                root=root,
            )
        if self.config.require_full_root_coverage and (
            not root_generation.exhaustive or len(root.children) < len(root_generation.candidates)
        ):
            return self._fallback_result(
                fallback,
                timer,
                seed,
                root_player,
                root_turn,
                "incomplete_root_coverage",
                errors,
                generation=root_generation,
                counters=counters,
                root=root,
            )
        chosen = min(
            root.children,
            key=lambda edge: (-edge.visits, -edge.mean_value, edge.action.fingerprint),
        )
        return SearchResult(
            action=chosen.action.indices,
            fallback_action=fallback,
            trace=self._trace(
                timer,
                seed,
                root_player,
                root_turn,
                stopped_reason,
                False,
                None,
                errors,
                root_generation,
                counters,
                root,
            ),
        )

    def _simulate(
        self,
        session: SearchSession,
        root: _Node,
        root_player: int,
        root_turn: int,
        seed: int,
        timer: TimeManager,
        counters: _Counters,
    ) -> tuple[float, list[_Node], list[_Edge]]:
        node = root
        nodes = [root]
        edges: list[_Edge] = []
        path_fingerprints = {root.fingerprint}
        while True:
            counters.max_depth = max(counters.max_depth, node.depth)
            cutoff = self._cutoff(node, root_turn, timer, counters)
            if cutoff:
                return self._value(node.record, root_player), nodes, edges
            generation = self._generation(node, seed)
            if generation is None:
                counters.expansion_failures += 1
                return self._value(node.record, root_player), nodes, edges
            widening_limit = min(
                len(generation.candidates),
                max(
                    1,
                    int(
                        self.config.progressive_widening_base
                        * ((node.visits + 1) ** self.config.progressive_widening_exponent)
                    ),
                ),
            )
            if node.next_unexpanded < widening_limit and counters.native_steps < self.config.max_nodes:
                candidate = generation.candidates[node.next_unexpanded]
                node.next_unexpanded += 1
                try:
                    child_state = session.step(node.state, candidate.indices)
                    counters.native_steps += 1
                    child_record = PublicObservationRecord.from_engine(child_state.observation)
                    child = _Node(
                        state=child_state,
                        record=child_record,
                        fingerprint=search_fingerprint(child_record),
                        depth=node.depth + 1,
                        actor=child_record.state.acting_player if child_record.state is not None else None,
                    )
                    edge = _Edge(
                        action=candidate,
                        child=child,
                        immediate_reward=self._value(child_record, root_player) - self._value(node.record, root_player),
                        terminal=bool(child_record.state is not None and child_record.state.result != -1),
                        prior=node.priors[node.next_unexpanded - 1] if node.priors else 0.0,
                    )
                    node.children.append(edge)
                    counters.tree_nodes += 1
                except Exception:
                    counters.expansion_failures += 1
                    continue
                nodes.append(child)
                edges.append(edge)
                if child.fingerprint in path_fingerprints:
                    counters.loops += 1
                    return self._value(child.record, root_player), nodes, edges
                path_fingerprints.add(child.fingerprint)
                return self._rollout(
                    session, child, root_player, root_turn, path_fingerprints, timer, counters
                ), nodes, edges
            if not node.children:
                return self._value(node.record, root_player), nodes, edges
            edge = self._select_edge(node, root_player)
            node = edge.child
            nodes.append(node)
            edges.append(edge)
            if node.fingerprint in path_fingerprints:
                counters.loops += 1
                return self._value(node.record, root_player), nodes, edges
            path_fingerprints.add(node.fingerprint)

    def _rollout(
        self,
        session: SearchSession,
        leaf: _Node,
        root_player: int,
        root_turn: int,
        path_fingerprints: set[str],
        timer: TimeManager,
        counters: _Counters,
    ) -> float:
        current = leaf.state
        record = leaf.record
        ephemeral = False
        depth = leaf.depth
        try:
            while True:
                counters.max_depth = max(counters.max_depth, depth)
                if self._record_terminal(record):
                    return self._value(record, root_player)
                if record.state is not None and record.state.turn > root_turn + self.config.horizon_turns:
                    counters.horizons += 1
                    return self._value(record, root_player)
                if depth >= self.config.max_depth:
                    counters.depths += 1
                    return self._value(record, root_player)
                if timer.search_expired() or counters.native_steps >= self.config.max_nodes:
                    counters.time_cutoffs += int(timer.search_expired())
                    return self._value(record, root_player)
                action = tuple(self.rollout_policy(current.observation))
                next_state = session.step(current, action)
                counters.native_steps += 1
                if ephemeral:
                    session.release(current)
                current = next_state
                ephemeral = True
                depth += 1
                record = PublicObservationRecord.from_engine(current.observation)
                fingerprint = search_fingerprint(record)
                if fingerprint in path_fingerprints:
                    counters.loops += 1
                    return self._value(record, root_player)
                path_fingerprints.add(fingerprint)
        finally:
            if ephemeral:
                session.release(current)

    def _generation(self, node: _Node, seed: int) -> GenerationResult | None:
        if node.generation is not None:
            return node.generation
        if node.record.selection is None:
            return None
        try:
            preferred = self.rollout_policy(node.state.observation)
            node.generation = self.generator.generate(
                node.record.selection,
                preferred_indices=preferred,
                seed=seed ^ int(node.fingerprint[:16], 16),
            )
            perspective = node.actor if node.actor in (0, 1) else 0
            node.generation, node.priors = self._rank_generation(
                node.record, node.generation, perspective
            )
        except Exception:
            return None
        return node.generation

    def _rank_generation(
        self,
        record: PublicObservationRecord,
        generation: GenerationResult,
        perspective: int,
    ) -> tuple[GenerationResult, tuple[float, ...]]:
        count = len(generation.candidates)
        if self.policy_value is None:
            return generation, tuple(1.0 / count for _ in generation.candidates)
        try:
            priors = self.policy_value.policy(record, generation.candidates, perspective)
            if len(priors) != count or any(not math.isfinite(value) or value < 0 for value in priors):
                raise ValueError("invalid policy prior vector")
            total = sum(priors)
            if total <= 0:
                raise ValueError("policy prior vector has zero mass")
            normalized = tuple(value / total for value in priors)
        except Exception:
            normalized = tuple(1.0 / count for _ in generation.candidates)
        ranked = sorted(
            zip(generation.candidates, normalized),
            key=lambda item: (-item[1], item[0].fingerprint),
        )
        return (
            GenerationResult(
                candidates=tuple(item[0] for item in ranked),
                ordered=generation.ordered,
                exhaustive=generation.exhaustive,
                total_action_count=generation.total_action_count,
                issues=generation.issues,
            ),
            tuple(item[1] for item in ranked),
        )

    def _select_edge(self, node: _Node, root_player: int) -> _Edge:
        maximizing = node.actor == root_player

        def score(edge: _Edge) -> tuple[float, str]:
            exploit = edge.mean_value if maximizing else -edge.mean_value
            if self.policy_value is None:
                log_parent = math.log(max(2, node.visits + 1))
                explore = self.config.exploration_constant * math.sqrt(
                    log_parent / max(1, edge.visits)
                )
            else:
                explore = (
                    self.puct_constant
                    * edge.prior
                    * math.sqrt(max(1, node.visits))
                    / (1 + edge.visits)
                )
            return exploit + explore, edge.action.fingerprint

        return min(node.children, key=lambda edge: (-score(edge)[0], score(edge)[1]))

    def _cutoff(self, node: _Node, root_turn: int, timer: TimeManager, counters: _Counters) -> bool:
        if self._record_terminal(node.record):
            return True
        state = node.record.state
        if state is not None and state.turn > root_turn + self.config.horizon_turns:
            counters.horizons += 1
            return True
        if node.depth >= self.config.max_depth:
            counters.depths += 1
            return True
        if timer.search_expired():
            counters.time_cutoffs += 1
            return True
        return False

    def _value(self, record: PublicObservationRecord, root_player: int) -> float:
        score = self.evaluator.score(record, root_player)
        if abs(score) >= TERMINAL_SCORE:
            return 1.0 if score > 0 else -1.0
        heuristic = math.tanh(score / self.config.value_scale)
        if self.policy_value is None or self.learned_value_mix == 0.0:
            return heuristic
        try:
            learned = max(-1.0, min(1.0, float(self.policy_value.value(record, root_player))))
        except Exception:
            return heuristic
        return (1.0 - self.learned_value_mix) * heuristic + self.learned_value_mix * learned

    @staticmethod
    def _record_terminal(record: PublicObservationRecord) -> bool:
        return bool(record.state is not None and record.state.result != -1)

    def _backup(self, nodes: list[_Node], edges: list[_Edge], leaf_value: float) -> None:
        value = leaf_value
        for node in reversed(nodes):
            node.visits += 1
            node.value_sum += value
            value *= self.config.discount_factor
        value = leaf_value
        for edge in reversed(edges):
            edge.visits += 1
            edge.value_sum += value
            value *= self.config.discount_factor

    def _fallback(self, observation: Any) -> tuple[int, ...]:
        try:
            return tuple(self.rollout_policy(observation))
        except Exception:
            select = getattr(observation, "select", None)
            if select is None:
                return ()
            return tuple(range(min(int(select.minCount), len(select.option))))

    def _fallback_result(
        self,
        action: Sequence[int],
        timer: TimeManager,
        seed: int,
        root_player: int | None,
        root_turn: int | None,
        reason: str,
        errors: list[str],
        *,
        generation: GenerationResult | None = None,
        counters: _Counters | None = None,
        root: _Node | None = None,
        fallback_used: bool = True,
    ) -> SearchResult:
        counters = counters or _Counters(tree_nodes=0)
        return SearchResult(
            action=tuple(action),
            fallback_action=tuple(action),
            trace=self._trace(
                timer,
                seed,
                root_player,
                root_turn,
                reason,
                fallback_used,
                reason if fallback_used else None,
                errors,
                generation,
                counters,
                root,
            ),
        )

    def _trace(
        self,
        timer: TimeManager,
        seed: int,
        root_player: int | None,
        root_turn: int | None,
        stopped_reason: str,
        fallback_used: bool,
        fallback_reason: str | None,
        errors: list[str],
        generation: GenerationResult | None,
        counters: _Counters,
        root: _Node | None,
    ) -> SearchTrace:
        edge_traces = tuple(
            EdgeTrace(
                action=edge.action.indices,
                fingerprint=edge.action.fingerprint,
                visits=edge.visits,
                value_sum=edge.value_sum,
                mean_value=edge.mean_value,
                immediate_reward=edge.immediate_reward,
                terminal=edge.terminal,
                expansion_failures=edge.expansion_failures,
                sampled_determinizations=edge.sampled_determinizations,
                prior=edge.prior,
            )
            for edge in (root.children if root is not None else ())
        )
        return SearchTrace(
            version="puct-v1" if self.policy_value is not None else MCTS_VERSION,
            seed=seed,
            root_player=root_player,
            root_turn=root_turn,
            horizon_turns=self.config.horizon_turns,
            simulations=counters.simulations,
            completed_simulations=counters.completed_simulations,
            tree_nodes=counters.tree_nodes,
            native_steps=counters.native_steps,
            max_depth_reached=counters.max_depth,
            loop_cutoffs=counters.loops,
            horizon_cutoffs=counters.horizons,
            depth_cutoffs=counters.depths,
            time_cutoffs=counters.time_cutoffs,
            hard_deadline_exceeded=timer.hard_expired(),
            expansion_failures=counters.expansion_failures,
            elapsed_ms=timer.elapsed_ms(),
            stopped_reason=stopped_reason,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            generation_exhaustive=generation.exhaustive if generation is not None else False,
            total_root_actions=generation.total_action_count if generation is not None else 0,
            generated_root_actions=len(generation.candidates) if generation is not None else 0,
            root_edges=edge_traces,
            errors=tuple(errors),
        )
