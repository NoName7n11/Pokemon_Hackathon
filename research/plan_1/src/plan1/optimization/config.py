from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SearchVariant:
    name: str
    config_path: Path


@dataclass(frozen=True, slots=True)
class SearchGates:
    baseline_name: str
    minimum_decisive_games: int
    minimum_baseline_win_rate: float
    minimum_nonfallback_rate: float
    maximum_hard_overrun_rate: float
    maximum_match_p95_ms: float


@dataclass(frozen=True, slots=True)
class ModelAblation:
    corpus_root: Path
    dimensions: tuple[int, ...]
    epochs: int
    value_epochs: int
    learning_rate: float
    value_learning_rate: float
    l2: float
    seed: int
    maximum_policy_loss_ratio: float
    maximum_value_brier_ratio: float


@dataclass(frozen=True, slots=True)
class OptimizationConfig:
    schema_version: int
    run_id: str
    checkpoint: Path
    deck_paths: tuple[Path, ...]
    search_variants: tuple[SearchVariant, ...]
    games_per_pair: int
    max_steps: int
    search_gates: SearchGates
    model_ablation: ModelAblation

    def validate(self) -> None:
        if self.schema_version != 1 or not self.run_id:
            raise ValueError("invalid optimization config identity")
        if self.games_per_pair < 2 or self.games_per_pair % 2:
            raise ValueError("games_per_pair must be a positive even integer")
        if self.max_steps < 1 or len(self.deck_paths) < 2:
            raise ValueError("optimization requires positive max_steps and multiple decks")
        names = [variant.name for variant in self.search_variants]
        if len(names) < 2 or len(names) != len(set(names)):
            raise ValueError("optimization requires at least two uniquely named search variants")
        if self.search_gates.baseline_name not in names:
            raise ValueError("search baseline_name is not a configured variant")
        for path in (
            self.checkpoint,
            self.model_ablation.corpus_root / "CURRENT.json",
            *self.deck_paths,
            *(variant.config_path for variant in self.search_variants),
        ):
            if not path.is_file():
                raise FileNotFoundError(path)
        gates = self.search_gates
        if gates.minimum_decisive_games < 1 or gates.maximum_match_p95_ms <= 0:
            raise ValueError("invalid search evidence or latency gate")
        rates = (
            gates.minimum_baseline_win_rate,
            gates.minimum_nonfallback_rate,
            gates.maximum_hard_overrun_rate,
        )
        if any(not 0.0 <= value <= 1.0 for value in rates):
            raise ValueError("search gate rates must be in [0, 1]")
        model = self.model_ablation
        if len(model.dimensions) < 2 or len(model.dimensions) != len(set(model.dimensions)):
            raise ValueError("model ablation dimensions must be unique")
        if any(value < 128 or value & (value - 1) for value in model.dimensions):
            raise ValueError("model dimensions must be powers of two >= 128")
        if model.epochs < 1 or model.value_epochs < 1 or model.value_epochs > model.epochs:
            raise ValueError("invalid model epoch configuration")
        if model.learning_rate <= 0 or model.value_learning_rate <= 0 or model.l2 < 0:
            raise ValueError("invalid model learning rates")
        if model.seed < 0 or model.maximum_policy_loss_ratio < 1.0 or model.maximum_value_brier_ratio < 1.0:
            raise ValueError("invalid model seed or quality ratio")


def load_optimization_config(path: Path) -> OptimizationConfig:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version", "run_id", "checkpoint", "deck_paths",
        "search_variants", "games_per_pair", "max_steps", "search_gates",
        "model_ablation",
    }
    if set(data) != expected:
        raise ValueError(f"optimization config keys differ: {sorted(set(data) ^ expected)}")
    variant_keys = {"name", "config_path"}
    if any(set(item) != variant_keys for item in data["search_variants"]):
        raise ValueError("search variant config keys differ")
    if set(data["search_gates"]) != set(SearchGates.__dataclass_fields__):
        raise ValueError("search gate config keys differ")
    if set(data["model_ablation"]) != set(ModelAblation.__dataclass_fields__):
        raise ValueError("model ablation config keys differ")
    root = path.resolve().parents[3]

    def resolve(value: str) -> Path:
        candidate = Path(value)
        return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()

    model = dict(data["model_ablation"])
    model["corpus_root"] = resolve(model["corpus_root"])
    model["dimensions"] = tuple(model["dimensions"])
    config = OptimizationConfig(
        schema_version=data["schema_version"],
        run_id=data["run_id"],
        checkpoint=resolve(data["checkpoint"]),
        deck_paths=tuple(resolve(value) for value in data["deck_paths"]),
        search_variants=tuple(
            SearchVariant(item["name"], resolve(item["config_path"]))
            for item in data["search_variants"]
        ),
        games_per_pair=data["games_per_pair"],
        max_steps=data["max_steps"],
        search_gates=SearchGates(**data["search_gates"]),
        model_ablation=ModelAblation(**model),
    )
    config.validate()
    return config
