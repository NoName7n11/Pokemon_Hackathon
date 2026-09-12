from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401

from plan1.engine.process_probe import run_process_isolation_probe
from plan1.paths import ARTIFACT_ROOT, REPO_ROOT
from plan1.reproducibility import write_json_atomic


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify native engine isolation across spawned worker processes.")
    parser.add_argument("--deck", type=Path, default=REPO_ROOT / "Decs" / "Hydrapple.csv")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--sessions", type=int, default=50)
    parser.add_argument("--max-path-steps", type=int, default=600)
    parser.add_argument("--output", type=Path, default=ARTIFACT_ROOT / "reports" / "phase1-process-isolation.json")
    args = parser.parse_args()
    report = run_process_isolation_probe(
        args.deck,
        workers=args.workers,
        sessions=args.sessions,
        max_path_steps=args.max_path_steps,
    )
    write_json_atomic(args.output, report)
    print(f"Wrote {args.output}")
    print(f"ok: {report['ok']}")
    print(f"exit_codes: {report['exit_codes']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
