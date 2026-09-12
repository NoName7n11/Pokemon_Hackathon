from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plan1.reproducibility import canonical_json_hash, sha256_file, write_json_atomic


ARCHIVE_SCHEMA_VERSION = 1
_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


class ArchiveError(ValueError):
    """Raised when Phase 12 evidence cannot be verified or archived safely."""


@dataclass(frozen=True, slots=True)
class ArchiveConfig:
    schema_version: int
    run_id: str
    claims_path: Path
    manifest_path: Path
    archive_path: Path
    signer: str
    include_globs: tuple[str, ...]


def load_archive_config(path: Path) -> ArchiveConfig:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArchiveError(f"could not read archive config {path}: {exc}") from exc
    expected = {
        "schema_version", "run_id", "claims_path", "manifest_path",
        "archive_path", "signer", "include_globs",
    }
    if not isinstance(data, dict) or set(data) != expected:
        raise ArchiveError("archive config keys differ from the strict schema")
    if data["schema_version"] != ARCHIVE_SCHEMA_VERSION:
        raise ArchiveError("archive config schema_version must equal 1")
    for name in ("run_id", "claims_path", "manifest_path", "archive_path", "signer"):
        if not isinstance(data[name], str) or not data[name].strip():
            raise ArchiveError(f"archive config {name} must be a non-empty string")
    patterns = data["include_globs"]
    if not isinstance(patterns, list) or not patterns or not all(
        isinstance(item, str) and item.strip() for item in patterns
    ):
        raise ArchiveError("include_globs must be a non-empty list of strings")
    return ArchiveConfig(
        schema_version=1,
        run_id=data["run_id"],
        claims_path=Path(data["claims_path"]),
        manifest_path=Path(data["manifest_path"]),
        archive_path=Path(data["archive_path"]),
        signer=data["signer"],
        include_globs=tuple(patterns),
    )


def json_path_value(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise ArchiveError(f"JSON path does not exist: {path}")
    return current


def verify_claims(claims_path: Path, *, repo_root: Path) -> dict[str, Any]:
    try:
        data = json.loads(claims_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArchiveError(f"could not read claims {claims_path}: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"schema_version", "claims"}:
        raise ArchiveError("claims file keys differ from the strict schema")
    if data["schema_version"] != 1 or not isinstance(data["claims"], list):
        raise ArchiveError("claims schema is invalid")
    results = []
    failures = []
    evidence_cache: dict[Path, Any] = {}
    seen_ids = set()
    for claim in data["claims"]:
        if not isinstance(claim, dict) or set(claim) != {"id", "statement", "evidence"}:
            raise ArchiveError("claim keys differ from the strict schema")
        claim_id = claim["id"]
        if not isinstance(claim_id, str) or not claim_id or claim_id in seen_ids:
            raise ArchiveError(f"invalid or duplicate claim id: {claim_id!r}")
        seen_ids.add(claim_id)
        checks = []
        for evidence in claim["evidence"]:
            if not isinstance(evidence, dict) or set(evidence) != {"path", "json_path", "expected"}:
                raise ArchiveError(f"claim {claim_id} evidence keys differ")
            path = (repo_root / evidence["path"]).resolve()
            try:
                path.relative_to(repo_root.resolve())
            except ValueError as exc:
                raise ArchiveError(f"claim path escapes repository: {path}") from exc
            if path not in evidence_cache:
                try:
                    evidence_cache[path] = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                    raise ArchiveError(f"could not read claim evidence {path}: {exc}") from exc
            actual = json_path_value(evidence_cache[path], evidence["json_path"])
            passed = actual == evidence["expected"]
            check = {
                "path": path.relative_to(repo_root).as_posix(),
                "file_sha256": sha256_file(path),
                "json_path": evidence["json_path"],
                "expected": evidence["expected"],
                "actual": actual,
                "passed": passed,
            }
            checks.append(check)
            if not passed:
                failures.append(f"{claim_id}:{evidence['json_path']}")
        results.append({
            "id": claim_id,
            "statement": claim["statement"],
            "checks": checks,
            "passed": all(check["passed"] for check in checks),
        })
    return {
        "claims": len(results),
        "checks": sum(len(item["checks"]) for item in results),
        "passed": not failures,
        "failures": failures,
        "results": results,
    }


def collect_evidence(config: ArchiveConfig, *, repo_root: Path) -> tuple[Path, ...]:
    root = repo_root.resolve()
    files: set[Path] = set()
    for pattern in config.include_globs:
        matches = [path for path in root.glob(pattern) if path.is_file()]
        if not matches:
            raise ArchiveError(f"archive include pattern matched no files: {pattern}")
        for path in matches:
            resolved = path.resolve()
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise ArchiveError(f"archive file escapes repository: {resolved}") from exc
            if "__pycache__" not in resolved.parts and resolved.suffix != ".pyc":
                files.add(resolved)
    return tuple(sorted(files, key=lambda path: path.relative_to(root).as_posix()))


def _manifest(config: ArchiveConfig, files: tuple[Path, ...], *, repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    payload = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "run_id": config.run_id,
        "claims_path": config.claims_path.as_posix(),
        "claims_sha256": sha256_file(root / config.claims_path),
        "files": [
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }
    payload["manifest_sha256"] = canonical_json_hash(payload)
    return payload


def _write_archive(
    archive_path: Path,
    files: tuple[Path, ...],
    manifest_path: Path,
    *,
    repo_root: Path,
) -> None:
    root = repo_root.resolve()
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive_path.with_suffix(archive_path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, _ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo("evidence-manifest.json", _ZIP_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        archive.writestr(info, manifest_path.read_bytes())
    temporary.replace(archive_path)


def verify_archive(archive_path: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checksum = manifest.get("manifest_sha256")
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    errors = []
    if checksum != canonical_json_hash(unsigned):
        errors.append("manifest_checksum_mismatch")
    declared = {item["path"]: item for item in manifest.get("files", [])}
    with zipfile.ZipFile(archive_path, "r") as archive:
        names = set(archive.namelist())
        expected = set(declared) | {"evidence-manifest.json"}
        if names != expected:
            errors.append("archive_entries_differ")
        for relative, item in declared.items():
            if relative not in names:
                continue
            content = archive.read(relative)
            import hashlib
            if len(content) != item["bytes"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
                errors.append(f"archive_file_mismatch:{relative}")
        if "evidence-manifest.json" in names and archive.read("evidence-manifest.json") != manifest_path.read_bytes():
            errors.append("embedded_manifest_mismatch")
    return {
        "passed": not errors,
        "errors": errors,
        "files": len(declared),
        "manifest_sha256": checksum,
        "archive_bytes": archive_path.stat().st_size,
        "archive_sha256": sha256_file(archive_path),
    }


def build_evidence_archive(config: ArchiveConfig, *, repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    claims = verify_claims(root / config.claims_path, repo_root=root)
    if not claims["passed"]:
        raise ArchiveError(f"claim verification failed: {claims['failures']}")
    files = collect_evidence(config, repo_root=root)
    manifest = _manifest(config, files, repo_root=root)
    write_json_atomic(root / config.manifest_path, manifest)
    _write_archive(root / config.archive_path, files, root / config.manifest_path, repo_root=root)
    verification = verify_archive(root / config.archive_path, root / config.manifest_path)
    if not verification["passed"]:
        raise ArchiveError(f"archive verification failed: {verification['errors']}")
    return {"claims": claims, "manifest": manifest, "archive": verification}
