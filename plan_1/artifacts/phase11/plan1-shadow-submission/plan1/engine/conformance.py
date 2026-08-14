from __future__ import annotations

import importlib
import ctypes
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass, fields, is_dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Sequence

from plan1.engine.api_loader import load_competition_api
from plan1.engine.lifecycle import SearchInputs, SearchSession
from plan1.paths import ENGINE_PARENT
from plan1.reproducibility import canonical_json_hash


DEFAULT_MEMORY_TAIL_LIMIT_BYTES = 8 * 1024 * 1024


@dataclass
class ConformanceResult:
    branch_parent_reusable: bool
    child_survives_parent_release: bool | None
    sibling_survives_leaf_release: bool
    descendant_survives_ancestor_release: bool | None
    released_state_rejected: bool
    double_release_idempotent: bool
    crossed_turn_boundary: bool
    max_path_steps: int
    replay_exact: bool
    replay_terminal: bool
    replay_second_terminal: bool
    replay_steps: int
    replay_mismatch_step: int | None
    replay_stochastic_boundary_step: int | None
    replay_stochastic_boundary_reason: str | None
    replay_coin_events: int
    session_iterations: int
    root_ids_reused_across_sessions: bool
    begin_ms_median: float
    step_ms_median: float
    rss_before_bytes: int | None
    rss_after_bytes: int | None
    rss_delta_bytes: int | None
    rss_peak_bytes: int | None
    rss_tail_growth_bytes: int | None
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def conformance_passes(
    result: ConformanceResult,
    *,
    memory_tail_limit_bytes: int = DEFAULT_MEMORY_TAIL_LIMIT_BYTES,
) -> bool:
    tail = result.rss_tail_growth_bytes
    memory_ok = tail is None or tail <= memory_tail_limit_bytes
    return all(
        (
            result.branch_parent_reusable,
            result.child_survives_parent_release,
            result.sibling_survives_leaf_release,
            result.descendant_survives_ancestor_release,
            result.released_state_rejected,
            result.double_release_idempotent,
            result.crossed_turn_boundary,
            result.replay_exact,
            result.replay_terminal,
            result.replay_second_terminal,
            not result.errors,
            memory_ok,
        )
    )


def read_deck(path: Path) -> list[int]:
    values = [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(values) != 60 or not all(value.isdecimal() for value in values):
        raise ValueError(f"deck must contain exactly 60 integer card IDs: {path}")
    return [int(value) for value in values]


def legal_probe_selection(select: Any, preferred_index: int = 0) -> list[int]:
    option_count = len(select.option)
    if select.minCount == 0:
        return [preferred_index] if option_count and select.maxCount > 0 else []
    if option_count < select.minCount:
        raise ValueError("engine selection exposes fewer options than minCount")
    chosen = list(range(select.minCount))
    if preferred_index < option_count and chosen:
        chosen[0] = preferred_index
        chosen = list(dict.fromkeys(chosen))
        for index in range(option_count):
            if len(chosen) >= select.minCount:
                break
            if index not in chosen:
                chosen.append(index)
    return chosen


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, float, bool)):
        return value
    if isinstance(value, IntEnum):
        return int(value)
    if isinstance(value, int):
        return value
    if is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    raise TypeError(f"unsupported fingerprint value: {type(value).__name__}")


def observation_fingerprint(observation: Any) -> str:
    """Hash public/search-visible state while excluding incremental logs."""
    return canonical_json_hash(
        {
            "current": _jsonable(observation.current),
            "select": _jsonable(observation.select),
        }
    )


def conformance_action(observation: Any, api: Any) -> list[int]:
    """Choose a deterministic legal-looking action that avoids ability loops.

    MAIN choices develop the board, attack when possible, then end the turn.
    The engine remains the final legality authority. Phase 2 will replace this
    probe helper with exhaustive canonical action generation.
    """
    select = observation.select
    if select is None:
        raise ValueError("cannot choose an action without selection data")
    if select.type == api.SelectType.MAIN:
        priorities = (
            api.OptionType.ATTACH,
            api.OptionType.EVOLVE,
            api.OptionType.PLAY,
            api.OptionType.ATTACK,
            api.OptionType.END,
            api.OptionType.RETREAT,
            api.OptionType.DISCARD,
            api.OptionType.ABILITY,
        )
        for option_type in priorities:
            for index, option in enumerate(select.option):
                if option.type == option_type:
                    return legal_probe_selection(select, index)
    return legal_probe_selection(select, 0)


@dataclass
class ReplayProbe:
    exact: bool
    terminal: bool
    second_terminal: bool
    steps: int
    mismatch_step: int | None
    stochastic_boundary_step: int | None
    stochastic_boundary_reason: str | None
    coin_events: int


def _coin_event_count(observation: Any, api: Any) -> int:
    return sum(1 for log in observation.logs if log.type == api.LogType.COIN)


def stochastic_boundary_reason(observation: Any, api: Any) -> str | None:
    select = observation.select
    if select is not None and select.deck is not None:
        return "randomized_deck_selection"
    stochastic_logs = {
        api.LogType.SHUFFLE: "shuffle",
        api.LogType.DRAW: "hidden_draw",
        api.LogType.DRAW_REVERSE: "opponent_hidden_draw",
        api.LogType.COIN: "coin",
    }
    for log in observation.logs:
        if log.type in stochastic_logs:
            return stochastic_logs[log.type]
    return None


def probe_path_replay(
    api: Any,
    observation: Any,
    inputs: SearchInputs,
    *,
    max_steps: int,
) -> ReplayProbe:
    actions: list[list[int]] = []
    fingerprints: list[str] = []
    coin_events = 0
    terminal = False
    boundary_step: int | None = None
    boundary_reason: str | None = None

    with SearchSession(api, observation, inputs) as session:
        state = session.root
        fingerprints.append(observation_fingerprint(state.observation))
        for _ in range(max_steps):
            current = state.observation.current
            if current is None or current.result != -1 or state.observation.select is None:
                terminal = current is not None and current.result != -1
                break
            action = conformance_action(state.observation, api)
            state = session.step(state, action)
            actions.append(action)
            fingerprints.append(observation_fingerprint(state.observation))
            coin_events += _coin_event_count(state.observation, api)
            reason = stochastic_boundary_reason(state.observation, api)
            if reason is not None and boundary_step is None:
                boundary_step = len(actions)
                boundary_reason = reason
        else:
            current = state.observation.current
            terminal = current is not None and current.result != -1

    mismatch: int | None = None
    second_terminal = False
    with SearchSession(api, observation, inputs) as session:
        state = session.root
        if observation_fingerprint(state.observation) != fingerprints[0]:
            mismatch = 0
        else:
            for step, action in enumerate(actions, 1):
                state = session.step(state, action)
                # The API exposes no RNG seed control. Once a shuffle, hidden
                # draw, coin, or randomized deck selection occurs, a fresh
                # search session is allowed to diverge. Exact replay is still
                # required for every state before that boundary.
                if boundary_step is not None and step >= boundary_step:
                    break
                if observation_fingerprint(state.observation) != fingerprints[step]:
                    mismatch = step
                    break
            if mismatch is None:
                for _ in range(max_steps):
                    current = state.observation.current
                    if current is None or current.result != -1 or state.observation.select is None:
                        second_terminal = current is not None and current.result != -1
                        break
                    state = session.step(state, conformance_action(state.observation, api))
                else:
                    current = state.observation.current
                    second_terminal = current is not None and current.result != -1

    return ReplayProbe(
        exact=mismatch is None,
        terminal=terminal,
        second_terminal=second_terminal,
        steps=len(actions),
        mismatch_step=mismatch,
        stochastic_boundary_step=boundary_step,
        stochastic_boundary_reason=boundary_reason,
        coin_events=coin_events,
    )


@dataclass
class ReleaseProbe:
    parent_reusable: bool
    child_survives_parent_release: bool | None
    sibling_survives_leaf_release: bool
    descendant_survives_ancestor_release: bool | None
    released_state_rejected: bool
    double_release_idempotent: bool


def probe_release_topology(api: Any, observation: Any, inputs: SearchInputs) -> ReleaseProbe:
    parent_reusable = False
    child_survives_parent = None
    sibling_survives_leaf = False
    descendant_survives_ancestor = None
    released_rejected = False
    double_release = False

    with SearchSession(api, observation, inputs) as session:
        root = session.root
        select = root.observation.select
        if select is None or len(select.option) < 2:
            raise RuntimeError("release probe requires at least two root options")
        first = session.step(root, legal_probe_selection(select, 0))
        second = session.step(root, legal_probe_selection(select, 1))
        parent_reusable = first.searchId != second.searchId

        session.release(first)
        session.release(first)
        double_release = True
        try:
            session.step(first, conformance_action(first.observation, api))
        except Exception:
            released_rejected = True

        second_select = second.observation.select
        if second_select is not None and second.observation.current.result == -1:
            try:
                session.step(second, conformance_action(second.observation, api))
                sibling_survives_leaf = True
            except Exception:
                sibling_survives_leaf = False

    with SearchSession(api, observation, inputs) as session:
        root = session.root
        child = session.step(root, conformance_action(root.observation, api))
        child_select = child.observation.select
        if child_select is not None and child.observation.current.result == -1:
            grandchild = session.step(child, conformance_action(child.observation, api))
            session.release(root)
            try:
                session.step(child, conformance_action(child.observation, api))
                child_survives_parent = True
            except Exception:
                child_survives_parent = False
            session.release(child)
            grandchild_select = grandchild.observation.select
            if grandchild_select is not None and grandchild.observation.current.result == -1:
                try:
                    session.step(grandchild, conformance_action(grandchild.observation, api))
                    descendant_survives_ancestor = True
                except Exception:
                    descendant_survives_ancestor = False

    return ReleaseProbe(
        parent_reusable=parent_reusable,
        child_survives_parent_release=child_survives_parent,
        sibling_survives_leaf_release=sibling_survives_leaf,
        descendant_survives_ancestor_release=descendant_survives_ancestor,
        released_state_rejected=released_rejected,
        double_release_idempotent=double_release,
    )


def repeated_prediction_inputs(observation: Any, my_deck: Sequence[int], opponent_deck: Sequence[int]) -> SearchInputs:
    state = observation.current
    if state is None:
        raise ValueError("searchable observation must contain current state")
    your_index = state.yourIndex
    me, opponent = state.players[your_index], state.players[1 - your_index]

    def take(pool: Sequence[int], count: int) -> list[int]:
        if count <= 0:
            return []
        if not pool:
            raise ValueError("prediction pool cannot be empty")
        return [pool[index % len(pool)] for index in range(count)]

    opponent_active: list[int] = []
    if opponent.active and opponent.active[0] is None:
        # A searchable post-setup observation is preferred. If this branch is
        # reached, select the first known Basic from the supplied deck upstream.
        opponent_active = [opponent_deck[0]]
    return SearchInputs.from_sequences(
        your_deck=take(my_deck, me.deckCount),
        your_prize=take(my_deck, len(me.prize)),
        opponent_deck=take(opponent_deck, opponent.deckCount),
        opponent_prize=take(opponent_deck, len(opponent.prize)),
        opponent_hand=take(opponent_deck, opponent.handCount),
        opponent_active=opponent_active,
    )


def _load_game_module() -> Any:
    load_competition_api()
    return importlib.import_module("cg.game")


def _load_baseline_agent() -> Any:
    engine_text = str(ENGINE_PARENT.resolve())
    if engine_text not in sys.path:
        sys.path.insert(0, engine_text)
    return importlib.import_module("main").agent


def find_searchable_observation(deck: Sequence[int], max_steps: int = 300) -> tuple[Any, Any, Any]:
    api = load_competition_api()
    game = _load_game_module()
    agent = _load_baseline_agent()
    observation_dict, start = game.battle_start(list(deck), list(deck))
    if observation_dict is None:
        raise RuntimeError(f"battle_start failed: {start}")
    try:
        for _ in range(max_steps):
            observation = api.to_observation_class(observation_dict)
            state, select = observation.current, observation.select
            if state is not None and state.result != -1:
                break
            if (
                observation.search_begin_input
                and state is not None
                and select is not None
                and state.turn > 0
                and all(not player.active or player.active[0] is not None for player in state.players)
                and len(select.option) >= 2
            ):
                return observation, game, api
            observation_dict = game.battle_select(agent(observation_dict))
    except BaseException:
        game.battle_finish()
        raise
    game.battle_finish()
    raise RuntimeError("could not reach a searchable observation with at least two options")


def process_rss_bytes() -> int | None:
    """Return current process working set where a standard OS API is available."""
    if os.name != "nt":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    process = kernel32.GetCurrentProcess()
    ok = psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb)
    return int(counters.WorkingSetSize) if ok else None


def run_conformance(deck: Sequence[int], *, session_iterations: int = 10, max_path_steps: int = 600) -> ConformanceResult:
    observation, game, api = find_searchable_observation(deck)
    inputs = repeated_prediction_inputs(observation, deck, deck)
    begin_times: list[float] = []
    step_times: list[float] = []
    root_ids: list[int] = []
    errors: list[str] = []
    crossed_turn = False
    path_steps = 0
    rss_samples: list[int] = []

    try:
        release = probe_release_topology(api, observation, inputs)
        replay = probe_path_replay(api, observation, inputs, max_steps=max_path_steps)

        # Probe a path across a turn boundary.
        start_turn = observation.current.turn
        with SearchSession(api, observation, inputs) as session:
            state = session.root
            for path_steps in range(1, max_path_steps + 1):
                current = state.observation.current
                select = state.observation.select
                if current is None or current.result != -1 or select is None:
                    break
                state = session.step(state, conformance_action(state.observation, api))
                if state.observation.current is not None and state.observation.current.turn != start_turn:
                    crossed_turn = True
                    break

        # Sample working set throughout the soak so warmup can be separated from
        # sustained tail growth.
        rss_before = process_rss_bytes()
        if rss_before is not None:
            rss_samples.append(rss_before)
        sample_interval = max(1, session_iterations // 10)
        for iteration in range(session_iterations):
            started = time.perf_counter()
            with SearchSession(api, observation, inputs) as session:
                begin_times.append((time.perf_counter() - started) * 1000)
                root_ids.append(session.root.searchId)
                select = session.root.observation.select
                stepped = time.perf_counter()
                session.step(session.root, legal_probe_selection(select, 0))
                step_times.append((time.perf_counter() - stepped) * 1000)
            if (iteration + 1) % sample_interval == 0:
                sample = process_rss_bytes()
                if sample is not None:
                    rss_samples.append(sample)
        rss_after = process_rss_bytes()
        if rss_after is not None and (not rss_samples or rss_samples[-1] != rss_after):
            rss_samples.append(rss_after)
    finally:
        game.battle_finish()

    middle_rss = rss_samples[len(rss_samples) // 2] if rss_samples else None

    return ConformanceResult(
        branch_parent_reusable=release.parent_reusable,
        child_survives_parent_release=release.child_survives_parent_release,
        sibling_survives_leaf_release=release.sibling_survives_leaf_release,
        descendant_survives_ancestor_release=release.descendant_survives_ancestor_release,
        released_state_rejected=release.released_state_rejected,
        double_release_idempotent=release.double_release_idempotent,
        crossed_turn_boundary=crossed_turn,
        max_path_steps=path_steps,
        replay_exact=replay.exact,
        replay_terminal=replay.terminal,
        replay_second_terminal=replay.second_terminal,
        replay_steps=replay.steps,
        replay_mismatch_step=replay.mismatch_step,
        replay_stochastic_boundary_step=replay.stochastic_boundary_step,
        replay_stochastic_boundary_reason=replay.stochastic_boundary_reason,
        replay_coin_events=replay.coin_events,
        session_iterations=session_iterations,
        root_ids_reused_across_sessions=len(set(root_ids)) < len(root_ids),
        begin_ms_median=statistics.median(begin_times),
        step_ms_median=statistics.median(step_times),
        rss_before_bytes=rss_before,
        rss_after_bytes=rss_after,
        rss_delta_bytes=(rss_after - rss_before) if rss_before is not None and rss_after is not None else None,
        rss_peak_bytes=max(rss_samples) if rss_samples else None,
        rss_tail_growth_bytes=(rss_after - middle_rss) if rss_after is not None and middle_rss is not None else None,
        errors=errors,
    )


def run_coin_distribution_probe(*, trials: int = 200, max_steps: int = 80) -> dict[str, Any]:
    """Exercise an Applin coin attack without controlling the outcome."""
    if trials < 2 or max_steps < 1:
        raise ValueError("trials must be at least 2 and max_steps must be positive")
    deck = [92] * 4 + [1] * 56
    observation, game, api = find_searchable_observation(deck)
    inputs = repeated_prediction_inputs(observation, deck, deck)
    heads = 0
    tails = 0
    no_coin = 0
    errors: list[str] = []
    try:
        for _ in range(trials):
            found: bool | None = None
            try:
                with SearchSession(api, observation, inputs) as session:
                    state = session.root
                    for _ in range(max_steps):
                        current = state.observation.current
                        if current is None or current.result != -1 or state.observation.select is None:
                            break
                        state = session.step(state, conformance_action(state.observation, api))
                        for log in state.observation.logs:
                            if log.type == api.LogType.COIN:
                                found = bool(log.head)
                                break
                        if found is not None:
                            break
            except Exception as exc:
                if len(errors) < 10:
                    errors.append(repr(exc))
            if found is True:
                heads += 1
            elif found is False:
                tails += 1
            else:
                no_coin += 1
    finally:
        game.battle_finish()

    observed = heads + tails
    head_rate = heads / observed if observed else None
    # This is a broad corruption/forced-outcome guard, not a precision fairness
    # test. Statistical quality belongs to the later evaluation framework.
    passed = not errors and observed >= trials * 0.9 and heads > 0 and tails > 0
    return {
        "trials": trials,
        "heads": heads,
        "tails": tails,
        "no_coin": no_coin,
        "head_rate": head_rate,
        "passed": passed,
        "errors": errors,
    }
