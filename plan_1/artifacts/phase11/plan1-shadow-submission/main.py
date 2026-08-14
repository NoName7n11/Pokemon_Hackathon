from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path
from typing import Any


def _asset_root() -> Path:
    module_file = globals().get("__file__")
    if module_file:
        return Path(module_file).resolve().parent
    kaggle_root = Path("/kaggle_simulations/agent")
    return kaggle_root if kaggle_root.is_dir() else Path.cwd()


_ROOT = _asset_root()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_RUNTIME: Any | None = None
_FALLBACK: Any | None = None
_STATUS: dict[str, Any] = {
    "agent_status": "uninitialized",
    "model_status": "uninitialized",
    "model_error": None,
    "agent_error": None,
    "model_load_ms": None,
}


def read_deck_csv() -> list[int]:
    rows = [line.strip() for line in (_ROOT / "deck.csv").read_text(encoding="utf-8").splitlines()]
    deck = [int(row) for row in rows if row]
    if len(deck) != 60 or any(card_id <= 0 for card_id in deck):
        raise ValueError("deck.csv must contain exactly 60 positive card IDs")
    return deck


def _fallback_module() -> Any:
    global _FALLBACK
    if _FALLBACK is None:
        _FALLBACK = importlib.import_module("fallback_agent")
        _FALLBACK._MY_DECK = read_deck_csv()
    return _FALLBACK


def _initialize_runtime() -> Any | None:
    global _RUNTIME
    if _RUNTIME is not None or _STATUS["agent_status"] != "uninitialized":
        return _RUNTIME
    try:
        api = importlib.import_module("cg.api")
        from plan1.config import load_config
        from plan1.model.inference import ModelInference
        from plan1.model.policy_value import PolicyValueModel
        from plan1.search.agent import Plan1MCTSAgent

        deck = read_deck_csv()
        fallback = _fallback_module()
        policy_value = None
        started = time.perf_counter_ns()
        try:
            policy_value = ModelInference(PolicyValueModel.load(_ROOT / "model.json"))
            _STATUS["model_status"] = "loaded"
        except Exception as exc:
            _STATUS["model_status"] = "disabled"
            _STATUS["model_error"] = f"{type(exc).__name__}:{exc}"
        finally:
            _STATUS["model_load_ms"] = (time.perf_counter_ns() - started) / 1_000_000
        _RUNTIME = Plan1MCTSAgent(
            api,
            deck,
            load_config(_ROOT / "search.json"),
            opponent_deck=deck,
            fallback_policy=fallback._greedy_select,
            rollout_policy=fallback._greedy_select,
            action_observer=fallback._record_if_ability,
            policy_value=policy_value,
            puct_constant=1.0,
            learned_value_mix=0.10,
        )
        _STATUS["agent_status"] = "ready_model" if policy_value is not None else "ready_heuristic"
    except Exception as exc:
        _STATUS["agent_status"] = "fallback_only"
        _STATUS["agent_error"] = f"{type(exc).__name__}:{exc}"
        _RUNTIME = None
    return _RUNTIME


def deployment_status(*, initialize: bool = False) -> dict[str, Any]:
    if initialize:
        _initialize_runtime()
    return dict(_STATUS)


def reset_runtime() -> None:
    global _RUNTIME, _FALLBACK
    _RUNTIME = None
    _FALLBACK = None
    _STATUS.update({
        "agent_status": "uninitialized",
        "model_status": "uninitialized",
        "model_error": None,
        "agent_error": None,
        "model_load_ms": None,
    })


def _minimal_legal_action(observation: dict[str, Any]) -> list[int]:
    selection = observation.get("select") if isinstance(observation, dict) else None
    if selection is None:
        return read_deck_csv()
    options = selection.get("option") or []
    minimum = selection.get("minCount", 0) or 0
    return list(range(min(int(minimum), len(options))))


def agent(observation: dict[str, Any]) -> list[int]:
    if not isinstance(observation, dict):
        return []
    if observation.get("select") is None:
        try:
            return read_deck_csv()
        except Exception:
            return []
    runtime = _initialize_runtime()
    if runtime is not None:
        try:
            return list(runtime.act(observation))
        except Exception as exc:
            _STATUS["agent_error"] = f"runtime:{type(exc).__name__}:{exc}"
    try:
        fallback = _fallback_module()
        converted = fallback.to_observation_class(observation)
        return list(fallback._greedy_select(converted))
    except Exception as exc:
        _STATUS["agent_error"] = f"fallback:{type(exc).__name__}:{exc}"
        return _minimal_legal_action(observation)
