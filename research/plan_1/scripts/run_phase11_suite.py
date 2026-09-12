from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plan1.deployment.config import load_deployment_config
from plan1.deployment.package import build_submission_package
from plan1.reproducibility import canonical_json_hash, sha256_file, write_json_atomic


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "plan_1" / "src"
ENGINE_ROOT = ROOT / "sample_submission" / "sample_submission"
PROBE = Path(__file__).with_name("phase11_probe.py")


def _probe(package: Path, *, fault: str = "none", games: int = 0, max_steps: int = 3000) -> dict[str, Any]:
    command = [
        sys.executable, "-I", str(PROBE), str(package), str(ENGINE_ROOT), "--fault", fault,
        "--max-steps", str(max_steps),
    ]
    if games:
        command.extend(("--games", str(games)))
    completed = subprocess.run(command, capture_output=True, text=True, timeout=900, check=False)
    if not completed.stdout.strip():
        raise RuntimeError(f"Phase 11 probe produced no JSON: {completed.stderr.strip()}")
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    result["returncode"] = completed.returncode
    result["stderr"] = completed.stderr.strip()
    return result


def _frozen_evidence(path: Path, package: dict[str, Any]) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    analysis = report["analysis"]
    gate = analysis["gate"]
    candidate = next(item for item in report["policies"] if item["role"] == "candidate")
    identity_matches = candidate["sha256"] == package["manifest"]["source_identity"]["checkpoint_sha256"]
    return {
        "report_path": str(path.resolve()),
        "report_sha256": sha256_file(path),
        "run_id": report["run_id"],
        "games": report["schedule"]["total_games"],
        "matchups": report["schedule"]["matchups"],
        "candidate_checkpoint_identity_matches": identity_matches,
        "decision": gate["decision"],
        "promoted": gate["promoted"],
        "conclusive_strength_rejection": gate["conclusive_strength_rejection"],
        "passed": identity_matches and gate["decision"] == "rejected" and not gate["promoted"],
    }


def _active_identity() -> dict[str, str]:
    return {
        "main.py": sha256_file(ENGINE_ROOT / "main.py"),
        "deck.csv": sha256_file(ENGINE_ROOT / "deck.csv"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and shadow-validate the Phase 11 package")
    parser.add_argument("--config", type=Path, default=Path("plan_1/configs/phase11_deployment.json"))
    parser.add_argument("--output", type=Path, default=Path("plan_1/artifacts/reports/phase11-shadow-validation.json"))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    config = load_deployment_config(args.config)
    if args.validate_only:
        print(json.dumps({"run_id": config.run_id, "validated": True}, indent=2))
        return 0
    active_before = _active_identity()
    package = build_submission_package(config, source_root=SOURCE_ROOT)
    package_root = Path(package["package_root"])
    normal = _probe(package_root)
    missing = _probe(package_root, fault="missing")
    corrupt = _probe(package_root, fault="corrupt")
    games = _probe(package_root, games=config.shadow_games, max_steps=config.max_steps)
    frozen = _frozen_evidence(config.frozen_evaluation_path, package)
    active_after = _active_identity()
    limits = config.runtime_limits
    package_passed = (
        package["verification"]["passed"]
        and package["archive_bytes"] <= limits.maximum_archive_bytes
    )
    runtime_passed = (
        normal["passed"]
        and normal["import_ms"] <= limits.maximum_import_ms
        and normal["status"]["model_load_ms"] <= limits.maximum_model_load_ms
        and missing["passed"] and missing["status"]["agent_status"] == "ready_heuristic"
        and corrupt["passed"] and corrupt["status"]["agent_status"] == "ready_heuristic"
        and games["passed"]
        and games["decision_timing"]["p95_ms"] <= limits.maximum_decision_p95_ms
        and games["decision_timing"]["max_ms"] <= limits.maximum_decision_ms
    )
    shadow_passed = package_passed and runtime_passed and frozen["passed"] and active_before == active_after
    unsigned = {
        "schema_version": 1,
        "run_id": config.run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": str(args.config.resolve()),
        "config_sha256": sha256_file(args.config),
        "package": package,
        "probes": {"normal": normal, "missing_model": missing, "corrupt_model": corrupt, "games": games},
        "frozen_evaluation": frozen,
        "active_submission": {
            "before": active_before,
            "after": active_after,
            "unchanged": active_before == active_after,
        },
        "gates": {
            "package_passed": package_passed,
            "runtime_passed": runtime_passed,
            "shadow_validation_passed": shadow_passed,
            "strength_passed": False,
        },
        "promotion": {
            "decision": "rejected",
            "replace_active_submission": False,
            "reason": "Phase 9 conclusively rejected this exact candidate on development and held-out strength.",
            "rollback_target": active_before,
        },
    }
    signature = {
        "kind": "sha256-integrity-signature-v1",
        "signer": config.signer,
        "signed_utc": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": canonical_json_hash(unsigned),
    }
    report = {**unsigned, "signature": signature}
    write_json_atomic(args.output, report)
    print(json.dumps({
        "run_id": config.run_id,
        "output": str(args.output.resolve()),
        "sha256": sha256_file(args.output),
        "archive_sha256": package["archive_sha256"],
        "shadow_validation_passed": shadow_passed,
        "promotion_decision": "rejected",
    }, indent=2))
    return 0 if shadow_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
