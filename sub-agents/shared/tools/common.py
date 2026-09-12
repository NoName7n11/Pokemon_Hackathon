from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
SUB_AGENTS_ROOT = REPO_ROOT / "sub-agents"
SPECIALISTS_ROOT = SUB_AGENTS_ROOT / "specialists"
DATASET_PATH = REPO_ROOT / "data" / "dataset" / "EN_Card_Data.csv"
ENGINE_PARENT = REPO_ROOT / "sample_submission" / "sample_submission"


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "details": self.details,
        }


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temp.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_specialist_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._-")
    if not name:
        raise ValueError("specialist name must contain a letter or number")
    return name


def load_deck_ids(path: Path) -> list[int]:
    ids: list[int] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        value = raw.strip()
        if not value:
            continue
        if not value.isdecimal():
            raise ValueError(f"line {line_number} is not a positive integer card ID: {value!r}")
        ids.append(int(value))
    return ids


def load_card_metadata(path: Path = DATASET_PATH) -> dict[int, dict[str, str]]:
    cards: dict[int, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            card_id = int(row["Card ID"])
            current = cards.get(card_id)
            if current is None:
                cards[card_id] = row
                continue
            stable_fields = (
                "Card Name",
                "Stage (Pokémon)/Type (Energy and Trainer)",
                "Rule",
                "Category",
            )
            if any(current.get(field) != row.get(field) for field in stable_fields):
                raise ValueError(f"dataset contains inconsistent metadata for card ID {card_id}")
    return cards


def validate_deck(deck_path: Path, dataset_path: Path = DATASET_PATH) -> ValidationReport:
    report = ValidationReport(details={"deck_path": str(deck_path)})
    if not deck_path.is_file():
        report.errors.append(f"deck file does not exist: {deck_path}")
        return report
    if not dataset_path.is_file():
        report.errors.append(f"card dataset does not exist: {dataset_path}")
        return report

    try:
        ids = load_deck_ids(deck_path)
    except (OSError, UnicodeError, ValueError) as exc:
        report.errors.append(str(exc))
        return report

    report.details["card_count"] = len(ids)
    report.details["unique_card_ids"] = len(set(ids))
    if len(ids) != 60:
        report.errors.append(f"deck must contain exactly 60 card IDs; found {len(ids)}")

    try:
        cards = load_card_metadata(dataset_path)
    except (OSError, UnicodeError, ValueError, KeyError) as exc:
        report.errors.append(f"could not read card dataset: {exc}")
        return report

    missing = sorted(set(ids) - set(cards))
    if missing:
        report.errors.append(f"card IDs missing from dataset: {missing}")

    known_ids = [card_id for card_id in ids if card_id in cards]
    name_counts = Counter(cards[card_id]["Card Name"] for card_id in known_ids)
    basic_energy_names = {
        cards[card_id]["Card Name"]
        for card_id in known_ids
        if cards[card_id]["Stage (Pokémon)/Type (Energy and Trainer)"] == "Basic Energy"
    }
    over_limit = {name: count for name, count in name_counts.items() if count > 4 and name not in basic_energy_names}
    if over_limit:
        formatted = ", ".join(f"{name} x{count}" for name, count in sorted(over_limit.items()))
        report.errors.append(f"four-copy limit exceeded by card name: {formatted}")

    basic_pokemon = sum(
        1
        for card_id in known_ids
        if cards[card_id]["Stage (Pokémon)/Type (Energy and Trainer)"] == "Basic Pokémon"
    )
    ace_spec = sum(1 for card_id in known_ids if cards[card_id]["Rule"] == "ACE SPEC")
    report.details["basic_pokemon"] = basic_pokemon
    report.details["ace_spec"] = ace_spec
    if basic_pokemon == 0:
        report.errors.append("deck must contain at least one Basic Pokémon")
    if ace_spec > 1:
        report.errors.append(f"deck may contain at most one ACE SPEC card; found {ace_spec}")

    return report


def validate_python_syntax(agent_path: Path) -> ValidationReport:
    report = ValidationReport(details={"agent_path": str(agent_path)})
    if not agent_path.is_file():
        report.errors.append(f"agent file does not exist: {agent_path}")
        return report
    try:
        source = agent_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(agent_path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        report.errors.append(f"agent syntax validation failed: {exc}")
        return report

    functions = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    report.details["top_level_functions"] = sorted(functions)
    for required in ("agent", "read_deck_csv"):
        if required not in functions:
            report.errors.append(f"agent module must define top-level function {required}()")
    return report


def ensure_within(path: Path, parent: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(parent.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes allowed directory {parent}: {resolved}") from exc
    return resolved


def resolve_specialist(value: str | Path) -> Path:
    supplied = Path(value)
    candidate = supplied if supplied.is_absolute() or supplied.exists() else SPECIALISTS_ROOT / supplied
    specialist = ensure_within(candidate, SPECIALISTS_ROOT)
    if not specialist.is_dir():
        raise ValueError(f"specialist directory does not exist: {specialist}")
    return specialist


def copy_pair(source_dir: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=False)
    for filename in ("main.py", "deck.csv"):
        source = source_dir / filename
        if not source.is_file():
            raise ValueError(f"missing specialist file: {source}")
        shutil.copy2(source, destination_dir / filename)


def copy_file_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    shutil.copy2(source, temporary)
    temporary.replace(destination)


def next_experiment_id(specialist: Path) -> str:
    highest = 0
    for path in (specialist / "experiments").glob("EXP-*"):
        match = re.fullmatch(r"EXP-(\d+)", path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"EXP-{highest + 1:04d}"


def next_version(current: str, suffix: str = "candidate") -> str:
    match = re.match(r"v(\d+)", current)
    number = int(match.group(1)) + 1 if match else 1
    return f"v{number:03d}-{suffix}"


def update_registry_specialist(name: str, **changes: Any) -> None:
    registry_path = SUB_AGENTS_ROOT / "registry.json"
    registry = read_json(registry_path)
    for entry in registry.get("specialists", []):
        if entry.get("name") == name:
            entry.update(changes)
            write_json_atomic(registry_path, registry)
            return
    raise ValueError(f"specialist is not registered: {name}")


def normalize_worker_identity(provider: str | None, model: str | None = None) -> str:
    provider_name = (provider or "").strip().lower()
    model_name = (model or "").strip().lower()
    if provider_name == "codex":
        return "codex"
    if provider_name == "claude":
        if "opus" in model_name:
            return "opus"
        if "sonnet" in model_name:
            return "sonnet"
        return "claude"
    if provider_name == "antigravity":
        return "antigravity"
    return provider_name or "unknown"


def assigned_review_identity(worker_identity: str) -> dict[str, str]:
    identity = worker_identity.strip().lower()
    if identity == "codex":
        return {
            "reviewer": "opus",
            "provider": "claude",
            "model": "opus",
            "reason": "Codex-authored experiments require an independent Opus/Claude review.",
        }
    if identity in {"opus", "claude", "sonnet"}:
        return {
            "reviewer": "codex",
            "provider": "codex",
            "model": "gpt-5.5",
            "reason": "Claude/Opus-authored experiments require an independent Codex review.",
        }
    return {
        "reviewer": "codex",
        "provider": "codex",
        "model": "gpt-5.5",
        "reason": "Unmapped worker identities default to Codex review.",
    }
