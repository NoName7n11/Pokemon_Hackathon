from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from plan1.reproducibility import canonical_json_hash


MANIFEST_SCHEMA_VERSION = 1
SPLITS = frozenset({"train", "validation", "test", "evaluation"})


class ManifestError(ValueError):
    """Raised when a corpus manifest or split assignment is invalid."""


def _strict(data: Mapping[str, Any], expected: set[str], location: str) -> None:
    missing = expected - data.keys()
    extra = data.keys() - expected
    if missing or extra:
        raise ManifestError(f"{location} keys differ; missing={sorted(missing)} extra={sorted(extra)}")


@dataclass(frozen=True, slots=True)
class SplitPolicy:
    train_percent: int = 80
    validation_percent: int = 10
    test_percent: int = 10
    holdout_deck_sha256: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = (self.train_percent, self.validation_percent, self.test_percent)
        if any(type(value) is not int or value < 0 for value in values) or sum(values) != 100:
            raise ManifestError("split percentages must be non-negative integers summing to 100")

    def assign(self, *, purpose: str, seed_group: str, deck_hashes: Sequence[str]) -> str:
        if purpose == "evaluation":
            return "evaluation"
        if purpose != "training":
            raise ManifestError("purpose must be training or evaluation")
        if not seed_group:
            raise ManifestError("seed group cannot be empty")
        if set(deck_hashes) & set(self.holdout_deck_sha256):
            return "test"
        bucket = int(canonical_json_hash({"seed_group": seed_group})[:16], 16) % 100
        if bucket < self.train_percent:
            return "train"
        if bucket < self.train_percent + self.validation_percent:
            return "validation"
        return "test"


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    game_id: str
    relative_path: str
    file_sha256: str
    content_sha256: str
    bytes: int
    decisions: int
    purpose: str
    split: str
    seed: int
    seed_group: str
    deck_sha256: tuple[str, str]
    policy_names: tuple[str, str]
    final_result: int
    created_utc: str

    def validate(self) -> None:
        if not self.game_id or not self.relative_path or "\\" in self.relative_path:
            raise ManifestError("manifest entry has invalid game ID or POSIX path")
        for name, value in (("file_sha256", self.file_sha256), ("content_sha256", self.content_sha256)):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ManifestError(f"entry {name} is not a lowercase SHA-256")
        if type(self.bytes) is not int or self.bytes <= 0 or type(self.decisions) is not int or self.decisions <= 0:
            raise ManifestError("entry bytes and decisions must be positive integers")
        if self.purpose not in {"training", "evaluation"} or self.split not in SPLITS:
            raise ManifestError("entry has invalid purpose or split")
        if (self.purpose == "evaluation") != (self.split == "evaluation"):
            raise ManifestError("evaluation purpose and split must match exactly")
        if type(self.seed) is not int or self.seed < 0 or not self.seed_group:
            raise ManifestError("entry seed identity is invalid")
        if len(self.deck_sha256) != 2 or len(self.policy_names) != 2:
            raise ManifestError("entry must identify two decks and policies")
        if self.final_result not in (0, 1, 2):
            raise ManifestError("entry final result is invalid")
        try:
            timestamp = datetime.fromisoformat(self.created_utc)
        except ValueError as exc:
            raise ManifestError("entry timestamp is invalid") from exc
        if timestamp.tzinfo is None:
            raise ManifestError("entry timestamp must include a timezone")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ManifestEntry":
        _strict(
            data,
            {
                "game_id", "relative_path", "file_sha256", "content_sha256", "bytes", "decisions",
                "purpose", "split", "seed", "seed_group", "deck_sha256", "policy_names",
                "final_result", "created_utc",
            },
            "manifest.entry",
        )
        result = cls(
            game_id=data["game_id"], relative_path=data["relative_path"], file_sha256=data["file_sha256"],
            content_sha256=data["content_sha256"], bytes=data["bytes"], decisions=data["decisions"],
            purpose=data["purpose"], split=data["split"], seed=data["seed"], seed_group=data["seed_group"],
            deck_sha256=tuple(data["deck_sha256"]), policy_names=tuple(data["policy_names"]),
            final_result=data["final_result"], created_utc=data["created_utc"],
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class CorpusManifest:
    schema_version: int
    corpus_id: str
    revision: int
    created_utc: str
    previous_manifest_sha256: str | None
    split_policy: SplitPolicy
    entries: tuple[ManifestEntry, ...]

    def validate(self) -> None:
        if self.schema_version != MANIFEST_SCHEMA_VERSION or not self.corpus_id or self.revision < 0:
            raise ManifestError("invalid corpus manifest identity")
        if self.revision == 0 and self.previous_manifest_sha256 is not None:
            raise ManifestError("revision zero cannot have a previous manifest")
        if self.revision > 0 and (
            self.previous_manifest_sha256 is None or len(self.previous_manifest_sha256) != 64
        ):
            raise ManifestError("nonzero revision requires previous manifest SHA-256")
        ids = [entry.game_id for entry in self.entries]
        paths = [entry.relative_path for entry in self.entries]
        if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
            raise ManifestError("manifest contains duplicate game IDs or paths")
        for entry in self.entries:
            entry.validate()
        validate_split_isolation(self.entries)

    @property
    def fingerprint(self) -> str:
        return canonical_json_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CorpusManifest":
        _strict(
            data,
            {
                "schema_version", "corpus_id", "revision", "created_utc",
                "previous_manifest_sha256", "split_policy", "entries",
            },
            "manifest",
        )
        policy = data["split_policy"]
        _strict(
            policy,
            {"train_percent", "validation_percent", "test_percent", "holdout_deck_sha256"},
            "manifest.split_policy",
        )
        result = cls(
            schema_version=data["schema_version"], corpus_id=data["corpus_id"], revision=data["revision"],
            created_utc=data["created_utc"], previous_manifest_sha256=data["previous_manifest_sha256"],
            split_policy=SplitPolicy(
                train_percent=policy["train_percent"], validation_percent=policy["validation_percent"],
                test_percent=policy["test_percent"], holdout_deck_sha256=tuple(policy["holdout_deck_sha256"]),
            ),
            entries=tuple(ManifestEntry.from_dict(item) for item in data["entries"]),
        )
        result.validate()
        return result


def validate_split_isolation(entries: Sequence[ManifestEntry]) -> None:
    seed_splits: dict[str, str] = {}
    game_splits: dict[str, str] = {}
    for entry in entries:
        if entry.game_id in game_splits and game_splits[entry.game_id] != entry.split:
            raise ManifestError(f"game {entry.game_id} crosses dataset splits")
        game_splits[entry.game_id] = entry.split
        if entry.seed_group in seed_splits and seed_splits[entry.seed_group] != entry.split:
            raise ManifestError(f"seed group {entry.seed_group} crosses dataset splits")
        seed_splits[entry.seed_group] = entry.split
        if entry.purpose == "evaluation" and entry.split != "evaluation":
            raise ManifestError("evaluation game leaked into a training split")
