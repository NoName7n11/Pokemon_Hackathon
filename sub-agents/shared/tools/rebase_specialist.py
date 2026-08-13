from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import (
    REPO_ROOT,
    copy_file_atomic,
    copy_pair,
    read_json,
    resolve_specialist,
    sha256_file,
    update_registry_specialist,
    validate_deck,
    write_json_atomic,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def relative_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebase an inactive specialist onto a revised human deck.")
    parser.add_argument("--specialist", required=True)
    parser.add_argument("--deck", required=True, type=Path)
    parser.add_argument("--strategy", type=Path)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()

    specialist = resolve_specialist(args.specialist)
    status = read_json(specialist / "status.json")
    config = read_json(specialist / "config.json")
    if status.get("active_experiment") or status.get("state") != "READY_FOR_EXPERIMENT":
        print("ERROR: specialist must be inactive and READY_FOR_EXPERIMENT", file=sys.stderr)
        return 2

    source_deck = args.deck.resolve()
    deck_report = validate_deck(source_deck)
    if not deck_report.ok:
        for error in deck_report.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    strategy = args.strategy.resolve() if args.strategy else None
    if strategy is not None and not strategy.is_file():
        print(f"ERROR: strategy file does not exist: {strategy}", file=sys.stderr)
        return 2

    old_version = status["current_version"]
    old_hash = sha256_file(specialist / "deck.csv")
    number = int(old_version[1:4]) + 1 if old_version.startswith("v") and old_version[1:4].isdigit() else 1
    new_version = f"v{number:03d}-deck-rebase"
    snapshot = specialist / "snapshots" / new_version
    if snapshot.exists():
        print(f"ERROR: snapshot already exists: {snapshot}", file=sys.stderr)
        return 2

    temporary_deck = specialist / ".deck-rebase.tmp"
    try:
        shutil.copy2(source_deck, temporary_deck)
        temporary_deck.replace(specialist / "deck.csv")
        copy_pair(specialist, snapshot)
        write_json_atomic(snapshot / "manifest.json", {
            "version": new_version,
            "created_at": utc_now(),
            "reason": args.reason,
            "source_deck": relative_to_repo(source_deck),
            "source_strategy": relative_to_repo(strategy) if strategy else None,
            "agent_sha256": sha256_file(snapshot / "main.py"),
            "deck_sha256": sha256_file(snapshot / "deck.csv"),
        })
    finally:
        temporary_deck.unlink(missing_ok=True)

    new_hash = sha256_file(specialist / "deck.csv")
    config["source_deck"] = relative_to_repo(source_deck)
    if strategy is not None:
        config["source_strategy"] = relative_to_repo(strategy)
    status.update({
        "current_version": new_version,
        "updated_at": utc_now(),
        "deck_sha256": new_hash,
        "validation": {
            "static": "passed",
            "runtime_import": "pending",
            "smoke_benchmark": "pending",
        },
    })
    write_json_atomic(specialist / "config.json", config)
    write_json_atomic(specialist / "status.json", status)
    update_registry_specialist(
        specialist.name,
        state=status["state"],
        active_experiment=None,
        current_version=new_version,
        agent_sha256=status["agent_sha256"],
        deck_sha256=new_hash,
    )
    with (specialist / "PROGRESS.md").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            f"\n## {utc_now()[:10]} - deck rebase\n\n"
            f"- **Rebased `{old_version}` to `{new_version}`.**\n"
            f"  - Deck hash: `{old_hash}` -> `{new_hash}`.\n"
            f"  - Source deck: `{relative_to_repo(source_deck)}`.\n"
            + (f"  - Strategy: `{relative_to_repo(strategy)}`.\n" if strategy else "")
            + f"  - Reason: {args.reason}\n"
        )
    print(f"Rebased {specialist.name}: {old_version} -> {new_version}")
    print(f"Deck SHA-256: {new_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
