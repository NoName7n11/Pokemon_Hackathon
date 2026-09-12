from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

from plan1.deployment.config import DeploymentConfig
from plan1.reproducibility import canonical_json_hash, sha256_file, write_json_atomic


PACKAGE_SCHEMA_VERSION = 1
_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def _copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _copy_plan1_source(source_root: Path, destination_root: Path) -> None:
    for source in sorted(source_root.rglob("*.py")):
        if "__pycache__" in source.parts:
            continue
        relative = source.relative_to(source_root)
        _copy_file(source, destination_root / relative)


def _manifest(package_root: Path, config: DeploymentConfig) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in package_root.rglob("*") if item.is_file()):
        relative = path.relative_to(package_root).as_posix()
        if relative == "manifest.json":
            continue
        files.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    payload = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "run_id": config.run_id,
        "package_name": config.package_name,
        "entrypoint": "main.py",
        "network_required": False,
        "files": files,
        "source_identity": {
            "deck_sha256": sha256_file(config.deck_path),
            "fallback_sha256": sha256_file(config.fallback_path),
            "search_config_sha256": sha256_file(config.search_config_path),
            "checkpoint_sha256": sha256_file(config.checkpoint_path),
            "frozen_evaluation_sha256": sha256_file(config.frozen_evaluation_path),
        },
    }
    payload["manifest_sha256"] = canonical_json_hash(payload)
    return payload


def _deterministic_zip(package_root: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive_path.with_suffix(archive_path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in package_root.rglob("*") if item.is_file()):
            relative = path.relative_to(package_root).as_posix()
            info = zipfile.ZipInfo(relative, _ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    temporary.replace(archive_path)


def verify_submission_package(package_root: Path) -> dict[str, Any]:
    manifest_path = package_root / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    checksum = data.get("manifest_sha256")
    unsigned = dict(data)
    unsigned.pop("manifest_sha256", None)
    errors = []
    if checksum != canonical_json_hash(unsigned):
        errors.append("manifest_checksum_mismatch")
    declared = {item["path"]: item for item in data.get("files", [])}
    actual = {
        path.relative_to(package_root).as_posix(): path
        for path in package_root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if set(declared) != set(actual):
        errors.append("declared_files_differ")
    for relative, item in declared.items():
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            errors.append(f"unsafe_path:{relative}")
            continue
        path = actual.get(relative)
        if path is None:
            continue
        if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            errors.append(f"file_identity_mismatch:{relative}")
    required = {"main.py", "deck.csv", "fallback_agent.py", "search.json", "model.json"}
    if not required.issubset(actual):
        errors.append("required_files_missing")
    return {
        "passed": not errors,
        "errors": errors,
        "file_count": len(actual),
        "total_bytes": sum(path.stat().st_size for path in actual.values()) + manifest_path.stat().st_size,
        "manifest_sha256": checksum,
    }


def build_submission_package(config: DeploymentConfig, *, source_root: Path) -> dict[str, Any]:
    if Path(config.package_name).name != config.package_name:
        raise ValueError("package_name must be one path component")
    package_root = config.output_root / config.package_name
    try:
        package_root.resolve().relative_to(config.output_root.resolve())
    except ValueError as exc:
        raise ValueError("package root escapes output_root") from exc
    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True)
    runtime_source = source_root / "plan1" / "deployment" / "runtime_main.py"
    _copy_file(runtime_source, package_root / "main.py")
    _copy_file(config.deck_path, package_root / "deck.csv")
    _copy_file(config.fallback_path, package_root / "fallback_agent.py")
    _copy_file(config.search_config_path, package_root / "search.json")
    _copy_file(config.checkpoint_path, package_root / "model.json")
    _copy_plan1_source(source_root / "plan1", package_root / "plan1")
    manifest = _manifest(package_root, config)
    write_json_atomic(package_root / "manifest.json", manifest)
    verification = verify_submission_package(package_root)
    if not verification["passed"]:
        raise ValueError(f"built package failed verification: {verification['errors']}")
    _deterministic_zip(package_root, config.archive_path)
    return {
        "package_root": str(package_root.resolve()),
        "archive_path": str(config.archive_path.resolve()),
        "archive_bytes": config.archive_path.stat().st_size,
        "archive_sha256": sha256_file(config.archive_path),
        "manifest": manifest,
        "verification": verification,
    }
