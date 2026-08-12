from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
from pathlib import Path

from common import SUB_AGENTS_ROOT, read_json, resolve_specialist, write_json_atomic
from orchestrate import SpecialistLock, create_review_pack, update_orchestration, utc_now


TOOLS_DIR = Path(__file__).resolve().parent
BENCHMARK_CONFIG = SUB_AGENTS_ROOT / "shared" / "benchmark_config.json"


def run_checked(command: list[str], log_path: Path, timeout_seconds: int) -> None:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "COMMAND: " + subprocess.list2cmdline(command)
        + f"\n\nSTDOUT:\n{completed.stdout}\n\nSTDERR:\n{completed.stderr}",
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise ValueError(f"command failed with exit {completed.returncode}; see {log_path}")


def eligible_opponents(specialist_name: str) -> list[dict]:
    registry = read_json(SUB_AGENTS_ROOT / "registry.json")
    opponents = []
    for entry in registry.get("specialists", []):
        if entry["name"] == specialist_name or entry.get("state") != "READY_FOR_EXPERIMENT":
            continue
        directory = SUB_AGENTS_ROOT / entry["path"]
        status = read_json(directory / "status.json")
        if status.get("active_experiment") or status.get("state") != "READY_FOR_EXPERIMENT":
            continue
        opponents.append({"entry": entry, "directory": directory, "status": status})
    return sorted(opponents, key=lambda item: item["entry"]["name"].lower())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run human-authorized deep evidence for an active candidate.")
    parser.add_argument("--specialist", required=True)
    parser.add_argument("--seed", type=int, help="Seed base; defaults to a fresh random value")
    args = parser.parse_args()

    specialist = resolve_specialist(args.specialist)
    policy = read_json(BENCHMARK_CONFIG)
    seed_base = args.seed if args.seed is not None else secrets.randbelow(2_000_000_000) + 1

    with SpecialistLock(specialist):
        status = read_json(specialist / "status.json")
        active = status.get("active_experiment")
        if not active:
            raise ValueError(f"{specialist.name} has no active experiment")
        experiment_dir = specialist / "experiments" / active
        experiment = read_json(experiment_dir / "experiment.json")
        if experiment.get("orchestration", {}).get("state") != "MAIN_AUTHORIZED":
            raise ValueError("deep evaluation requires human screening approval")

        logs = experiment_dir / "orchestration-logs"
        update_orchestration(experiment_dir, state="DEEP_EVALUATION", deep_seed_base=seed_base)
        for offset, stage in enumerate(("main", "confirmation"), 1):
            experiment = read_json(experiment_dir / "experiment.json")
            if experiment.get(f"{stage}_result") is not None:
                continue
            run_checked(
                [
                    sys.executable,
                    str(TOOLS_DIR / "run_experiment.py"),
                    "run",
                    "--specialist",
                    specialist.name,
                    "--stage",
                    stage,
                    "--seed",
                    str(seed_base + offset),
                ],
                logs / f"deep-{stage}.log",
                7200,
            )
            experiment = read_json(experiment_dir / "experiment.json")
            result = experiment[f"{stage}_result"]
            if result["crashes"] or result["illegal_actions"] or result["timeouts"]:
                raise ValueError(f"{stage} produced an execution failure")

        experiment = read_json(experiment_dir / "experiment.json")
        completed_opponents = {
            result.get("opponent") for result in experiment.get("cross_deck_results", [])
            if result.get("status") == "complete"
        }
        candidate = experiment_dir / "candidate"
        games_per_seat = int(policy["cross_deck_games_per_seat"])
        required = int(policy["required_cross_deck_opponents"])
        for index, opponent in enumerate(eligible_opponents(specialist.name)):
            name = opponent["entry"]["name"]
            if name in completed_opponents:
                continue
            output = experiment_dir / "results" / f"cross-deck-{name}.json"
            run_checked(
                [
                    sys.executable,
                    str(TOOLS_DIR / "matchup_pair.py"),
                    "--agent-a", str(candidate / "main.py"),
                    "--deck-a", str(candidate / "deck.csv"),
                    "--name-a", specialist.name,
                    "--version-a", experiment["candidate_version"],
                    "--agent-b", str(opponent["directory"] / "main.py"),
                    "--deck-b", str(opponent["directory"] / "deck.csv"),
                    "--name-b", name,
                    "--version-b", opponent["status"]["current_version"],
                    "--games-per-seat", str(games_per_seat),
                    "--max-steps", str(policy["max_steps_per_game"]),
                    "--seed", str(seed_base + 100 + index),
                    "--output", str(output),
                ],
                logs / f"deep-cross-{name}.log",
                7200,
            )
            result = read_json(output)
            experiment = read_json(experiment_dir / "experiment.json")
            experiment.setdefault("cross_deck_results", []).append(
                {
                    "status": "complete",
                    "opponent": name,
                    "opponent_version": opponent["status"]["current_version"],
                    "games": result["games"],
                    "wins": result["a_wins"],
                    "losses": result["b_wins"],
                    "draws": result["draws"],
                    "win_rate": result["a_win_rate"],
                    "result": str(output.relative_to(experiment_dir)).replace("\\", "/"),
                }
            )
            experiment["updated_at"] = utc_now()
            write_json_atomic(experiment_dir / "experiment.json", experiment)

        experiment = read_json(experiment_dir / "experiment.json")
        available = len({
            result.get("opponent") for result in experiment.get("cross_deck_results", [])
            if result.get("status") == "complete"
        })
        if available < required:
            limitation = f"cross-deck evidence has {available}/{required} required opponents"
            if limitation not in experiment.setdefault("limitations", []):
                experiment["limitations"].append(limitation)
                write_json_atomic(experiment_dir / "experiment.json", experiment)

        markdown, _ = create_review_pack(specialist, experiment_dir, "confirmation")
        update_orchestration(
            experiment_dir,
            state="FINAL_REVIEW_REQUIRED",
            final_review_pack=str(markdown.relative_to(SUB_AGENTS_ROOT)).replace("\\", "/"),
        )
        print(f"Final review required: {markdown}")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
