from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

from common import (
    ENGINE_PARENT,
    SUB_AGENTS_ROOT,
    read_json,
    sha256_file,
    validate_deck,
    validate_python_syntax,
    write_json_atomic,
)
from provider_adapters import provider_status


VERIFICATION_ROOT = SUB_AGENTS_ROOT / "verification"
REPORT_PATH = VERIFICATION_ROOT / "REPORT.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_schema(instance: dict[str, Any], schema_path: Path, label: str, errors: list[str]) -> None:
    try:
        jsonschema.validate(instance, read_json(schema_path))
    except (jsonschema.ValidationError, jsonschema.SchemaError, OSError, ValueError) as exc:
        errors.append(f"{label} schema validation failed: {exc}")


def runtime_import(path: Path) -> tuple[bool, str]:
    script = (
        "import importlib.util, pathlib, sys; "
        f"sys.path.insert(0, {str(ENGINE_PARENT)!r}); "
        f"p=pathlib.Path({str(path)!r}); "
        "s=importlib.util.spec_from_file_location('platform_verify_agent', p); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "assert callable(getattr(m, 'agent', None)); assert callable(getattr(m, 'read_deck_csv', None))"
    )
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30, check=False)
    return completed.returncode == 0, completed.stderr.strip()


def append_report(result: dict[str, Any]) -> None:
    VERIFICATION_ROOT.mkdir(parents=True, exist_ok=True)
    is_new = not REPORT_PATH.is_file() or REPORT_PATH.stat().st_size == 0
    with REPORT_PATH.open("w" if is_new else "a", encoding="utf-8") as handle:
        if is_new:
            handle.write("# Plan_2 Verification History\n\nAppend-only platform verification results.\n\n")
        handle.write(
            f"<!-- verification:{result['id']} -->\n"
            f"## {result['finished_at']} - {result['id']}\n\n"
            f"- Overall: **{'PASS' if result['ok'] else 'FAIL'}**\n"
            f"- Phases: "
            + ", ".join(f"{name}={'PASS' if value['ok'] else 'FAIL'}" for name, value in result["phases"].items())
            + f"\n- Errors: {len(result['errors'])}\n- Warnings: {len(result['warnings'])}\n\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Plan_2 platform invariants across all implemented phases.")
    parser.parse_args()
    started_at = utc_now()
    verification_id = datetime.now(timezone.utc).strftime("VERIFY-%Y%m%d-%H%M%S-%f")
    global_errors: list[str] = []
    warnings: list[str] = []
    phases: dict[str, dict[str, Any]] = {}

    all_json = list(SUB_AGENTS_ROOT.rglob("*.json"))
    for path in all_json:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            global_errors.append(f"invalid JSON {path}: {exc}")

    phase_errors: list[str] = []
    registry = read_json(SUB_AGENTS_ROOT / "registry.json")
    specialists = registry.get("specialists", [])
    check(len(specialists) >= 2, "Phase 1 requires at least two registered specialists", phase_errors)
    for entry in specialists:
        directory = SUB_AGENTS_ROOT / entry["path"]
        status = read_json(directory / "status.json")
        deck_report = validate_deck(directory / "deck.csv")
        agent_report = validate_python_syntax(directory / "main.py")
        check(deck_report.ok, f"{entry['name']} deck invalid: {deck_report.errors}", phase_errors)
        check(agent_report.ok, f"{entry['name']} agent invalid: {agent_report.errors}", phase_errors)
        ok, detail = runtime_import(directory / "main.py")
        check(ok, f"{entry['name']} runtime import failed: {detail}", phase_errors)
        check(entry.get("agent_sha256") == sha256_file(directory / "main.py"), f"{entry['name']} registry agent hash stale", phase_errors)
        check(entry.get("deck_sha256") == sha256_file(directory / "deck.csv"), f"{entry['name']} registry deck hash stale", phase_errors)
        check(status.get("active_experiment") is None, f"{entry['name']} has an active experiment", phase_errors)
    phases["phase_1_foundation"] = {"ok": not phase_errors, "errors": phase_errors, "specialists": len(specialists)}

    phase_errors = []
    experiment_schema = SUB_AGENTS_ROOT / "shared" / "schemas" / "experiment.schema.json"
    experiments = list((SUB_AGENTS_ROOT / "specialists").glob("*/experiments/EXP-*/experiment.json"))
    for path in experiments:
        validate_schema(read_json(path), experiment_schema, str(path), phase_errors)
    benchmark = read_json(SUB_AGENTS_ROOT / "shared" / "benchmark_config.json")
    expected_stages = {"smoke": 20, "screening": 200, "main": 300, "confirmation": 500}
    check(benchmark.get("game_stages") == expected_stages, "Phase 2 evidence stages are not 20/200/300/500", phase_errors)
    check(benchmark.get("minimum_acceptance_stage") == "confirmation", "Phase 2 acceptance is not confirmation-gated", phase_errors)
    phases["phase_2_experiments"] = {"ok": not phase_errors, "errors": phase_errors, "experiments": len(experiments)}

    phase_errors = []
    provider_config = read_json(SUB_AGENTS_ROOT / "shared" / "provider_config.json")
    configured = provider_config.get("providers", {})
    check(set(configured) == {"codex", "claude", "antigravity"}, "Phase 3 provider set is incomplete", phase_errors)
    providers = provider_status(provider_config)
    unavailable = [item["provider"] for item in providers if not item.get("available")]
    if unavailable:
        warnings.append("Configured coding providers currently unavailable: " + ", ".join(unavailable))
    phases["phase_3_providers"] = {"ok": not phase_errors, "errors": phase_errors, "providers": providers}

    phase_errors = []
    orchestration = read_json(SUB_AGENTS_ROOT / "shared" / "orchestration_config.json")
    check(orchestration.get("auto_accept") is False, "Phase 4 auto_accept must be false", phase_errors)
    check(orchestration.get("auto_promote") is False, "Phase 4 auto_promote must be false", phase_errors)
    locks = list(SUB_AGENTS_ROOT.rglob("*.lock"))
    check(not locks, f"stale Plan_2 locks found: {locks}", phase_errors)
    phases["phase_4_orchestration"] = {"ok": not phase_errors, "errors": phase_errors}

    phase_errors = []
    tournament_schema = SUB_AGENTS_ROOT / "shared" / "schemas" / "tournament.schema.json"
    matchup_schema = SUB_AGENTS_ROOT / "shared" / "schemas" / "matchup.schema.json"
    result_dirs = sorted((SUB_AGENTS_ROOT / "tournaments" / "results").glob("T-*"))
    for directory in result_dirs:
        validate_schema(read_json(directory / "summary.json"), tournament_schema, str(directory / "summary.json"), phase_errors)
        for matchup in (directory / "matchups").glob("*.json"):
            validate_schema(read_json(matchup), matchup_schema, str(matchup), phase_errors)
    history = (SUB_AGENTS_ROOT / "tournaments" / "REPORT.md").read_text(encoding="utf-8")
    marker_count = history.count("<!-- tournament:")
    check(marker_count == len(result_dirs), f"tournament history has {marker_count} markers for {len(result_dirs)} runs", phase_errors)
    phases["phase_5_tournament"] = {"ok": not phase_errors, "errors": phase_errors, "runs": len(result_dirs)}
    if not any(read_json(path / "summary.json").get("games_per_seat", 0) >= 300 for path in result_dirs):
        warnings.append("No statistically powered central tournament has completed yet")

    phase_errors = []
    continuous_state = read_json(SUB_AGENTS_ROOT / "continuous" / "state.json")
    job_schema = SUB_AGENTS_ROOT / "shared" / "schemas" / "continuous_job.schema.json"
    for job in continuous_state.get("jobs", []):
        validate_schema(job, job_schema, f"continuous job {job.get('id')}", phase_errors)
        if job.get("state") == "awaiting_provider_authorization":
            check(not job.get("provider_authorized"), f"{job['id']} authorization state is inconsistent", phase_errors)
    continuous_config = read_json(SUB_AGENTS_ROOT / "shared" / "continuous_config.json")
    check(continuous_config.get("auto_accept") is False, "continuous auto_accept must be false", phase_errors)
    check(continuous_config.get("auto_promote") is False, "continuous auto_promote must be false", phase_errors)
    phases["phase_5_continuous"] = {"ok": not phase_errors, "errors": phase_errors, "jobs": len(continuous_state.get("jobs", []))}

    phase_errors = []
    promotion_config = read_json(SUB_AGENTS_ROOT / "promotion" / "promotion_config.json")
    check(promotion_config.get("auto_promote") is False, "Phase 6 auto_promote must be false", phase_errors)
    check(promotion_config.get("automatic_rollback_on_failure") is True, "Phase 6 automatic rollback is disabled", phase_errors)
    promotion_schema = SUB_AGENTS_ROOT / "shared" / "schemas" / "promotion.schema.json"
    requests = list((SUB_AGENTS_ROOT / "promotion" / "requests").glob("PROM-*.json"))
    for path in requests:
        validate_schema(read_json(path), promotion_schema, str(path), phase_errors)
    phases["phase_6_promotion"] = {"ok": not phase_errors, "errors": phase_errors, "requests": len(requests)}

    submission = {
        "agent_sha256": sha256_file(ENGINE_PARENT / "main.py"),
        "deck_sha256": sha256_file(ENGINE_PARENT / "deck.csv"),
    }
    hydrapple = next((entry for entry in specialists if entry["name"] == "Hydrapple"), None)
    if hydrapple and submission != {
        "agent_sha256": hydrapple["agent_sha256"], "deck_sha256": hydrapple["deck_sha256"]
    }:
        warnings.append("Active submission no longer matches the accepted Hydrapple pair")

    global_errors.extend(error for phase in phases.values() for error in phase["errors"])
    result = {
        "schema_version": 1,
        "id": verification_id,
        "started_at": started_at,
        "finished_at": utc_now(),
        "ok": not global_errors,
        "phases": phases,
        "submission": submission,
        "json_files_checked": len(all_json),
        "errors": global_errors,
        "warnings": warnings,
    }
    VERIFICATION_ROOT.mkdir(parents=True, exist_ok=True)
    write_json_atomic(VERIFICATION_ROOT / f"{verification_id}.json", result)
    write_json_atomic(VERIFICATION_ROOT / "latest.json", result)
    append_report(result)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
