from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import ENGINE_PARENT, load_deck_ids, write_json_atomic


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Python module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "agent", None)):
        raise ValueError(f"{path} does not define callable agent()")
    return module


def enum_name(value: Any, enum_type=None) -> str:
    if enum_type is not None:
        try:
            return enum_type(value).name
        except (TypeError, ValueError):
            pass
    return getattr(value, "name", str(value))


def safe_choice(agent_module, observation: dict[str, Any], deck_ids: list[int]) -> list[int]:
    agent_module._MY_DECK = deck_ids
    choice = agent_module.agent(observation)
    if not isinstance(choice, list) or any(not isinstance(index, int) for index in choice):
        raise ValueError(f"agent returned non-integer-list choice: {choice!r}")
    return choice


def card_name(card_id: int | None, cards: dict[int, Any]) -> str | None:
    if card_id is None:
        return None
    card = cards.get(card_id)
    return getattr(card, "name", None) or f"card#{card_id}"


def pokemon_summary(pokemon, cards: dict[int, Any]) -> dict[str, Any] | None:
    if pokemon is None:
        return None
    return {
        "card_id": pokemon.id,
        "name": card_name(pokemon.id, cards),
        "hp": pokemon.hp,
        "max_hp": pokemon.maxHp,
        "energy_count": len(pokemon.energies),
        "tool_count": len(pokemon.tools),
    }


def board_summary(state, cards: dict[int, Any]) -> dict[str, Any] | None:
    if state is None:
        return None
    players = []
    for player in state.players:
        players.append(
            {
                "active": pokemon_summary(player.active[0], cards) if player.active else None,
                "bench": [pokemon_summary(pokemon, cards) for pokemon in player.bench],
                "hand_count": player.handCount,
                "deck_count": player.deckCount,
                "prizes_left": len(player.prize),
            }
        )
    return {
        "turn": state.turn,
        "turn_action_count": state.turnActionCount,
        "acting_player": state.yourIndex,
        "first_player": state.firstPlayer,
        "supporter_played": state.supporterPlayed,
        "energy_attached": state.energyAttached,
        "retreated": state.retreated,
        "players": players,
    }


def option_summary(
    option,
    cards: dict[int, Any],
    attacks: dict[int, Any],
    option_type,
    area_type,
    special_condition_type,
) -> dict[str, Any]:
    result = {"type": enum_name(option.type, option_type)}
    fields = (
        "number", "area", "index", "playerIndex", "toolIndex", "energyIndex",
        "count", "inPlayArea", "inPlayIndex", "attackId", "cardId", "serial",
        "specialConditionType",
    )
    for field in fields:
        value = getattr(option, field, None)
        if value is None:
            continue
        if field in {"area", "inPlayArea"}:
            result[field] = enum_name(value, area_type)
        elif field == "specialConditionType":
            result[field] = enum_name(value, special_condition_type)
        else:
            result[field] = value
    if option.cardId is not None:
        result["card_name"] = card_name(option.cardId, cards)
    if option.attackId is not None:
        attack = attacks.get(option.attackId)
        result["attack_name"] = getattr(attack, "name", None) or f"attack#{option.attackId}"
        result["printed_damage"] = getattr(attack, "damage", None)
    return result


def selected_options(options: list[dict[str, Any]], choice: list[int]) -> list[dict[str, Any]]:
    return [options[index] for index in choice if 0 <= index < len(options)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect bounded candidate-versus-baseline policy differences.")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--deck", required=True, type=Path)
    parser.add_argument("--specialist", required=True)
    parser.add_argument("--candidate-version", required=True)
    parser.add_argument("--baseline-version", required=True)
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=3000)
    parser.add_argument("--max-records", type=int, default=200)
    parser.add_argument("--max-options", type=int, default=40)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if min(args.games, args.max_steps, args.max_records, args.max_options) <= 0:
        raise ValueError("games and trace limits must be positive")
    sys.path.insert(0, str(ENGINE_PARENT))
    from cg.api import (
        AreaType,
        OptionType,
        SelectContext,
        SelectType,
        SpecialConditionType,
        all_attack,
        all_card_data,
        to_observation_class,
    )
    from cg.game import battle_finish, battle_select, battle_start

    cards = {card.cardId: card for card in all_card_data()}
    attacks = {attack.attackId: attack for attack in all_attack()}
    candidate = load_module("trace_candidate", args.candidate.resolve())
    baseline_shadow = load_module("trace_baseline_shadow", args.baseline.resolve())
    baseline_opponent = load_module("trace_baseline_opponent", args.baseline.resolve())
    deck_ids = load_deck_ids(args.deck.resolve())
    random.seed(args.seed)
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    contexts: Counter[str] = Counter()
    select_types: Counter[str] = Counter()
    candidate_option_types: Counter[str] = Counter()
    baseline_option_types: Counter[str] = Counter()
    games_with_difference = 0
    candidate_wins = 0
    baseline_opponent_wins = 0
    draws = 0
    total_candidate_decisions = 0

    for game_index in range(args.games):
        candidate_seat = game_index % 2
        seat_modules = [candidate, baseline_opponent] if candidate_seat == 0 else [baseline_opponent, candidate]
        observation, start_data = battle_start(deck_ids, deck_ids)
        if observation is None:
            errors.append(f"game {game_index + 1}: battle_start failed: {start_data}")
            continue
        game_differed = False
        try:
            for step in range(args.max_steps):
                parsed = to_observation_class(observation)
                if parsed.current is not None and parsed.current.result != -1:
                    if parsed.current.result == candidate_seat:
                        candidate_wins += 1
                    elif parsed.current.result in (0, 1):
                        baseline_opponent_wins += 1
                    else:
                        draws += 1
                    break
                acting_seat = parsed.current.yourIndex if parsed.current else 0
                actual_module = seat_modules[acting_seat]
                try:
                    actual_choice = safe_choice(actual_module, observation, deck_ids)
                    if acting_seat == candidate_seat and parsed.select is not None:
                        total_candidate_decisions += 1
                        shadow_choice = safe_choice(baseline_shadow, observation, deck_ids)
                        if actual_choice != shadow_choice:
                            game_differed = True
                            selection = parsed.select
                            context = enum_name(selection.context, SelectContext)
                            select_type = enum_name(selection.type, SelectType)
                            contexts[context] += 1
                            select_types[select_type] += 1
                            options = [
                                option_summary(
                                    option,
                                    cards,
                                    attacks,
                                    OptionType,
                                    AreaType,
                                    SpecialConditionType,
                                )
                                for option in selection.option
                            ]
                            for option in selected_options(options, actual_choice):
                                candidate_option_types[option["type"]] += 1
                            for option in selected_options(options, shadow_choice):
                                baseline_option_types[option["type"]] += 1
                            if len(records) < args.max_records:
                                records.append(
                                    {
                                        "game": game_index + 1,
                                        "step": step,
                                        "candidate_seat": candidate_seat,
                                        "select_type": select_type,
                                        "context": context,
                                        "min_count": selection.minCount,
                                        "max_count": selection.maxCount,
                                        "option_count": len(options),
                                        "options_truncated": len(options) > args.max_options,
                                        "options": options[: args.max_options],
                                        "candidate_choice": actual_choice,
                                        "candidate_selected": selected_options(options, actual_choice),
                                        "baseline_choice": shadow_choice,
                                        "baseline_selected": selected_options(options, shadow_choice),
                                        "board": board_summary(parsed.current, cards),
                                    }
                                )
                    observation = battle_select(actual_choice)
                except Exception as exc:
                    errors.append(f"game {game_index + 1}, step {step}, seat {acting_seat}: {type(exc).__name__}: {exc}")
                    break
            else:
                draws += 1
        finally:
            battle_finish()
        if game_differed:
            games_with_difference += 1

    total_differences = sum(contexts.values())
    result = {
        "schema_version": 1,
        "specialist": args.specialist,
        "candidate_version": args.candidate_version,
        "baseline_version": args.baseline_version,
        "seed": args.seed,
        "created_at": utc_now(),
        "games": args.games,
        "records": records,
        "summary": {
            "candidate_decisions": total_candidate_decisions,
            "total_differences": total_differences,
            "difference_rate": total_differences / total_candidate_decisions if total_candidate_decisions else 0.0,
            "games_with_difference": games_with_difference,
            "contexts": dict(contexts.most_common()),
            "select_types": dict(select_types.most_common()),
            "candidate_selected_option_types": dict(candidate_option_types.most_common()),
            "baseline_selected_option_types": dict(baseline_option_types.most_common()),
            "candidate_wins": candidate_wins,
            "baseline_opponent_wins": baseline_opponent_wins,
            "draws_or_timeouts": draws,
            "records_retained": len(records),
            "records_truncated": total_differences > len(records),
        },
        "limits": {
            "max_steps_per_game": args.max_steps,
            "max_records": args.max_records,
            "max_options_per_record": args.max_options,
        },
        "errors": errors[:20],
    }
    write_json_atomic(args.output.resolve(), result)
    print(json.dumps(result["summary"], indent=2, ensure_ascii=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
