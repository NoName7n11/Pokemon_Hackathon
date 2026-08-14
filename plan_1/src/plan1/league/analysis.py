from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable

from plan1.league.config import LeagueConfig


def wilson_interval(wins: int, total: int, z: float = 1.96) -> list[float] | None:
    if total == 0:
        return None
    rate = wins / total
    denominator = 1.0 + z * z / total
    center = (rate + z * z / (2.0 * total)) / denominator
    half = z * math.sqrt((rate * (1.0 - rate) + z * z / (4.0 * total)) / total) / denominator
    return [center - half, center + half]


def _perspective(match: dict[str, Any], policy: str) -> tuple[int, int, int]:
    if match["left_policy"] == policy:
        return match["left_wins"], match["right_wins"], match["draws"]
    if match["right_policy"] == policy:
        return match["right_wins"], match["left_wins"], match["draws"]
    raise ValueError(f"policy {policy} is absent from matchup {match['matchup_id']}")


def _summary(matches: Iterable[dict[str, Any]], policy: str) -> dict[str, Any]:
    wins = losses = draws = games = 0
    matchup_ids = []
    for match in matches:
        won, lost, tied = _perspective(match, policy)
        wins += won
        losses += lost
        draws += tied
        games += match["games"]
        matchup_ids.append(match["matchup_id"])
    decisive = wins + losses
    interval = wilson_interval(wins, decisive)
    return {
        "policy": policy,
        "matchups": len(matchup_ids),
        "matchup_ids": matchup_ids,
        "games": games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "decisive_games": decisive,
        "decisive_win_rate": wins / decisive if decisive else None,
        "wilson_95": interval,
    }


def _canonical_cycle(cycle: tuple[str, ...]) -> tuple[str, ...]:
    rotations = [cycle[index:] + cycle[:index] for index in range(len(cycle))]
    return min(rotations)


def dominance_cycles(
    matches: Iterable[dict[str, Any]],
    checkpoint_names: set[str],
    *,
    minimum_rate: float,
    minimum_games: int,
) -> dict[str, Any]:
    pair_totals: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for match in matches:
        left = match["left_policy"]
        right = match["right_policy"]
        if left not in checkpoint_names or right not in checkpoint_names:
            continue
        key = tuple(sorted((left, right)))
        if left == key[0]:
            pair_totals[key][0] += match["left_wins"]
            pair_totals[key][1] += match["right_wins"]
        else:
            pair_totals[key][0] += match["right_wins"]
            pair_totals[key][1] += match["left_wins"]
    edges: dict[str, set[str]] = defaultdict(set)
    evidence = []
    for (first, second), (first_wins, second_wins) in sorted(pair_totals.items()):
        decisive = first_wins + second_wins
        winner = loser = None
        rate = None
        if decisive >= minimum_games:
            first_rate = first_wins / decisive
            if first_rate >= minimum_rate:
                winner, loser, rate = first, second, first_rate
            elif 1.0 - first_rate >= minimum_rate:
                winner, loser, rate = second, first, 1.0 - first_rate
        if winner is not None:
            edges[winner].add(loser)
        evidence.append({
            "first": first, "second": second, "first_wins": first_wins,
            "second_wins": second_wins, "decisive_games": decisive,
            "dominant_policy": winner, "dominant_win_rate": rate,
        })
    cycles: set[tuple[str, ...]] = set()

    def visit(start: str, current: str, path: tuple[str, ...]) -> None:
        for neighbor in edges.get(current, set()):
            if neighbor == start and len(path) >= 3:
                cycles.add(_canonical_cycle(path))
            elif neighbor not in path and len(path) < len(checkpoint_names):
                visit(start, neighbor, path + (neighbor,))

    for node in sorted(checkpoint_names):
        visit(node, node, (node,))
    return {
        "minimum_rate": minimum_rate,
        "minimum_games": minimum_games,
        "edges": {key: sorted(value) for key, value in sorted(edges.items())},
        "pair_evidence": evidence,
        "cycles": [list(cycle) for cycle in sorted(cycles)],
        "cyclic_dominance_detected": bool(cycles),
    }


def analyze_league(config: LeagueConfig, matches: list[dict[str, Any]]) -> dict[str, Any]:
    candidate = next(policy.name for policy in config.policies if policy.role == "candidate")
    checkpoint_names = {policy.name for policy in config.policies if policy.kind == "checkpoint"}
    candidate_matches = [
        match for match in matches
        if candidate in {match["left_policy"], match["right_policy"]}
    ]
    by_split = {
        split: _summary((match for match in candidate_matches if match["split"] == split), candidate)
        for split in ("development", "heldout")
    }
    per_matchup = []
    for match in candidate_matches:
        item = _summary((match,), candidate)
        item.update({
            key: match[key]
            for key in (
                "matchup_id", "category", "split", "left_policy", "right_policy",
                "left_deck", "right_deck",
            )
        })
        per_matchup.append(item)
    by_category = {
        category: _summary(
            (match for match in candidate_matches if match["category"] == category),
            candidate,
        )
        for category in sorted({match["category"] for match in candidate_matches})
    }
    by_candidate_deck = {}
    for deck in config.decks:
        relevant = []
        for match in candidate_matches:
            candidate_deck = (
                match["left_deck"]
                if match["left_policy"] == candidate
                else match["right_deck"]
            )
            if candidate_deck == deck.name:
                relevant.append(match)
        by_candidate_deck[deck.name] = _summary(relevant, candidate)
        by_candidate_deck[deck.name]["split"] = deck.split
    historical_names = {
        policy.name for policy in config.policies
        if policy.role in {"historical", "league_member"}
    }
    forgetting = []
    for opponent in sorted(historical_names):
        for deck in (deck for deck in config.decks if deck.split == "development"):
            relevant = [
                match for match in candidate_matches
                if opponent in {match["left_policy"], match["right_policy"]}
                and match["left_deck"] == deck.name
                and match["right_deck"] == deck.name
            ]
            item = _summary(relevant, candidate)
            item["opponent"] = opponent
            item["deck"] = deck.name
            item["passed_evidence"] = item["decisive_games"] >= config.gates.minimum_matchup_decisive_games
            item["passed_floor"] = bool(
                item["decisive_win_rate"] is not None
                and item["decisive_win_rate"] >= config.gates.forgetting_win_rate_floor
            )
            forgetting.append(item)
    development = by_split["development"]
    heldout = by_split["heldout"]
    aggregate_evidence_sufficient = bool(
        development["decisive_games"] >= config.gates.minimum_aggregate_decisive_games
        and heldout["decisive_games"] >= config.gates.minimum_aggregate_decisive_games
    )
    matchup_evidence_sufficient = bool(
        per_matchup
        and all(
            item["decisive_games"] >= config.gates.minimum_matchup_decisive_games
            for item in per_matchup
        )
    )
    evidence_sufficient = aggregate_evidence_sufficient and matchup_evidence_sufficient
    development_lower = development["wilson_95"][0] if development["wilson_95"] else None
    heldout_lower = heldout["wilson_95"][0] if heldout["wilson_95"] else None
    worst_rate = min(
        (item["decisive_win_rate"] for item in per_matchup if item["decisive_win_rate"] is not None),
        default=None,
    )
    safety_passed = all(not match["faults"] and not match["errors"] for match in matches)
    forgetting_passed = bool(forgetting) and all(
        item["passed_evidence"] and item["passed_floor"] for item in forgetting
    )
    development_strength_passed = bool(
        development_lower is not None
        and development_lower >= config.gates.development_wilson_lower
    )
    heldout_strength_passed = bool(
        heldout_lower is not None
        and heldout_lower >= config.gates.heldout_wilson_lower
    )
    worst_matchup_passed = bool(
        worst_rate is not None
        and worst_rate >= config.gates.worst_matchup_win_rate
    )
    strength_passed = (
        development_strength_passed
        and heldout_strength_passed
        and worst_matchup_passed
    )
    promoted = safety_passed and evidence_sufficient and forgetting_passed and strength_passed
    cycles = dominance_cycles(
        matches,
        checkpoint_names,
        minimum_rate=config.gates.dominance_win_rate,
        minimum_games=config.gates.dominance_minimum_games,
    )
    checkpoint_table = {
        policy: _summary(
            (
                match for match in matches
                if match["left_policy"] in checkpoint_names
                and match["right_policy"] in checkpoint_names
                and policy in {match["left_policy"], match["right_policy"]}
            ),
            policy,
        )
        for policy in sorted(checkpoint_names)
    }
    conclusive_strength_rejection = bool(
        safety_passed
        and aggregate_evidence_sufficient
        and (not development_strength_passed or not heldout_strength_passed)
    )
    if promoted:
        decision = "promoted"
    elif conclusive_strength_rejection or not safety_passed:
        decision = "rejected"
    else:
        decision = "insufficient_evidence"
    return {
        "candidate": candidate,
        "candidate_by_split": by_split,
        "candidate_by_category": by_category,
        "candidate_by_deck": by_candidate_deck,
        "candidate_per_matchup": per_matchup,
        "checkpoint_table": checkpoint_table,
        "catastrophic_forgetting": {
            "floor": config.gates.forgetting_win_rate_floor,
            "comparisons": forgetting,
            "passed": forgetting_passed,
        },
        "cyclic_dominance": cycles,
        "gate": {
            "rule": "safety && sufficient_evidence && multi_deck_strength && no_forgetting",
            "safety_passed": safety_passed,
            "aggregate_evidence_sufficient": aggregate_evidence_sufficient,
            "matchup_evidence_sufficient": matchup_evidence_sufficient,
            "evidence_sufficient": evidence_sufficient,
            "strength_passed": strength_passed,
            "development_strength_passed": development_strength_passed,
            "heldout_strength_passed": heldout_strength_passed,
            "worst_matchup_passed": worst_matchup_passed,
            "forgetting_passed": forgetting_passed,
            "conclusive_strength_rejection": conclusive_strength_rejection,
            "development_wilson_lower": development_lower,
            "heldout_wilson_lower": heldout_lower,
            "worst_matchup_win_rate": worst_rate,
            "decision": decision,
            "promoted": promoted,
        },
    }
