from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when a Plan 1 configuration violates its strict contract."""


def _require_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{location} must be an object")
    return value


def _strict_keys(value: dict[str, Any], expected: set[str], location: str) -> None:
    missing = expected - value.keys()
    extra = value.keys() - expected
    if missing:
        raise ConfigError(f"{location} missing keys: {sorted(missing)}")
    if extra:
        raise ConfigError(f"{location} unknown keys: {sorted(extra)}")


def _positive_int(value: Any, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(f"{location} must be a positive integer")
    return value


def _nonnegative_int(value: Any, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConfigError(f"{location} must be a non-negative integer")
    return value


def _positive_number(value: Any, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ConfigError(f"{location} must be a positive number")
    return float(value)


@dataclass(frozen=True)
class SearchConfig:
    max_simulations: int
    max_depth: int
    max_nodes: int
    max_candidates: int
    time_budget_ms: int
    exploration_constant: float
    horizon_turns: int
    progressive_widening_base: float
    progressive_widening_exponent: float
    value_scale: float
    discount_factor: float
    require_full_root_coverage: bool


@dataclass(frozen=True)
class SafetyConfig:
    cleanup_reserve_ms: int
    allow_manual_coin: bool
    fallback_on_error: bool


@dataclass(frozen=True)
class ReproducibilityConfig:
    seed: int
    record_dirty_worktree: bool


@dataclass(frozen=True)
class Plan1Config:
    schema_version: int
    search: SearchConfig
    safety: SafetyConfig
    reproducibility: ReproducibilityConfig


def parse_config(data: Any) -> Plan1Config:
    root = _require_object(data, "config")
    _strict_keys(root, {"schema_version", "search", "safety", "reproducibility"}, "config")
    if root["schema_version"] != 1:
        raise ConfigError("config.schema_version must equal 1")

    search = _require_object(root["search"], "config.search")
    _strict_keys(
        search,
        {
            "max_simulations",
            "max_depth",
            "max_nodes",
            "max_candidates",
            "time_budget_ms",
            "exploration_constant",
            "horizon_turns",
            "progressive_widening_base",
            "progressive_widening_exponent",
            "value_scale",
            "discount_factor",
            "require_full_root_coverage",
        },
        "config.search",
    )
    widening_exponent = search["progressive_widening_exponent"]
    if (
        isinstance(widening_exponent, bool)
        or not isinstance(widening_exponent, (int, float))
        or not 0 < widening_exponent <= 1
    ):
        raise ConfigError("config.search.progressive_widening_exponent must be in (0, 1]")
    discount_factor = search["discount_factor"]
    if (
        isinstance(discount_factor, bool)
        or not isinstance(discount_factor, (int, float))
        or not 0 < discount_factor <= 1
    ):
        raise ConfigError("config.search.discount_factor must be in (0, 1]")
    if not isinstance(search["require_full_root_coverage"], bool):
        raise ConfigError("config.search.require_full_root_coverage must be boolean")

    safety = _require_object(root["safety"], "config.safety")
    _strict_keys(safety, {"cleanup_reserve_ms", "allow_manual_coin", "fallback_on_error"}, "config.safety")
    if safety["allow_manual_coin"] is not False:
        raise ConfigError("config.safety.allow_manual_coin must be false")
    if safety["fallback_on_error"] is not True:
        raise ConfigError("config.safety.fallback_on_error must be true")

    reproducibility = _require_object(root["reproducibility"], "config.reproducibility")
    _strict_keys(reproducibility, {"seed", "record_dirty_worktree"}, "config.reproducibility")
    if not isinstance(reproducibility["record_dirty_worktree"], bool):
        raise ConfigError("config.reproducibility.record_dirty_worktree must be boolean")

    result = Plan1Config(
        schema_version=1,
        search=SearchConfig(
            max_simulations=_positive_int(search["max_simulations"], "config.search.max_simulations"),
            max_depth=_positive_int(search["max_depth"], "config.search.max_depth"),
            max_nodes=_positive_int(search["max_nodes"], "config.search.max_nodes"),
            max_candidates=_positive_int(search["max_candidates"], "config.search.max_candidates"),
            time_budget_ms=_positive_int(search["time_budget_ms"], "config.search.time_budget_ms"),
            exploration_constant=_positive_number(
                search["exploration_constant"], "config.search.exploration_constant"
            ),
            horizon_turns=_nonnegative_int(search["horizon_turns"], "config.search.horizon_turns"),
            progressive_widening_base=_positive_number(
                search["progressive_widening_base"], "config.search.progressive_widening_base"
            ),
            progressive_widening_exponent=float(widening_exponent),
            value_scale=_positive_number(search["value_scale"], "config.search.value_scale"),
            discount_factor=float(discount_factor),
            require_full_root_coverage=search["require_full_root_coverage"],
        ),
        safety=SafetyConfig(
            cleanup_reserve_ms=_positive_int(safety["cleanup_reserve_ms"], "config.safety.cleanup_reserve_ms"),
            allow_manual_coin=False,
            fallback_on_error=True,
        ),
        reproducibility=ReproducibilityConfig(
            seed=_nonnegative_int(reproducibility["seed"], "config.reproducibility.seed"),
            record_dirty_worktree=reproducibility["record_dirty_worktree"],
        ),
    )
    if result.safety.cleanup_reserve_ms >= result.search.time_budget_ms:
        raise ConfigError("cleanup_reserve_ms must be smaller than time_budget_ms")
    return result


def load_config(path: Path) -> Plan1Config:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"could not read config {path}: {exc}") from exc
    return parse_config(data)
