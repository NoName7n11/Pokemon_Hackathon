from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401

from plan1.engine.conformance import conformance_passes, read_deck, run_conformance
from plan1.paths import ARTIFACT_ROOT, REPO_ROOT
from plan1.reproducibility import write_json_atomic


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe the native search API contract used by Plan 1.")
    parser.add_argument("--deck", type=Path, default=REPO_ROOT / "Decs" / "Hydrapple.csv")
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument("--max-path-steps", type=int, default=600)
    parser.add_argument("--output", type=Path, default=ARTIFACT_ROOT / "reports" / "phase1-conformance.json")
    args = parser.parse_args()
    if args.sessions < 1 or args.max_path_steps < 1:
        parser.error("--sessions and --max-path-steps must be positive")
    result = run_conformance(read_deck(args.deck), session_iterations=args.sessions, max_path_steps=args.max_path_steps)
    data = result.to_dict()
    data["deck"] = str(args.deck.resolve())
    write_json_atomic(args.output, data)
    print(f"Wrote {args.output}")
    for key, value in data.items():
        print(f"{key}: {value}")
    return 0 if conformance_passes(result) else 1


if __name__ == "__main__":
    raise SystemExit(main())
