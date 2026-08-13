from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401

from plan1.config import load_config
from plan1.paths import ARTIFACT_ROOT, CONFIG_ROOT, REPO_ROOT
from plan1.reproducibility import build_manifest, write_json_atomic


DEFAULT_FILES = (
    "sample_submission/sample_submission/main.py",
    "sample_submission/sample_submission/deck.csv",
    "sample_submission/sample_submission/cg/api.py",
    "sample_submission/sample_submission/cg/game.py",
    "Decs/Hydrapple.csv",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture immutable identities for the Plan 1 starting baseline.")
    parser.add_argument("--config", type=Path, default=CONFIG_ROOT / "mcts_baseline.json")
    parser.add_argument("--output", type=Path, default=ARTIFACT_ROOT / "manifests" / "phase0-baseline.json")
    parser.add_argument("--file", action="append", dest="files", help="Repository-relative file to hash")
    args = parser.parse_args()
    config = load_config(args.config)
    tracked = [REPO_ROOT / value for value in (args.files or DEFAULT_FILES)]
    manifest = build_manifest(REPO_ROOT, config, tracked, run_kind="phase0-baseline", run_id="phase0-baseline")
    write_json_atomic(args.output, manifest)
    print(f"Wrote {args.output} with {len(manifest['files'])} tracked files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
