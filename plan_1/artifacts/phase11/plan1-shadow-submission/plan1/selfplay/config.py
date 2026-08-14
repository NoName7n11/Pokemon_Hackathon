from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plan1.model.policy_value import ModelConfig


@dataclass(frozen=True, slots=True)
class ReinforcementConfig:
    schema_version: int
    run_id: str
    iterations: int
    selfplay_games_per_iteration: int
    validation_games_per_iteration: int
    evaluation_games: int
    workers: int
    replay_window_games: int
    root_seed: int
    max_steps: int
    max_candidates: int
    temperature_turns: int
    visit_temperature: float
    promotion_min_win_rate: float
    initial_checkpoint: Path
    bootstrap_corpus: Path
    deck_paths: tuple[Path, ...]
    search_config: Path
    model: ModelConfig

    def validate(self) -> None:
        if self.schema_version != 1 or not self.run_id:
            raise ValueError("invalid reinforcement config identity")
        positive = (
            self.iterations, self.selfplay_games_per_iteration,
            self.validation_games_per_iteration, self.evaluation_games,
            self.workers, self.replay_window_games, self.max_steps, self.max_candidates,
        )
        if any(type(value) is not int or value < 1 for value in positive):
            raise ValueError("reinforcement integer limits must be positive")
        if self.evaluation_games % 2:
            raise ValueError("evaluation_games must be even")
        if self.validation_games_per_iteration >= self.selfplay_games_per_iteration:
            raise ValueError("validation games must be fewer than total self-play games")
        if self.root_seed < 0 or self.temperature_turns < 0 or self.visit_temperature <= 0:
            raise ValueError("invalid seed or exploration settings")
        if not 0.5 <= self.promotion_min_win_rate <= 1.0:
            raise ValueError("promotion_min_win_rate must be in [0.5, 1]")
        if len(self.deck_paths) < 1:
            raise ValueError("at least one self-play deck is required")
        self.model.validate()


def load_reinforcement_config(path: Path) -> ReinforcementConfig:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version", "run_id", "iterations", "selfplay_games_per_iteration",
        "validation_games_per_iteration", "evaluation_games", "workers",
        "replay_window_games", "root_seed", "max_steps", "max_candidates",
        "temperature_turns", "visit_temperature", "promotion_min_win_rate",
        "initial_checkpoint", "bootstrap_corpus", "deck_paths", "search_config", "model",
    }
    if set(data) != expected:
        raise ValueError(f"reinforcement config keys differ: {sorted(set(data) ^ expected)}")
    model_data = data["model"]
    if set(model_data) != set(ModelConfig.__dataclass_fields__):
        raise ValueError("reinforcement model config keys differ")
    root = path.parent.parent.parent.resolve()

    def resolve(value: str) -> Path:
        candidate = Path(value)
        return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()

    result = ReinforcementConfig(
        schema_version=data["schema_version"],
        run_id=data["run_id"],
        iterations=data["iterations"],
        selfplay_games_per_iteration=data["selfplay_games_per_iteration"],
        validation_games_per_iteration=data["validation_games_per_iteration"],
        evaluation_games=data["evaluation_games"],
        workers=data["workers"],
        replay_window_games=data["replay_window_games"],
        root_seed=data["root_seed"],
        max_steps=data["max_steps"],
        max_candidates=data["max_candidates"],
        temperature_turns=data["temperature_turns"],
        visit_temperature=float(data["visit_temperature"]),
        promotion_min_win_rate=float(data["promotion_min_win_rate"]),
        initial_checkpoint=resolve(data["initial_checkpoint"]),
        bootstrap_corpus=resolve(data["bootstrap_corpus"]),
        deck_paths=tuple(resolve(value) for value in data["deck_paths"]),
        search_config=resolve(data["search_config"]),
        model=ModelConfig(**model_data),
    )
    result.validate()
    return result
