from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from plan1.config import load_config
from plan1.engine import load_competition_api
from plan1.paths import ARTIFACT_ROOT, CONFIG_ROOT, ENGINE_PARENT, REPO_ROOT
from plan1.reproducibility import write_json_atomic


OPTIONAL_PACKAGES = ("numpy", "torch", "onnx", "onnxruntime", "gymnasium", "tensorboard")


def main() -> int:
    checks: dict[str, object] = {
        "python": sys.version,
        "python_supported": sys.version_info >= (3, 11),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "repo_root": str(REPO_ROOT),
        "engine_parent": str(ENGINE_PARENT),
        "packages": {name: importlib.util.find_spec(name) is not None for name in OPTIONAL_PACKAGES},
    }
    errors: list[str] = []
    try:
        config = load_config(CONFIG_ROOT / "mcts_baseline.json")
        checks["config_schema_version"] = config.schema_version
    except Exception as exc:
        errors.append(f"config: {exc}")
    try:
        api = load_competition_api()
        cards = api.all_card_data()
        attacks = api.all_attack()
        checks["engine"] = {"cards": len(cards), "attacks": len(attacks), "ok": bool(cards and attacks)}
    except Exception as exc:
        errors.append(f"engine: {exc}")
    checks["errors"] = errors
    checks["ok"] = checks["python_supported"] and not errors
    output = ARTIFACT_ROOT / "reports" / "phase0-environment.json"
    write_json_atomic(output, checks)
    print(json.dumps(checks, indent=2, ensure_ascii=True))
    print(f"Wrote {output}")
    return 0 if checks["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
