from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from plan1.game.actions import validate_action
from plan1.game.records import PublicObservationRecord
from plan1.reproducibility import canonical_json_hash


TRAJECTORY_SCHEMA_VERSION = 1


class TrajectoryError(ValueError):
    """Raised when trajectory data violates the immutable schema."""


def _timestamp(value: str, location: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise TrajectoryError(f"{location} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise TrajectoryError(f"{location} must include a timezone")
    return value


def _hash(value: str, location: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise TrajectoryError(f"{location} must be a lowercase SHA-256")
    return value


def _strict(data: Mapping[str, Any], expected: set[str], location: str) -> None:
    missing = expected - data.keys()
    extra = data.keys() - expected
    if missing or extra:
        raise TrajectoryError(f"{location} keys differ; missing={sorted(missing)} extra={sorted(extra)}")


@dataclass(frozen=True, slots=True)
class DeckIdentity:
    name: str
    sha256: str
    card_ids: tuple[int, ...]

    def validate(self) -> None:
        if not self.name:
            raise TrajectoryError("deck name cannot be empty")
        _hash(self.sha256, "deck.sha256")
        if len(self.card_ids) != 60 or any(type(card_id) is not int or card_id <= 0 for card_id in self.card_ids):
            raise TrajectoryError("deck.card_ids must contain 60 positive integers")
        if canonical_json_hash(list(self.card_ids)) != self.sha256:
            raise TrajectoryError("deck SHA-256 does not match card IDs")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DeckIdentity":
        _strict(data, {"name", "sha256", "card_ids"}, "deck")
        result = cls(str(data["name"]), str(data["sha256"]), tuple(data["card_ids"]))
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class PolicyIdentity:
    name: str
    version: str
    checkpoint_sha256: str | None

    def validate(self) -> None:
        if not self.name or not self.version:
            raise TrajectoryError("policy name and version cannot be empty")
        if self.checkpoint_sha256 is not None:
            _hash(self.checkpoint_sha256, "policy.checkpoint_sha256")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PolicyIdentity":
        _strict(data, {"name", "version", "checkpoint_sha256"}, "policy")
        result = cls(str(data["name"]), str(data["version"]), data["checkpoint_sha256"])
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class ActionTarget:
    fingerprint: str
    indices: tuple[int, ...]
    option_mask: tuple[bool, ...]
    visits: int
    prior: float | None
    q_value: float | None

    def validate(self, observation: PublicObservationRecord) -> None:
        _hash(self.fingerprint, "action.fingerprint")
        if observation.selection is None:
            raise TrajectoryError("decision observation has no selection")
        validate_action(observation.selection, self.indices)
        if len(self.option_mask) != len(observation.selection.options):
            raise TrajectoryError("action option mask length differs from selection options")
        selected = set(self.indices)
        if self.option_mask != tuple(index in selected for index in range(len(self.option_mask))):
            raise TrajectoryError("action option mask does not match selected indices")
        ordered = observation.selection.context == 34
        expected_fingerprint = canonical_json_hash(
            {
                "selection": observation.selection.fingerprint,
                "ordered": ordered,
                "selected": [
                    {"index": index, "option": asdict(observation.selection.options[index])}
                    for index in self.indices
                ],
            }
        )
        if self.fingerprint != expected_fingerprint:
            raise TrajectoryError("action fingerprint does not match selection and indices")
        if type(self.visits) is not int or self.visits < 0:
            raise TrajectoryError("action visits must be a non-negative integer")
        if self.prior is not None and not 0.0 <= self.prior <= 1.0:
            raise TrajectoryError("action prior must be in [0, 1]")
        if self.q_value is not None and not -1.0 <= self.q_value <= 1.0:
            raise TrajectoryError("action Q value must be in [-1, 1]")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ActionTarget":
        _strict(data, {"fingerprint", "indices", "option_mask", "visits", "prior", "q_value"}, "action")
        return cls(
            fingerprint=str(data["fingerprint"]),
            indices=tuple(data["indices"]),
            option_mask=tuple(data["option_mask"]),
            visits=data["visits"],
            prior=data["prior"],
            q_value=data["q_value"],
        )


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    schema_version: int
    game_id: str
    decision_index: int
    player: int
    seat: int
    seed: int
    seed_group: str
    timestamp_utc: str
    observation: dict[str, Any]
    observation_sha256: str
    information_set_key: str
    selection_fingerprint: str
    legal_actions: tuple[ActionTarget, ...]
    chosen_action_fingerprint: str
    chosen_indices: tuple[int, ...]
    search: dict[str, Any]
    belief: dict[str, Any]
    acting_policy: PolicyIdentity
    opponent_policy: PolicyIdentity
    deck_sha256: str
    opponent_deck_sha256: str
    final_result: int
    value_target: float
    terminal_reason: str

    def validate(self) -> None:
        if self.schema_version != TRAJECTORY_SCHEMA_VERSION:
            raise TrajectoryError("unsupported decision schema version")
        if not self.game_id or type(self.decision_index) is not int or self.decision_index < 0:
            raise TrajectoryError("invalid decision identity")
        if self.player not in (0, 1) or self.seat not in (0, 1) or self.player != self.seat:
            raise TrajectoryError("decision player/seat must identify seat 0 or 1")
        if type(self.seed) is not int or self.seed < 0 or not self.seed_group:
            raise TrajectoryError("invalid decision seed identity")
        _timestamp(self.timestamp_utc, "decision.timestamp_utc")
        _hash(self.observation_sha256, "decision.observation_sha256")
        _hash(self.information_set_key, "decision.information_set_key")
        _hash(self.selection_fingerprint, "decision.selection_fingerprint")
        _hash(self.deck_sha256, "decision.deck_sha256")
        _hash(self.opponent_deck_sha256, "decision.opponent_deck_sha256")
        if canonical_json_hash(self.observation) != self.observation_sha256:
            raise TrajectoryError("observation checksum mismatch")
        observation = public_observation_from_dict(self.observation)
        if observation.selection is None or observation.selection.fingerprint != self.selection_fingerprint:
            raise TrajectoryError("selection fingerprint mismatch")
        if not self.legal_actions:
            raise TrajectoryError("decision has no legal actions")
        fingerprints = [action.fingerprint for action in self.legal_actions]
        if len(fingerprints) != len(set(fingerprints)):
            raise TrajectoryError("decision contains duplicate action fingerprints")
        for action in self.legal_actions:
            action.validate(observation)
        if self.chosen_action_fingerprint not in fingerprints:
            raise TrajectoryError("chosen action is absent from legal action targets")
        chosen = self.legal_actions[fingerprints.index(self.chosen_action_fingerprint)]
        if chosen.indices != self.chosen_indices:
            raise TrajectoryError("chosen action fingerprint and indices disagree")
        self.acting_policy.validate()
        self.opponent_policy.validate()
        if self.final_result not in (0, 1, 2):
            raise TrajectoryError("final result must be seat 0, seat 1, or draw")
        expected_value = 0.0 if self.final_result == 2 else (1.0 if self.final_result == self.player else -1.0)
        if self.value_target != expected_value:
            raise TrajectoryError("value target does not match final result and acting player")
        if not self.terminal_reason:
            raise TrajectoryError("terminal reason cannot be empty")
        if not isinstance(self.search, dict) or not isinstance(self.belief, dict):
            raise TrajectoryError("search and belief diagnostics must be objects")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DecisionRecord":
        expected = {
            "schema_version", "game_id", "decision_index", "player", "seat", "seed", "seed_group",
            "timestamp_utc", "observation", "observation_sha256", "information_set_key",
            "selection_fingerprint", "legal_actions", "chosen_action_fingerprint", "chosen_indices",
            "search", "belief", "acting_policy", "opponent_policy", "deck_sha256",
            "opponent_deck_sha256", "final_result", "value_target", "terminal_reason",
        }
        _strict(data, expected, "decision")
        normalized_observation = public_observation_from_dict(data["observation"]).to_dict()
        result = cls(
            schema_version=data["schema_version"], game_id=data["game_id"],
            decision_index=data["decision_index"], player=data["player"], seat=data["seat"],
            seed=data["seed"], seed_group=data["seed_group"], timestamp_utc=data["timestamp_utc"],
            observation=normalized_observation, observation_sha256=data["observation_sha256"],
            information_set_key=data["information_set_key"], selection_fingerprint=data["selection_fingerprint"],
            legal_actions=tuple(ActionTarget.from_dict(item) for item in data["legal_actions"]),
            chosen_action_fingerprint=data["chosen_action_fingerprint"], chosen_indices=tuple(data["chosen_indices"]),
            search=dict(data["search"]), belief=dict(data["belief"]),
            acting_policy=PolicyIdentity.from_dict(data["acting_policy"]),
            opponent_policy=PolicyIdentity.from_dict(data["opponent_policy"]),
            deck_sha256=data["deck_sha256"], opponent_deck_sha256=data["opponent_deck_sha256"],
            final_result=data["final_result"], value_target=data["value_target"],
            terminal_reason=data["terminal_reason"],
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class GameTrajectory:
    schema_version: int
    game_id: str
    run_id: str
    purpose: str
    seed: int
    seed_group: str
    created_utc: str
    decks: tuple[DeckIdentity, DeckIdentity]
    policies: tuple[PolicyIdentity, PolicyIdentity]
    decisions: tuple[DecisionRecord, ...]
    final_result: int
    terminal_reason: str
    completed: bool

    def validate(self) -> None:
        if self.schema_version != TRAJECTORY_SCHEMA_VERSION:
            raise TrajectoryError("unsupported game schema version")
        if not self.game_id or not self.run_id or self.purpose not in {"training", "evaluation"}:
            raise TrajectoryError("invalid game identity or purpose")
        if type(self.seed) is not int or self.seed < 0 or not self.seed_group:
            raise TrajectoryError("invalid game seed identity")
        _timestamp(self.created_utc, "game.created_utc")
        if len(self.decks) != 2 or len(self.policies) != 2:
            raise TrajectoryError("game must identify exactly two decks and policies")
        for deck in self.decks:
            deck.validate()
        for policy in self.policies:
            policy.validate()
        if not self.completed or self.final_result not in (0, 1, 2) or not self.terminal_reason:
            raise TrajectoryError("only completed terminal games may be stored")
        if not self.decisions:
            raise TrajectoryError("game trajectory cannot be empty")
        for index, decision in enumerate(self.decisions):
            decision.validate()
            if decision.game_id != self.game_id or decision.decision_index != index:
                raise TrajectoryError("decision sequence identity is not contiguous")
            if decision.seed != self.seed or decision.seed_group != self.seed_group:
                raise TrajectoryError("decision seed identity differs from game")
            if decision.final_result != self.final_result or decision.terminal_reason != self.terminal_reason:
                raise TrajectoryError("decision terminal target differs from game")
            seat = decision.player
            if decision.deck_sha256 != self.decks[seat].sha256:
                raise TrajectoryError("decision deck identity differs from game")
            if decision.opponent_deck_sha256 != self.decks[1 - seat].sha256:
                raise TrajectoryError("decision opponent deck identity differs from game")
            if decision.acting_policy != self.policies[seat] or decision.opponent_policy != self.policies[1 - seat]:
                raise TrajectoryError("decision policy identity differs from game")

    @property
    def fingerprint(self) -> str:
        return canonical_json_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GameTrajectory":
        expected = {
            "schema_version", "game_id", "run_id", "purpose", "seed", "seed_group", "created_utc",
            "decks", "policies", "decisions", "final_result", "terminal_reason", "completed",
        }
        _strict(data, expected, "game")
        result = cls(
            schema_version=data["schema_version"], game_id=data["game_id"], run_id=data["run_id"],
            purpose=data["purpose"], seed=data["seed"], seed_group=data["seed_group"],
            created_utc=data["created_utc"], decks=tuple(DeckIdentity.from_dict(item) for item in data["decks"]),
            policies=tuple(PolicyIdentity.from_dict(item) for item in data["policies"]),
            decisions=tuple(DecisionRecord.from_dict(item) for item in data["decisions"]),
            final_result=data["final_result"], terminal_reason=data["terminal_reason"], completed=data["completed"],
        )
        result.validate()
        return result


def public_observation_from_dict(data: Mapping[str, Any]) -> PublicObservationRecord:
    """Reconstruct the immutable public record without accepting extra fields."""
    from plan1.game.records import CardRecord, LogRecord, OptionRecord, PlayerRecord, PokemonRecord, SelectionRecord, StateRecord

    _strict(data, {"schema_version", "selection", "logs", "state"}, "observation")

    def card(item: Mapping[str, Any]) -> CardRecord:
        _strict(item, {"card_id", "serial", "player_index"}, "observation.card")
        return CardRecord(**item)

    def pokemon(item: Mapping[str, Any]) -> PokemonRecord:
        _strict(
            item,
            {"card_id", "serial", "hp", "max_hp", "appear_this_turn", "energies", "energy_cards", "tools", "pre_evolution"},
            "observation.pokemon",
        )
        return PokemonRecord(
            card_id=item["card_id"], serial=item["serial"], hp=item["hp"], max_hp=item["max_hp"],
            appear_this_turn=item["appear_this_turn"], energies=tuple(item["energies"]),
            energy_cards=tuple(card(v) for v in item["energy_cards"]), tools=tuple(card(v) for v in item["tools"]),
            pre_evolution=tuple(card(v) for v in item["pre_evolution"]),
        )

    def player(item: Mapping[str, Any]) -> PlayerRecord:
        _strict(
            item,
            {"active", "bench", "bench_max", "deck_count", "discard", "prize", "hand_count", "hand", "poisoned", "burned", "asleep", "paralyzed", "confused"},
            "observation.player",
        )
        return PlayerRecord(
            active=tuple(None if v is None else pokemon(v) for v in item["active"]),
            bench=tuple(pokemon(v) for v in item["bench"]), bench_max=item["bench_max"], deck_count=item["deck_count"],
            discard=tuple(card(v) for v in item["discard"]),
            prize=tuple(None if v is None else card(v) for v in item["prize"]), hand_count=item["hand_count"],
            hand=None if item["hand"] is None else tuple(card(v) for v in item["hand"]), poisoned=item["poisoned"],
            burned=item["burned"], asleep=item["asleep"], paralyzed=item["paralyzed"], confused=item["confused"],
        )

    selection_data = data["selection"]
    if selection_data is not None:
        _strict(
            selection_data,
            {"select_type", "context", "min_count", "max_count", "remain_damage_counter", "remain_energy_cost", "options", "deck", "context_card", "effect"},
            "observation.selection",
        )
        for item in selection_data["options"]:
            _strict(
                item,
                {"option_type", "number", "area", "index", "player_index", "tool_index", "energy_index", "count", "in_play_area", "in_play_index", "attack_id", "card_id", "serial", "special_condition_type"},
                "observation.option",
            )
    selection = None if selection_data is None else SelectionRecord(
        select_type=selection_data["select_type"], context=selection_data["context"],
        min_count=selection_data["min_count"], max_count=selection_data["max_count"],
        remain_damage_counter=selection_data["remain_damage_counter"], remain_energy_cost=selection_data["remain_energy_cost"],
        options=tuple(OptionRecord(**item) for item in selection_data["options"]),
        deck=None if selection_data["deck"] is None else tuple(card(v) for v in selection_data["deck"]),
        context_card=None if selection_data["context_card"] is None else card(selection_data["context_card"]),
        effect=None if selection_data["effect"] is None else card(selection_data["effect"]),
    )
    state_data = data["state"]
    if state_data is not None:
        _strict(
            state_data,
            {"turn", "turn_action_count", "acting_player", "first_player", "supporter_played", "stadium_played", "energy_attached", "retreated", "result", "stadium", "looking", "players"},
            "observation.state",
        )
    for item in data["logs"]:
        _strict(item, {"log_type", "attributes"}, "observation.log")
    state = None if state_data is None else StateRecord(
        turn=state_data["turn"], turn_action_count=state_data["turn_action_count"],
        acting_player=state_data["acting_player"], first_player=state_data["first_player"],
        supporter_played=state_data["supporter_played"], stadium_played=state_data["stadium_played"],
        energy_attached=state_data["energy_attached"], retreated=state_data["retreated"], result=state_data["result"],
        stadium=tuple(card(v) for v in state_data["stadium"]),
        looking=None if state_data["looking"] is None else tuple(None if v is None else card(v) for v in state_data["looking"]),
        players=tuple(player(v) for v in state_data["players"]),
    )
    return PublicObservationRecord(
        schema_version=data["schema_version"], selection=selection,
        logs=tuple(LogRecord(log_type=item["log_type"], attributes=tuple(tuple(v) for v in item["attributes"])) for item in data["logs"]),
        state=state,
    )
