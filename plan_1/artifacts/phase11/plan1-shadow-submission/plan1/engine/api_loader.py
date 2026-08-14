from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

from plan1.paths import ENGINE_PARENT


class EngineImportError(RuntimeError):
    """Raised when the bundled competition API cannot be imported."""


def load_competition_api(engine_parent: Path = ENGINE_PARENT) -> ModuleType:
    parent = engine_parent.resolve()
    if not (parent / "cg" / "api.py").is_file():
        raise EngineImportError(f"competition API not found under {parent}")
    parent_text = str(parent)
    if parent_text not in sys.path:
        sys.path.insert(0, parent_text)
    try:
        return importlib.import_module("cg.api")
    except Exception as exc:
        raise EngineImportError(f"could not import competition API from {parent}: {exc}") from exc
