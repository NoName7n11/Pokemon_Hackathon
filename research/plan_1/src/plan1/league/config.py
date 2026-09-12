from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class DeckSpec:
    name: str
    path: Path
    split: str


@dataclass(frozen=True, slots=True)
class PolicySpec:
    name: str
    kind: str
    path: Path
    role: str
    preferred_deck: str | None


@dataclass(frozen=True, slots=True)
class GateConfig:
    minimum_aggregate_decisive_games: int
    minimum_matchup_decisive_games: int
    development_wilson_lower: float
    heldout_wilson_lower: float
    worst_matchup_win_rate: float
    forgetting_win_rate_floor: float
    dominance_win_rate: float
    dominance_minimum_games: int


@dataclass(frozen=True, slots=True)
class LeagueConfig:
    schema_version: int
    run_id: str
    games_per_matchup: int
    max_steps: int
    search_config: Path
    decks: tuple[DeckSpec, ...]
    policies: tuple[PolicySpec, ...]
    gates: GateConfig

    def validate(self) -> None:
        if self.schema_version != 1 or not self.run_id:
            raise ValueError("invalid league config identity")
        if self.games_per_matchup < 2 or self.games_per_matchup % 2:
            raise ValueError("games_per_matchup must be a positive even number")
        if self.max_steps < 1:
            raise ValueError("max_steps must be positive")
        deck_names = [deck.name for deck in self.decks]
        policy_names = [policy.name for policy in self.policies]
        if len(deck_names) != len(set(deck_names)) or len(policy_names) != len(set(policy_names)):
            raise ValueError("league deck and policy names must be unique")
        if {deck.split for deck in self.decks} != {"development", "heldout"}:
            raise ValueError("league requires both development and heldout decks")
        if sum(policy.role == "candidate" for policy in self.policies) != 1:
            raise ValueError("league requires exactly one candidate policy")
        checkpoints = [policy for policy in self.policies if policy.kind == "checkpoint"]
        specialists = [policy for policy in self.policies if policy.kind == "module"]
        if len(checkpoints) < 3:
            raise ValueError("league requires at least three checkpoint policies")
        if not specialists:
            raise ValueError("league requires Plan 2 or generic module opponents")
        if any(policy.kind not in {"checkpoint", "module"} for policy in self.policies):
            raise ValueError("unknown league policy kind")
        if any(policy.role not in {"candidate", "historical", "league_member", "specialist"} for policy in self.policies):
            raise ValueError("unknown league policy role")
        known_decks = set(deck_names)
        if any(
            policy.kind == "module" and policy.preferred_deck not in known_decks
            for policy in self.policies
        ):
            raise ValueError("every module policy must name a preferred league deck")
        for path in (self.search_config, *(deck.path for deck in self.decks), *(policy.path for policy in self.policies)):
            if not path.is_file():
                raise FileNotFoundError(path)
        gate = self.gates
        if gate.minimum_aggregate_decisive_games < 1 or gate.minimum_matchup_decisive_games < 1:
            raise ValueError("league evidence minimums must be positive")
        if gate.dominance_minimum_games < 1:
            raise ValueError("dominance_minimum_games must be positive")
        rates = (
            gate.development_wilson_lower,
            gate.heldout_wilson_lower,
            gate.worst_matchup_win_rate,
            gate.forgetting_win_rate_floor,
            gate.dominance_win_rate,
        )
        if any(not 0.0 <= value <= 1.0 for value in rates):
            raise ValueError("league gate rates must be in [0, 1]")


def load_league_config(path: Path) -> LeagueConfig:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version", "run_id", "games_per_matchup", "max_steps",
        "search_config", "decks", "policies", "gates",
    }
    if set(data) != expected:
        raise ValueError(f"league config keys differ: {sorted(set(data) ^ expected)}")
    root = path.resolve().parents[3]

    def resolve(value: str) -> Path:
        candidate = Path(value)
        return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()

    deck_keys = {"name", "path", "split"}
    policy_keys = {"name", "kind", "path", "role", "preferred_deck"}
    if any(set(item) != deck_keys for item in data["decks"]):
        raise ValueError("league deck config keys differ")
    if any(set(item) != policy_keys for item in data["policies"]):
        raise ValueError("league policy config keys differ")
    if set(data["gates"]) != set(GateConfig.__dataclass_fields__):
        raise ValueError("league gate config keys differ")
    config = LeagueConfig(
        schema_version=data["schema_version"],
        run_id=data["run_id"],
        games_per_matchup=data["games_per_matchup"],
        max_steps=data["max_steps"],
        search_config=resolve(data["search_config"]),
        decks=tuple(
            DeckSpec(item["name"], resolve(item["path"]), item["split"])
            for item in data["decks"]
        ),
        policies=tuple(
            PolicySpec(
                item["name"], item["kind"], resolve(item["path"]),
                item["role"], item["preferred_deck"],
            )
            for item in data["policies"]
        ),
        gates=GateConfig(**data["gates"]),
    )
    config.validate()
    return config
