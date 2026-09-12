from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from plan1.belief.information_set import information_set_key
from plan1.config import load_config
from plan1.data.generator import _load_game, _load_policy, deck_identity
from plan1.data.trajectory import ActionTarget, DecisionRecord, GameTrajectory, PolicyIdentity
from plan1.engine.api_loader import load_competition_api
from plan1.game.actions import ActionGenerator
from plan1.game.records import PublicObservationRecord
from plan1.model.inference import ModelInference
from plan1.model.policy_value import PolicyValueModel
from plan1.reproducibility import canonical_json_hash, derive_seed, sha256_file
from plan1.search.agent import Plan1MCTSAgent
from plan1.search.mcts import SearchResult


@dataclass(frozen=True, slots=True)
class SelfPlayJob:
    job_id: str
    run_id: str
    iteration: int
    game_index: int
    seed: int
    seed_group: str
    deck_names: tuple[str, str]
    decks: tuple[tuple[int, ...], tuple[int, ...]]
    checkpoints: tuple[str, str]
    search_config: str
    max_steps: int
    max_candidates: int
    temperature_turns: int
    visit_temperature: float


@dataclass(frozen=True, slots=True)
class SelfPlayResult:
    job_id: str
    trajectory: dict[str, Any] | None
    error: str | None
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class _Pending:
    decision_index: int
    player: int
    timestamp_utc: str
    observation: dict[str, Any]
    observation_sha256: str
    information_set_key: str
    selection_fingerprint: str
    legal_actions: tuple[ActionTarget, ...]
    chosen_action_fingerprint: str
    chosen_indices: tuple[int, ...]
    search: dict[str, Any]
    belief: dict[str, Any]


class _SelfPlayPolicy:
    def __init__(
        self,
        api: Any,
        deck: Sequence[int],
        opponent_deck: Sequence[int],
        checkpoint: Path,
        search_config: Path,
        module_name: str,
    ) -> None:
        self.model = PolicyValueModel.load(checkpoint)
        self.inference = ModelInference(self.model)
        self.module = _load_policy(module_name, deck)
        self.last_result: SearchResult | None = None

        def trace(result: SearchResult) -> None:
            self.last_result = result

        self.agent = Plan1MCTSAgent(
            api,
            deck,
            load_config(search_config),
            opponent_deck=opponent_deck,
            fallback_policy=self.module._greedy_select,
            rollout_policy=self.module._greedy_select,
            trace_sink=trace,
            policy_value=self.inference,
            puct_constant=1.0,
            learned_value_mix=0.10,
        )

    def act(self, observation_dict: dict[str, Any]) -> tuple[list[int], SearchResult | None, Any]:
        self.last_result = None
        observation = self.agent.api.to_observation_class(observation_dict)
        action = self.agent.act(observation_dict)
        return action, self.last_result, observation

    def record_action(self, observation: Any, action: Sequence[int]) -> None:
        self.module._record_if_ability(observation, action)


def _temperature_action(
    result: SearchResult | None,
    *,
    turn: int,
    temperature_turns: int,
    temperature: float,
    seed: int,
) -> tuple[int, ...] | None:
    if (
        result is None or result.trace.fallback_used or turn > temperature_turns
        or len(result.trace.root_edges) < 2
    ):
        return None
    edges = [edge for edge in result.trace.root_edges if edge.visits > 0]
    if len(edges) < 2:
        return None
    weights = [edge.visits ** (1.0 / temperature) for edge in edges]
    total = sum(weights)
    threshold = random.Random(seed).random() * total
    cumulative = 0.0
    for edge, weight in zip(edges, weights):
        cumulative += weight
        if threshold <= cumulative:
            return edge.action
    return edges[-1].action


def _capture(
    job: SelfPlayJob,
    actor: int,
    decision_index: int,
    observation: Any,
    action: Sequence[int],
    search_result: SearchResult | None,
    policy: _SelfPlayPolicy,
) -> _Pending:
    record = PublicObservationRecord.from_engine(observation)
    if record.selection is None:
        raise RuntimeError("self-play decision has no selection")
    generation = ActionGenerator(max_candidates=job.max_candidates).generate(
        record.selection,
        preferred_indices=action,
        seed=job.seed + decision_index,
    )
    priors = policy.inference.policy(record, generation.candidates, actor)
    edge_by_fingerprint = {}
    use_search_targets = bool(search_result is not None and not search_result.trace.fallback_used)
    if use_search_targets:
        edge_by_fingerprint = {
            edge.fingerprint: edge for edge in search_result.trace.root_edges
        }
    chosen_fingerprint = next(
        candidate.fingerprint for candidate in generation.candidates
        if candidate.indices == tuple(action)
    )
    targets = []
    for candidate, prior in zip(generation.candidates, priors):
        edge = edge_by_fingerprint.get(candidate.fingerprint)
        targets.append(
            ActionTarget(
                fingerprint=candidate.fingerprint,
                indices=candidate.indices,
                option_mask=candidate.option_mask,
                visits=(edge.visits if edge is not None else (1 if not use_search_targets and candidate.fingerprint == chosen_fingerprint else 0)),
                prior=prior,
                q_value=None if edge is None else max(-1.0, min(1.0, edge.mean_value)),
            )
        )
    payload = record.to_dict()
    trace = None if search_result is None else asdict(search_result.trace)
    return _Pending(
        decision_index=decision_index,
        player=actor,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        observation=payload,
        observation_sha256=canonical_json_hash(payload),
        information_set_key=information_set_key(record, actor),
        selection_fingerprint=record.selection.fingerprint,
        legal_actions=tuple(targets),
        chosen_action_fingerprint=chosen_fingerprint,
        chosen_indices=tuple(action),
        search={
            "kind": "policy_value_puct_selfplay" if use_search_targets else "policy_value_fallback_selfplay",
            "iteration": job.iteration,
            "temperature": job.visit_temperature if record.state and record.state.turn <= job.temperature_turns else 0.0,
            "trace": trace,
            "candidate_count": len(generation.candidates),
            "candidate_exhaustive": generation.exhaustive,
            "total_action_count": generation.total_action_count,
        },
        belief={"version": "phase8-public-no-oracle", "determinizations": 0, "hidden_policy_fields": False},
    )


def play_selfplay_job(job: SelfPlayJob) -> SelfPlayResult:
    import time

    started = time.perf_counter()
    game = None
    try:
        api = load_competition_api()
        game = _load_game()
        checkpoint_paths = (Path(job.checkpoints[0]), Path(job.checkpoints[1]))
        policies = (
            _SelfPlayPolicy(api, job.decks[0], job.decks[1], checkpoint_paths[0], Path(job.search_config), f"{job.job_id}_p0"),
            _SelfPlayPolicy(api, job.decks[1], job.decks[0], checkpoint_paths[1], Path(job.search_config), f"{job.job_id}_p1"),
        )
        deck_ids = (
            deck_identity(job.deck_names[0], job.decks[0]),
            deck_identity(job.deck_names[1], job.decks[1]),
        )
        policy_ids = tuple(
            PolicyIdentity(
                "plan1_policy_value_puct",
                path.stem,
                sha256_file(path),
            )
            for path in checkpoint_paths
        )
        observation_dict, start_data = game.battle_start(list(job.decks[0]), list(job.decks[1]))
        if observation_dict is None:
            raise RuntimeError(f"battle_start failed: {start_data}")
        pending: list[_Pending] = []
        for decision_index in range(job.max_steps):
            observation = api.to_observation_class(observation_dict)
            state = observation.current
            if state is not None and state.result != -1:
                result = int(state.result)
                break
            if observation.select is None:
                action = list(job.decks[0])
            else:
                actor = int(state.yourIndex) if state is not None else 0
                action, search_result, typed_observation = policies[actor].act(observation_dict)
                exploratory = _temperature_action(
                    search_result,
                    turn=state.turn if state is not None else 0,
                    temperature_turns=job.temperature_turns,
                    temperature=job.visit_temperature,
                    seed=derive_seed(job.seed, decision_index, actor),
                )
                if exploratory is not None:
                    action = list(exploratory)
                policies[actor].record_action(typed_observation, action)
                pending.append(
                    _capture(job, actor, decision_index, typed_observation, action, search_result, policies[actor])
                )
            observation_dict = game.battle_select(action)
        else:
            raise RuntimeError(f"game exceeded {job.max_steps} decisions")
        if not pending:
            raise RuntimeError("self-play game contained no decisions")
        decisions = tuple(
            DecisionRecord(
                schema_version=1,
                game_id=job.job_id,
                decision_index=index,
                player=item.player,
                seat=item.player,
                seed=job.seed,
                seed_group=job.seed_group,
                timestamp_utc=item.timestamp_utc,
                observation=item.observation,
                observation_sha256=item.observation_sha256,
                information_set_key=item.information_set_key,
                selection_fingerprint=item.selection_fingerprint,
                legal_actions=item.legal_actions,
                chosen_action_fingerprint=item.chosen_action_fingerprint,
                chosen_indices=item.chosen_indices,
                search=item.search,
                belief=item.belief,
                acting_policy=policy_ids[item.player],
                opponent_policy=policy_ids[1 - item.player],
                deck_sha256=deck_ids[item.player].sha256,
                opponent_deck_sha256=deck_ids[1 - item.player].sha256,
                final_result=result,
                value_target=0.0 if result == 2 else (1.0 if result == item.player else -1.0),
                terminal_reason="engine_terminal",
            )
            for index, item in enumerate(pending)
        )
        trajectory = GameTrajectory(
            schema_version=1,
            game_id=job.job_id,
            run_id=job.run_id,
            purpose="training",
            seed=job.seed,
            seed_group=job.seed_group,
            created_utc=datetime.now(timezone.utc).isoformat(),
            decks=deck_ids,
            policies=policy_ids,
            decisions=decisions,
            final_result=result,
            terminal_reason="engine_terminal",
            completed=True,
        )
        trajectory.validate()
        return SelfPlayResult(job.job_id, trajectory.to_dict(), None, time.perf_counter() - started)
    except Exception as exc:
        return SelfPlayResult(job.job_id, None, f"{type(exc).__name__}:{exc}", time.perf_counter() - started)
    finally:
        if game is not None:
            try:
                game.battle_finish()
            except Exception:
                pass
