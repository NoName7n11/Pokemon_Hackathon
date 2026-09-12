from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DeploymentConfigError(ValueError):
    """Raised when a Phase 11 configuration violates its strict contract."""


@dataclass(frozen=True, slots=True)
class RuntimeLimits:
    maximum_archive_bytes: int
    maximum_import_ms: float
    maximum_model_load_ms: float
    maximum_decision_p95_ms: float
    maximum_decision_ms: float


@dataclass(frozen=True, slots=True)
class DeploymentConfig:
    schema_version: int
    run_id: str
    package_name: str
    deck_path: Path
    fallback_path: Path
    search_config_path: Path
    checkpoint_path: Path
    frozen_evaluation_path: Path
    output_root: Path
    archive_path: Path
    shadow_games: int
    max_steps: int
    signer: str
    runtime_limits: RuntimeLimits


def _object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DeploymentConfigError(f"{location} must be an object")
    return value


def _strict(value: dict[str, Any], expected: set[str], location: str) -> None:
    missing = expected - value.keys()
    extra = value.keys() - expected
    if missing or extra:
        raise DeploymentConfigError(
            f"{location} keys differ: missing={sorted(missing)}, extra={sorted(extra)}"
        )


def _positive_int(value: Any, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DeploymentConfigError(f"{location} must be a positive integer")
    return value


def _positive_number(value: Any, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise DeploymentConfigError(f"{location} must be a positive number")
    return float(value)


def load_deployment_config(path: Path) -> DeploymentConfig:
    try:
        root = _object(json.loads(path.read_text(encoding="utf-8")), "config")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeploymentConfigError(f"could not read deployment config {path}: {exc}") from exc
    expected = {
        "schema_version", "run_id", "package_name", "deck_path", "fallback_path",
        "search_config_path", "checkpoint_path", "frozen_evaluation_path", "output_root",
        "archive_path", "shadow_games", "max_steps", "signer", "runtime_limits",
    }
    _strict(root, expected, "config")
    if root["schema_version"] != 1:
        raise DeploymentConfigError("config.schema_version must equal 1")
    for name in ("run_id", "package_name", "signer"):
        if not isinstance(root[name], str) or not root[name].strip():
            raise DeploymentConfigError(f"config.{name} must be a non-empty string")
    limits = _object(root["runtime_limits"], "config.runtime_limits")
    _strict(
        limits,
        {
            "maximum_archive_bytes", "maximum_import_ms", "maximum_model_load_ms",
            "maximum_decision_p95_ms", "maximum_decision_ms",
        },
        "config.runtime_limits",
    )
    return DeploymentConfig(
        schema_version=1,
        run_id=root["run_id"],
        package_name=root["package_name"],
        deck_path=Path(root["deck_path"]),
        fallback_path=Path(root["fallback_path"]),
        search_config_path=Path(root["search_config_path"]),
        checkpoint_path=Path(root["checkpoint_path"]),
        frozen_evaluation_path=Path(root["frozen_evaluation_path"]),
        output_root=Path(root["output_root"]),
        archive_path=Path(root["archive_path"]),
        shadow_games=_positive_int(root["shadow_games"], "config.shadow_games"),
        max_steps=_positive_int(root["max_steps"], "config.max_steps"),
        signer=root["signer"],
        runtime_limits=RuntimeLimits(
            maximum_archive_bytes=_positive_int(
                limits["maximum_archive_bytes"], "config.runtime_limits.maximum_archive_bytes"
            ),
            maximum_import_ms=_positive_number(
                limits["maximum_import_ms"], "config.runtime_limits.maximum_import_ms"
            ),
            maximum_model_load_ms=_positive_number(
                limits["maximum_model_load_ms"], "config.runtime_limits.maximum_model_load_ms"
            ),
            maximum_decision_p95_ms=_positive_number(
                limits["maximum_decision_p95_ms"],
                "config.runtime_limits.maximum_decision_p95_ms",
            ),
            maximum_decision_ms=_positive_number(
                limits["maximum_decision_ms"], "config.runtime_limits.maximum_decision_ms"
            ),
        ),
    )
