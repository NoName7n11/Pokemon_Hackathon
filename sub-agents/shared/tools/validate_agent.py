from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from common import ENGINE_PARENT, resolve_specialist, validate_deck, validate_python_syntax


def runtime_import(agent_path: Path) -> dict:
    script = (
        "import importlib.util, pathlib, sys; "
        f"sys.path.insert(0, {str(ENGINE_PARENT)!r}); "
        f"p=pathlib.Path({str(agent_path)!r}); "
        "s=importlib.util.spec_from_file_location('plan2_candidate', p); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "assert callable(getattr(m, 'agent', None)); print('runtime import passed')"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ENGINE_PARENT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an isolated Plan_2 specialist.")
    parser.add_argument("specialist", help="Specialist directory or registered specialist name")
    parser.add_argument("--runtime", action="store_true", help="Also import main.py (requires cg)")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    try:
        specialist_dir = resolve_specialist(args.specialist)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    deck_report = validate_deck(specialist_dir / "deck.csv")
    agent_report = validate_python_syntax(specialist_dir / "main.py")
    output = {
        "specialist": specialist_dir.name,
        "ok": deck_report.ok and agent_report.ok,
        "deck": deck_report.to_dict(),
        "agent": agent_report.to_dict(),
    }
    if args.runtime:
        output["runtime"] = runtime_import(specialist_dir / "main.py")
        output["ok"] = output["ok"] and output["runtime"]["ok"]

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=True))
    else:
        print(f"Specialist: {output['specialist']}")
        print(f"Static validation: {'PASS' if deck_report.ok and agent_report.ok else 'FAIL'}")
        print(f"  deck: {deck_report.details}")
        print(f"  agent: {agent_report.details}")
        for section in (deck_report, agent_report):
            for warning in section.warnings:
                print(f"WARNING: {warning}")
            for error in section.errors:
                print(f"ERROR: {error}")
        if args.runtime:
            runtime = output["runtime"]
            print(f"Runtime import: {'PASS' if runtime['ok'] else 'FAIL'}")
            if runtime["stderr"]:
                print(runtime["stderr"])
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
