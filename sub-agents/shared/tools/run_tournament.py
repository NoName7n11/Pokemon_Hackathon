from __future__ import annotations

import argparse
import itertools
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import (
    REPO_ROOT,
    SUB_AGENTS_ROOT,
    read_json,
    sha256_file,
    validate_deck,
    validate_python_syntax,
    write_json_atomic,
)


TOURNAMENT_ROOT = SUB_AGENTS_ROOT / "tournaments"
CONFIG_PATH = TOURNAMENT_ROOT / "tournament_config.json"
HISTORY_PATH = TOURNAMENT_ROOT / "REPORT.md"
HISTORY_LOCK_PATH = TOURNAMENT_ROOT / ".report.lock"
MATCHUP_RUNNER = Path(__file__).with_name("matchup_pair.py")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("T-%Y%m%d-%H%M%S-%f")


def relative_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def select_entrants(names: list[str] | None, config: dict[str, Any]) -> list[dict[str, Any]]:
    registry = read_json(SUB_AGENTS_ROOT / "registry.json")
    entries = registry.get("specialists", [])
    by_name = {entry["name"]: entry for entry in entries}
    requested = names or config.get("contestants") or sorted(by_name, key=str.lower)
    if len(requested) != len(set(requested)):
        raise ValueError("specialist names must not be repeated")

    allowed_states = set(config.get("allowed_states", []))
    entrants: list[dict[str, Any]] = []
    for name in requested:
        if name not in by_name:
            raise ValueError(f"specialist is not registered: {name}")
        registry_entry = by_name[name]
        specialist = SUB_AGENTS_ROOT / registry_entry["path"]
        status = read_json(specialist / "status.json")
        if status.get("active_experiment") or registry_entry.get("active_experiment"):
            raise ValueError(f"specialist has an active experiment: {name}")
        if allowed_states and status.get("state") not in allowed_states:
            raise ValueError(
                f"specialist {name} is in state {status.get('state')!r}; "
                f"allowed states are {sorted(allowed_states)}"
            )

        agent_path = specialist / "main.py"
        deck_path = specialist / "deck.csv"
        deck_report = validate_deck(deck_path)
        agent_report = validate_python_syntax(agent_path)
        if not deck_report.ok or not agent_report.ok:
            errors = deck_report.errors + agent_report.errors
            raise ValueError(f"specialist {name} failed static validation: {'; '.join(errors)}")
        entrants.append(
            {
                "name": name,
                "version": status.get("current_version", registry_entry.get("current_version", "unknown")),
                "state": status.get("state"),
                "provider": registry_entry.get("provider"),
                "specialist": specialist,
                "agent": agent_path,
                "deck": deck_path,
                "agent_sha256": sha256_file(agent_path),
                "deck_sha256": sha256_file(deck_path),
            }
        )

    if len(entrants) < 2:
        raise ValueError("a tournament requires at least two registered specialists")
    return entrants


def matchup_filename(a: str, b: str) -> str:
    return f"{a}__vs__{b}.json"


def run_matchup(
    entrant_a: dict[str, Any],
    entrant_b: dict[str, Any],
    games_per_seat: int,
    max_steps: int,
    seed: int,
    timeout_seconds: int,
    output_dir: Path,
) -> dict[str, Any]:
    output = output_dir / matchup_filename(entrant_a["name"], entrant_b["name"])
    command = [
        sys.executable,
        str(MATCHUP_RUNNER),
        "--agent-a",
        str(entrant_a["agent"]),
        "--deck-a",
        str(entrant_a["deck"]),
        "--name-a",
        entrant_a["name"],
        "--version-a",
        entrant_a["version"],
        "--agent-b",
        str(entrant_b["agent"]),
        "--deck-b",
        str(entrant_b["deck"]),
        "--name-b",
        entrant_b["name"],
        "--version-b",
        entrant_b["version"],
        "--games-per-seat",
        str(games_per_seat),
        "--max-steps",
        str(max_steps),
        "--seed",
        str(seed),
        "--output",
        str(output),
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    output.with_suffix(".stdout.log").write_text(completed.stdout, encoding="utf-8")
    output.with_suffix(".stderr.log").write_text(completed.stderr, encoding="utf-8")
    if not output.is_file():
        raise RuntimeError(
            f"matchup {entrant_a['name']} vs {entrant_b['name']} produced no result "
            f"(exit {completed.returncode})"
        )
    result = read_json(output)
    result["process"] = {
        "returncode": completed.returncode,
        "duration_seconds": time.perf_counter() - started,
        "stdout_log": output.with_suffix(".stdout.log").name,
        "stderr_log": output.with_suffix(".stderr.log").name,
    }
    write_json_atomic(output, result)
    return result


def aggregate_ranking(entrants: list[dict[str, Any]], matchups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for entrant in entrants:
        rows[entrant["name"]] = {
            "name": entrant["name"],
            "version": entrant["version"],
            "games": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "timeouts": 0,
            "agent_crashes": 0,
            "illegal_actions": 0,
            "engine_crashes": 0,
            "decision_ms": 0.0,
            "decisions": 0,
            "max_decision_time_ms": 0.0,
            "matchups": [],
        }

    for result in matchups:
        a_name = result["pair_a"]["name"]
        b_name = result["pair_b"]["name"]
        for side, own_name, other_name, own_wins, own_losses in (
            ("a", a_name, b_name, result["a_wins"], result["b_wins"]),
            ("b", b_name, a_name, result["b_wins"], result["a_wins"]),
        ):
            row = rows[own_name]
            row["games"] += result["games"]
            row["wins"] += own_wins
            row["losses"] += own_losses
            row["draws"] += result["draws"]
            row["timeouts"] += result["timeouts"]
            row["agent_crashes"] += result["faults"][side]["crashes"]
            row["illegal_actions"] += result["faults"][side]["illegal_actions"]
            row["engine_crashes"] += result["engine_crashes"]
            timing = result["decision_time"][side]
            decisions = timing["decisions"]
            if decisions and timing["average_ms"] is not None:
                row["decision_ms"] += timing["average_ms"] * decisions
                row["decisions"] += decisions
                row["max_decision_time_ms"] = max(row["max_decision_time_ms"], timing["max_ms"] or 0.0)
            row["matchups"].append(
                {
                    "opponent": other_name,
                    "games": result["games"],
                    "wins": own_wins,
                    "losses": own_losses,
                    "draws": result["draws"],
                    "win_rate": own_wins / result["games"],
                }
            )

    ranking: list[dict[str, Any]] = []
    for row in rows.values():
        games = row.pop("games")
        decisions = row.pop("decisions")
        decision_ms = row.pop("decision_ms")
        row["games"] = games
        row["field_win_rate"] = row["wins"] / games if games else 0.0
        decisive = row["wins"] + row["losses"]
        row["decisive_win_rate"] = row["wins"] / decisive if decisive else None
        row["worst_matchup_win_rate"] = min(
            (matchup["win_rate"] for matchup in row["matchups"]), default=0.0
        )
        row["average_decision_time_ms"] = decision_ms / decisions if decisions else None
        row["decision_count"] = decisions
        row["fault_free"] = row["agent_crashes"] == 0 and row["illegal_actions"] == 0
        ranking.append(row)

    ranking.sort(
        key=lambda row: (
            row["fault_free"],
            row["field_win_rate"],
            row["worst_matchup_win_rate"],
            -(row["average_decision_time_ms"] or float("inf")),
        ),
        reverse=True,
    )
    for index, row in enumerate(ranking, 1):
        row["rank"] = index
    return ranking


def build_matrix(entrants: list[dict[str, Any]], ranking: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    names = [entrant["name"] for entrant in entrants]
    by_name = {row["name"]: row for row in ranking}
    matrix: dict[str, dict[str, Any]] = {}
    for name in names:
        matrix[name] = {}
        matchup_by_opponent = {item["opponent"]: item for item in by_name[name]["matchups"]}
        for opponent in names:
            matrix[name][opponent] = None if name == opponent else matchup_by_opponent[opponent]
    return matrix


def field_signature(entrants: list[dict[str, Any]]) -> list[str]:
    return sorted(entrant["name"] for entrant in entrants)


def previous_comparable_summary(entrants: list[dict[str, Any]]) -> dict[str, Any] | None:
    signature = field_signature(entrants)
    result_dirs = sorted((TOURNAMENT_ROOT / "results").glob("T-*"), reverse=True)
    for directory in result_dirs:
        summary_path = directory / "summary.json"
        if not summary_path.is_file():
            continue
        try:
            summary = read_json(summary_path)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            continue
        prior_entrants = summary.get("entrants", [])
        if sorted(item.get("name") for item in prior_entrants) == signature:
            return summary
    return None


def build_progress_comparison(
    ranking: list[dict[str, Any]],
    entrants: list[dict[str, Any]],
    previous: dict[str, Any] | None,
    games_per_seat: int,
) -> dict[str, Any]:
    if previous is None:
        return {
            "previous_tournament_id": None,
            "same_field": False,
            "same_sample_size": False,
            "directly_comparable": False,
            "rows": [],
        }

    previous_ranking = {row["name"]: row for row in previous.get("ranking", [])}
    previous_entrants = {entry["name"]: entry for entry in previous.get("entrants", [])}
    current_entrants = {entry["name"]: entry for entry in entrants}
    rows = []
    for row in ranking:
        prior = previous_ranking.get(row["name"])
        if prior is None:
            continue
        current_manifest = current_entrants[row["name"]]
        prior_manifest = previous_entrants.get(row["name"], {})
        rows.append(
            {
                "name": row["name"],
                "previous_version": prior.get("version"),
                "current_version": row["version"],
                "agent_changed": prior_manifest.get("agent_sha256") != current_manifest.get("agent_sha256"),
                "deck_changed": prior_manifest.get("deck_sha256") != current_manifest.get("deck_sha256"),
                "previous_rank": prior.get("rank"),
                "current_rank": row["rank"],
                "rank_change": (
                    prior["rank"] - row["rank"]
                    if isinstance(prior.get("rank"), int)
                    else None
                ),
                "previous_field_win_rate": prior.get("field_win_rate"),
                "current_field_win_rate": row["field_win_rate"],
                "field_win_rate_change": (
                    row["field_win_rate"] - prior["field_win_rate"]
                    if isinstance(prior.get("field_win_rate"), (int, float))
                    else None
                ),
                "previous_worst_matchup_win_rate": prior.get("worst_matchup_win_rate"),
                "current_worst_matchup_win_rate": row["worst_matchup_win_rate"],
                "worst_matchup_win_rate_change": (
                    row["worst_matchup_win_rate"] - prior["worst_matchup_win_rate"]
                    if isinstance(prior.get("worst_matchup_win_rate"), (int, float))
                    else None
                ),
            }
        )

    same_field = field_signature(entrants) == sorted(previous_entrants)
    same_sample_size = previous.get("games_per_seat") == games_per_seat
    return {
        "previous_tournament_id": previous.get("tournament_id"),
        "same_field": same_field,
        "same_sample_size": same_sample_size,
        "directly_comparable": same_field and same_sample_size,
        "rows": rows,
    }


def format_delta(value: float | None, percentage: bool = False) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.1%}" if percentage else f"{value:+g}"


def markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        f"# Tournament {summary['tournament_id']}",
        "",
        f"Status: **{summary['status']}**",
        "",
        (
            f"Seat-balanced field comparison with {summary['games_per_seat']} games per seat "
            f"for each pairing. This report is advisory and cannot promote the submission."
        ),
        "",
        "## Ranking",
        "",
        "| Rank | Deck-agent pair | Field win rate | Worst matchup | W-L-D | Agent faults | Avg decision |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary["ranking"]:
        faults = row["agent_crashes"] + row["illegal_actions"]
        average_ms = row["average_decision_time_ms"]
        average_text = f"{average_ms:.3f} ms" if average_ms is not None else "n/a"
        lines.append(
            f"| {row['rank']} | {row['name']} ({row['version']}) | "
            f"{row['field_win_rate']:.1%} | {row['worst_matchup_win_rate']:.1%} | "
            f"{row['wins']}-{row['losses']}-{row['draws']} | {faults} | {average_text} |"
        )

    names = [entrant["name"] for entrant in summary["entrants"]]
    lines.extend(["", "## Matchup Matrix", "", "Rows show the row pair's win rate over all games.", ""])
    lines.append("| Pair | " + " | ".join(names) + " |")
    lines.append("|---|" + "|".join("---:" for _ in names) + "|")
    for name in names:
        cells = []
        for opponent in names:
            cell = summary["matchup_matrix"][name][opponent]
            cells.append("-" if cell is None else f"{cell['win_rate']:.1%} ({cell['wins']}/{cell['games']})")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    comparison = summary.get("progress_comparison", {})
    previous_id = comparison.get("previous_tournament_id")
    if previous_id:
        comparison_label = (
            "directly comparable"
            if comparison.get("directly_comparable")
            else "context only: field or sample size changed"
        )
        lines.extend(
            [
                "",
                "## Progress Since Previous Run",
                "",
                f"Compared with `{previous_id}` ({comparison_label}).",
                "",
                "| Pair | Version | Code/deck changed | Rank delta | Field win-rate delta | Worst-matchup delta |",
                "|---|---|---|---:|---:|---:|",
            ]
        )
        for row in comparison.get("rows", []):
            changed = []
            if row["agent_changed"]:
                changed.append("agent")
            if row["deck_changed"]:
                changed.append("deck")
            lines.append(
                f"| {row['name']} | {row['previous_version']} -> {row['current_version']} | "
                f"{', '.join(changed) or 'none'} | {format_delta(row['rank_change'])} | "
                f"{format_delta(row['field_win_rate_change'], percentage=True)} | "
                f"{format_delta(row['worst_matchup_win_rate_change'], percentage=True)} |"
            )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Ranking is fault-free status first, then field win rate, worst matchup, and decision time.",
            "- Engine crashes are reported separately and are not assigned to either specialist.",
            "- A small pilot verifies infrastructure; it is not sufficient evidence for submission promotion.",
            "- Promotion remains a separate human-approved phase.",
            "",
        ]
    )
    return "\n".join(lines)


def history_entry(summary: dict[str, Any]) -> str:
    lines = [
        f"## {summary['finished_at']} - {summary['tournament_id']}",
        "",
        (
            f"Field: {', '.join(entry['name'] for entry in summary['entrants'])}. "
            f"Games per seat: {summary['games_per_seat']}. Total games: {summary['total_games']}. "
            f"Provisional champion: **{summary['provisional_champion']}**."
        ),
        "",
        "| Rank | Pair | Version | W-L-D | Field win rate | Worst matchup | Agent faults |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]
    for row in summary["ranking"]:
        faults = row["agent_crashes"] + row["illegal_actions"]
        lines.append(
            f"| {row['rank']} | {row['name']} | {row['version']} | "
            f"{row['wins']}-{row['losses']}-{row['draws']} | {row['field_win_rate']:.1%} | "
            f"{row['worst_matchup_win_rate']:.1%} | {faults} |"
        )

    comparison = summary.get("progress_comparison", {})
    if comparison.get("previous_tournament_id"):
        comparability = "direct" if comparison.get("directly_comparable") else "context-only"
        lines.extend(
            [
                "",
                f"Progress comparison: `{comparison['previous_tournament_id']}` ({comparability}).",
                "",
                "| Pair | Agent/deck changed | Rank delta | Win-rate delta |",
                "|---|---|---:|---:|",
            ]
        )
        for row in comparison.get("rows", []):
            changed = []
            if row["agent_changed"]:
                changed.append("agent")
            if row["deck_changed"]:
                changed.append("deck")
            lines.append(
                f"| {row['name']} | {', '.join(changed) or 'none'} | "
                f"{format_delta(row['rank_change'])} | "
                f"{format_delta(row['field_win_rate_change'], percentage=True)} |"
            )

    lines.extend(
        [
            "",
            f"Detailed immutable report: `results/{summary['tournament_id']}/REPORT.md`",
            "",
        ]
    )
    return "\n".join(lines)


@contextmanager
def history_lock(timeout_seconds: float = 30.0):
    deadline = time.monotonic() + timeout_seconds
    descriptor = None
    while descriptor is None:
        try:
            descriptor = os.open(HISTORY_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"could not acquire tournament history lock: {HISTORY_LOCK_PATH}")
            time.sleep(0.05)
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
        yield
    finally:
        os.close(descriptor)
        HISTORY_LOCK_PATH.unlink(missing_ok=True)


def append_history(summary: dict[str, Any]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with history_lock():
        marker = f"<!-- tournament:{summary['tournament_id']} -->"
        is_new = not HISTORY_PATH.is_file() or HISTORY_PATH.stat().st_size == 0
        if not is_new:
            existing = HISTORY_PATH.read_text(encoding="utf-8")
            if marker in existing:
                return
        else:
            existing = (
                "# Plan_2 Tournament History\n\n"
                "Append-only ledger of complete deck-agent tournament runs. Detailed per-run "
                "reports remain immutable under `results/`. Deltas are direct only when the "
                "entrant field and games per seat match.\n\n"
            )
        separator = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
        with HISTORY_PATH.open("w" if is_new else "a", encoding="utf-8") as handle:
            if is_new:
                handle.write(existing)
            handle.write(f"{separator}{marker}\n{history_entry(summary)}")


def backfill_history() -> None:
    prior_by_field: dict[tuple[str, ...], dict[str, Any]] = {}
    for directory in sorted((TOURNAMENT_ROOT / "results").glob("T-*")):
        summary_path = directory / "summary.json"
        if not summary_path.is_file():
            continue
        summary = read_json(summary_path)
        signature = tuple(sorted(entry["name"] for entry in summary.get("entrants", [])))
        historical = dict(summary)
        historical["progress_comparison"] = build_progress_comparison(
            summary.get("ranking", []),
            summary.get("entrants", []),
            prior_by_field.get(signature),
            int(summary.get("games_per_seat", 0)),
        )
        append_history(historical)
        prior_by_field[signature] = summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the central Plan_2 deck-agent tournament.")
    parser.add_argument("--specialist", action="append", help="Registered specialist; repeat for each entrant")
    parser.add_argument("--games-per-seat", type=int, help="Override configured games in each seat orientation")
    parser.add_argument("--max-steps", type=int, help="Override configured turn-selection limit")
    parser.add_argument("--seed", type=int, help="Override configured seed label")
    args = parser.parse_args()

    config = read_json(CONFIG_PATH)
    games_per_seat = args.games_per_seat or int(config["games_per_seat"])
    max_steps = args.max_steps or int(config["max_steps_per_game"])
    seed = args.seed if args.seed is not None else int(config["seed"])
    timeout_seconds = int(config["matchup_timeout_seconds"])
    if games_per_seat <= 0 or max_steps <= 0 or timeout_seconds <= 0:
        raise ValueError("tournament game, step, and timeout limits must be positive")

    entrants = select_entrants(args.specialist, config)
    previous_summary = previous_comparable_summary(entrants)
    backfill_history()
    tournament_id = run_id()
    result_dir = TOURNAMENT_ROOT / "results" / tournament_id
    matchup_dir = result_dir / "matchups"
    matchup_dir.mkdir(parents=True, exist_ok=False)
    started_at = utc_now()
    started = time.perf_counter()

    entrant_manifest = [
        {
            key: relative_to_repo(value) if isinstance(value, Path) else value
            for key, value in entrant.items()
            if key != "specialist"
        }
        for entrant in entrants
    ]
    manifest = {
        "schema_version": 1,
        "tournament_id": tournament_id,
        "started_at": started_at,
        "games_per_seat": games_per_seat,
        "max_steps_per_game": max_steps,
        "seed": seed,
        "auto_promote": False,
        "entrants": entrant_manifest,
    }
    write_json_atomic(result_dir / "manifest.json", manifest)

    matchups: list[dict[str, Any]] = []
    for pair_index, (entrant_a, entrant_b) in enumerate(itertools.combinations(entrants, 2)):
        print(f"Running {entrant_a['name']} vs {entrant_b['name']}...")
        matchups.append(
            run_matchup(
                entrant_a,
                entrant_b,
                games_per_seat,
                max_steps,
                seed + pair_index,
                timeout_seconds,
                matchup_dir,
            )
        )

    ranking = aggregate_ranking(entrants, matchups)
    engine_crashes = sum(result["engine_crashes"] for result in matchups)
    summary = {
        "schema_version": 1,
        "tournament_id": tournament_id,
        "status": "complete" if engine_crashes == 0 else "complete_with_engine_errors",
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_seconds": time.perf_counter() - started,
        "seed": seed,
        "games_per_seat": games_per_seat,
        "pairings": len(matchups),
        "total_games": sum(result["games"] for result in matchups),
        "engine_crashes": engine_crashes,
        "auto_promote": False,
        "provisional_champion": ranking[0]["name"],
        "entrants": entrant_manifest,
        "ranking": ranking,
        "matchup_matrix": build_matrix(entrants, ranking),
        "progress_comparison": build_progress_comparison(
            ranking,
            entrant_manifest,
            previous_summary,
            games_per_seat,
        ),
        "matchup_results": [
            relative_to_repo(matchup_dir / matchup_filename(result["pair_a"]["name"], result["pair_b"]["name"]))
            for result in matchups
        ],
    }
    write_json_atomic(result_dir / "summary.json", summary)
    (result_dir / "REPORT.md").write_text(markdown_report(summary), encoding="utf-8")
    append_history(summary)
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    print(f"Report: {result_dir / 'REPORT.md'}")
    return 1 if engine_crashes else 0


if __name__ == "__main__":
    raise SystemExit(main())
