from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_directory(path: Path, excluded_names: set[str] | None = None) -> str:
    excluded = excluded_names or {"__pycache__"}
    digest = hashlib.sha256()
    for item in sorted((p for p in path.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        if any(part in excluded for part in item.relative_to(path).parts):
            continue
        relative = item.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(sha256_file(item)))
    return digest.hexdigest()


def canonical_json_hash(value: Any) -> str:
    if is_dataclass(value):
        value = asdict(value)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _git(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip()


def git_identity(repo_root: Path) -> dict[str, Any]:
    commit = _git(repo_root, "rev-parse", "HEAD")
    status = _git(repo_root, "status", "--porcelain")
    return {
        "commit": commit,
        "dirty": bool(status) if status is not None else None,
        "status_available": status is not None,
    }


def derive_seed(root_seed: int, namespace: str, index: int) -> int:
    if root_seed < 0 or index < 0:
        raise ValueError("root_seed and index must be non-negative")
    payload = f"plan1:{root_seed}:{namespace}:{index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF


def build_manifest(
    repo_root: Path,
    config: Any,
    tracked_files: Iterable[Path],
    *,
    run_kind: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    for supplied in tracked_files:
        path = supplied.resolve()
        relative = path.relative_to(repo_root.resolve()).as_posix()
        if not path.is_file():
            raise FileNotFoundError(path)
        files[relative] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}

    now = datetime.now(timezone.utc)
    identity = run_id or f"{run_kind}-{now.strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    config_data = asdict(config) if is_dataclass(config) else config
    return {
        "schema_version": 1,
        "run_id": identity,
        "run_kind": run_kind,
        "created_utc": now.isoformat(),
        "git": git_identity(repo_root),
        "config": config_data,
        "config_sha256": canonical_json_hash(config_data),
        "files": files,
        "runtime": {
            "python": sys.version,
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
    }


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)
