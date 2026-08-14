from __future__ import annotations

import gzip
import io
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

from plan1.data.manifests import CorpusManifest, ManifestEntry, ManifestError, SplitPolicy
from plan1.data.trajectory import GameTrajectory, TrajectoryError
from plan1.paths import ensure_within
from plan1.reproducibility import canonical_json_hash, sha256_file, write_json_atomic


MAX_TRAJECTORY_COMPRESSED_BYTES = 64 * 1024 * 1024
MAX_TRAJECTORY_JSON_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    max_games: int | None = None
    max_bytes: int | None = None

    def __post_init__(self) -> None:
        if self.max_games is not None and self.max_games < 1:
            raise ValueError("max_games must be positive when supplied")
        if self.max_bytes is not None and self.max_bytes < 1:
            raise ValueError("max_bytes must be positive when supplied")


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def _gzip_bytes(value: Any) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, compresslevel=6, mtime=0) as handle:
        handle.write(_json_bytes(value))
    return output.getvalue()


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class CorpusStore:
    def __init__(self, root: Path, corpus_id: str, split_policy: SplitPolicy | None = None) -> None:
        if not corpus_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in corpus_id):
            raise ValueError("corpus_id may contain only letters, digits, hyphen, and underscore")
        self.root = root.resolve()
        self.corpus_id = corpus_id
        self.games = self.root / "games"
        self.manifests = self.root / "manifests"
        self.quarantine = self.root / "quarantine"
        self.retired = self.root / "retired"
        self.pointer = self.root / "CURRENT.json"
        self.split_policy = split_policy or SplitPolicy()
        for directory in (self.games, self.manifests, self.quarantine, self.retired):
            directory.mkdir(parents=True, exist_ok=True)
        if not self.pointer.exists():
            self._write_revision(())
        else:
            current = self.load_manifest()
            if current.corpus_id != corpus_id or current.split_policy != self.split_policy:
                raise ManifestError("existing corpus identity or split policy differs")

    def load_manifest(self) -> CorpusManifest:
        pointer = json.loads(self.pointer.read_text(encoding="utf-8"))
        if set(pointer) != {"schema_version", "revision", "manifest", "manifest_sha256"}:
            raise ManifestError("CURRENT pointer schema differs")
        path = ensure_within(self.root / pointer["manifest"], self.manifests)
        if sha256_file(path) != pointer["manifest_sha256"]:
            raise ManifestError("CURRENT manifest checksum mismatch")
        manifest = CorpusManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
        if manifest.revision != pointer["revision"]:
            raise ManifestError("CURRENT revision differs from manifest")
        current = manifest
        expected_revision = manifest.revision
        while expected_revision > 0:
            previous = self.manifests / f"manifest-{expected_revision - 1:06d}.json"
            if not previous.exists() or sha256_file(previous) != current.previous_manifest_sha256:
                raise ManifestError(f"manifest hash chain is broken at revision {current.revision}")
            current = CorpusManifest.from_dict(json.loads(previous.read_text(encoding="utf-8")))
            expected_revision -= 1
            if current.revision != expected_revision:
                raise ManifestError("manifest revision filename and payload differ")
        if current.previous_manifest_sha256 is not None:
            raise ManifestError("manifest revision zero has a previous link")
        return manifest

    def commit(self, trajectory: GameTrajectory) -> ManifestEntry:
        trajectory.validate()
        manifest = self.load_manifest()
        existing = next((entry for entry in manifest.entries if entry.game_id == trajectory.game_id), None)
        content_hash = trajectory.fingerprint
        if existing is not None:
            if existing.content_sha256 != content_hash:
                raise ManifestError(f"game ID collision for {trajectory.game_id}")
            self.read_entry(existing)
            return existing

        split = self.split_policy.assign(
            purpose=trajectory.purpose,
            seed_group=trajectory.seed_group,
            deck_hashes=[deck.sha256 for deck in trajectory.decks],
        )
        relative = Path("games") / split / f"{trajectory.game_id}.json.gz"
        path = ensure_within(self.root / relative, self.games)
        if path.exists():
            raise ManifestError(f"unmanifested game path already exists: {relative.as_posix()}")
        payload = _gzip_bytes(trajectory.to_dict())
        _atomic_bytes(path, payload)
        try:
            recovered = self.read_path(path)
            if recovered.fingerprint != content_hash:
                raise TrajectoryError("atomic write replay hash differs")
            entry = ManifestEntry(
                game_id=trajectory.game_id, relative_path=relative.as_posix(), file_sha256=sha256_file(path),
                content_sha256=content_hash, bytes=path.stat().st_size, decisions=len(trajectory.decisions),
                purpose=trajectory.purpose, split=split, seed=trajectory.seed, seed_group=trajectory.seed_group,
                deck_sha256=(trajectory.decks[0].sha256, trajectory.decks[1].sha256),
                policy_names=(trajectory.policies[0].name, trajectory.policies[1].name),
                final_result=trajectory.final_result, created_utc=trajectory.created_utc,
            )
            entry.validate()
            self._write_revision((*manifest.entries, entry))
            return entry
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def read_path(self, path: Path) -> GameTrajectory:
        resolved = ensure_within(path, self.root)
        if resolved.stat().st_size > MAX_TRAJECTORY_COMPRESSED_BYTES:
            raise TrajectoryError("compressed trajectory exceeds the safety limit")
        try:
            with gzip.open(resolved, "rb") as handle:
                payload = handle.read(MAX_TRAJECTORY_JSON_BYTES + 1)
            if len(payload) > MAX_TRAJECTORY_JSON_BYTES:
                raise TrajectoryError("decompressed trajectory exceeds the safety limit")
            value = json.loads(payload.decode("ascii"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise TrajectoryError(f"could not decode trajectory {resolved.name}: {exc}") from exc
        return GameTrajectory.from_dict(value)

    def read_entry(self, entry: ManifestEntry) -> GameTrajectory:
        path = ensure_within(self.root / entry.relative_path, self.games)
        if not path.is_file() or sha256_file(path) != entry.file_sha256:
            raise TrajectoryError(f"trajectory file checksum mismatch: {entry.game_id}")
        trajectory = self.read_path(path)
        if trajectory.fingerprint != entry.content_sha256 or trajectory.game_id != entry.game_id:
            raise TrajectoryError(f"trajectory content checksum mismatch: {entry.game_id}")
        return trajectory

    def validate_all(self) -> dict[str, Any]:
        manifest = self.load_manifest()
        errors = []
        decisions = 0
        for entry in manifest.entries:
            try:
                decisions += len(self.read_entry(entry).decisions)
            except Exception as exc:
                errors.append({"game_id": entry.game_id, "error": f"{type(exc).__name__}:{exc}"})
        return {
            "games": len(manifest.entries), "decisions": decisions, "errors": errors,
            "manifest_revision": manifest.revision, "manifest_sha256": manifest.fingerprint,
            "passed": not errors,
        }

    def repair(self) -> dict[str, Any]:
        manifest = self.load_manifest()
        kept = []
        quarantined = []
        staged: list[tuple[Path, Path]] = []
        for entry in manifest.entries:
            path = ensure_within(self.root / entry.relative_path, self.games)
            try:
                self.read_entry(entry)
                kept.append(entry)
            except Exception as exc:
                destination = self.quarantine / f"{entry.game_id}-{entry.file_sha256[:12]}.json.gz"
                if path.exists():
                    if destination.exists() and sha256_file(destination) != sha256_file(path):
                        destination = self.quarantine / f"{entry.game_id}-{entry.file_sha256}.json.gz"
                    shutil.copy2(path, destination)
                    staged.append((path, destination))
                quarantined.append({"game_id": entry.game_id, "error": f"{type(exc).__name__}:{exc}"})
        if quarantined:
            self._write_revision(tuple(kept))
            for source, _ in staged:
                source.unlink(missing_ok=True)
        return {"quarantined": quarantined, "kept": len(kept), "changed": bool(quarantined)}

    def apply_retention(self, policy: RetentionPolicy) -> dict[str, Any]:
        manifest = self.load_manifest()
        entries = list(manifest.entries)
        total_bytes = sum(entry.bytes for entry in entries)
        removed = []
        staged: list[tuple[Path, Path]] = []
        while entries and (
            (policy.max_games is not None and len(entries) > policy.max_games)
            or (policy.max_bytes is not None and total_bytes > policy.max_bytes)
        ):
            candidates = [entry for entry in entries if entry.purpose == "training"]
            if not candidates:
                break
            oldest = min(candidates, key=lambda entry: (entry.created_utc, entry.game_id))
            source = ensure_within(self.root / oldest.relative_path, self.games)
            destination = self.retired / f"{oldest.game_id}-{oldest.file_sha256[:12]}.json.gz"
            if source.exists():
                if destination.exists() and sha256_file(destination) != sha256_file(source):
                    destination = self.retired / f"{oldest.game_id}-{oldest.file_sha256}.json.gz"
                shutil.copy2(source, destination)
                staged.append((source, destination))
            entries.remove(oldest)
            total_bytes -= oldest.bytes
            removed.append(oldest.game_id)
        if removed:
            self._write_revision(tuple(entries))
            for source, _ in staged:
                source.unlink(missing_ok=True)
        limits_met = (
            (policy.max_games is None or len(entries) <= policy.max_games)
            and (policy.max_bytes is None or total_bytes <= policy.max_bytes)
        )
        return {"retired": removed, "remaining_games": len(entries), "remaining_bytes": total_bytes, "limits_met": limits_met}

    def _write_revision(self, entries: Sequence[ManifestEntry]) -> CorpusManifest:
        previous = None
        revision = 0
        if self.pointer.exists():
            current = self.load_manifest()
            revision = current.revision + 1
            previous_path = self.manifests / f"manifest-{current.revision:06d}.json"
            previous = sha256_file(previous_path)
        manifest = CorpusManifest(
            schema_version=1, corpus_id=self.corpus_id, revision=revision,
            created_utc=datetime.now(timezone.utc).isoformat(), previous_manifest_sha256=previous,
            split_policy=self.split_policy, entries=tuple(entries),
        )
        manifest.validate()
        path = self.manifests / f"manifest-{revision:06d}.json"
        write_json_atomic(path, manifest.to_dict())
        write_json_atomic(
            self.pointer,
            {"schema_version": 1, "revision": revision, "manifest": path.relative_to(self.root).as_posix(), "manifest_sha256": sha256_file(path)},
        )
        return manifest


class ReplayReader:
    def __init__(self, store: CorpusStore, splits: Sequence[str] = ("train",)) -> None:
        requested = frozenset(splits)
        if not requested or not requested <= {"train", "validation", "test"}:
            raise ValueError("training replay splits must be train, validation, and/or test")
        self.store = store
        self.splits = requested

    def games(self) -> Iterator[GameTrajectory]:
        manifest = self.store.load_manifest()
        for entry in manifest.entries:
            if entry.purpose == "evaluation":
                continue
            if entry.split in self.splits:
                yield self.store.read_entry(entry)

    def decisions(self) -> Iterator[Any]:
        for game in self.games():
            yield from game.decisions

    def distribution(self) -> dict[str, Any]:
        games = list(self.games())
        contexts: dict[str, int] = {}
        outcomes: dict[str, int] = {}
        decks: dict[str, int] = {}
        models: dict[str, int] = {}
        decisions = 0
        for game in games:
            outcomes[str(game.final_result)] = outcomes.get(str(game.final_result), 0) + 1
            for deck in game.decks:
                decks[deck.sha256] = decks.get(deck.sha256, 0) + 1
            for policy in game.policies:
                models[f"{policy.name}:{policy.version}"] = models.get(f"{policy.name}:{policy.version}", 0) + 1
            for decision in game.decisions:
                record = decision.observation["selection"]
                key = f"{record['select_type']}:{record['context']}"
                contexts[key] = contexts.get(key, 0) + 1
                decisions += 1
        return {
            "games": len(games), "decisions": decisions,
            "outcomes": dict(sorted(outcomes.items())), "decks": dict(sorted(decks.items())),
            "models": dict(sorted(models.items())), "selection_contexts": dict(sorted(contexts.items())),
        }
