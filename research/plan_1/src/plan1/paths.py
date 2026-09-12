from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PACKAGE_ROOT.parents[1]
CONFIG_ROOT = PACKAGE_ROOT / "configs"
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts"
ENGINE_PARENT = REPO_ROOT / "sample_submission" / "sample_submission"
ACTIVE_SUBMISSION = ENGINE_PARENT


def ensure_within(path: Path, parent: Path) -> Path:
    """Resolve path and reject traversal outside parent."""
    resolved = path.resolve()
    try:
        resolved.relative_to(parent.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes allowed directory {parent}: {resolved}") from exc
    return resolved
