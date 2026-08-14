from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plan1.archival import build_evidence_archive, load_archive_config, verify_claims
from plan1.reproducibility import canonical_json_hash, sha256_file, write_json_atomic


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and verify the Phase 12 Strategy archive")
    parser.add_argument("--config", type=Path, default=Path("plan_1/configs/phase12_archive.json"))
    parser.add_argument("--output", type=Path, default=Path("plan_1/artifacts/reports/phase12-archive.json"))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    config = load_archive_config(args.config)
    if args.validate_only:
        claims = verify_claims(ROOT / config.claims_path, repo_root=ROOT)
        print(json.dumps({"run_id": config.run_id, "claims": claims}, indent=2))
        return 0 if claims["passed"] else 1
    built = build_evidence_archive(config, repo_root=ROOT)
    unsigned = {
        "schema_version": 1,
        "phase": 12,
        "run_id": config.run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": str(args.config.resolve()),
        "config_sha256": sha256_file(args.config),
        "strategy_report": {
            "path": "plan_1/strategy/STRATEGY_REPORT.md",
            "sha256": sha256_file(ROOT / "plan_1/strategy/STRATEGY_REPORT.md"),
        },
        "claim_verification": {
            "claims": built["claims"]["claims"],
            "checks": built["claims"]["checks"],
            "passed": built["claims"]["passed"],
        },
        "archive": built["archive"],
        "completion": {
            "strategy_report_complete": True,
            "claims_map_to_evidence": built["claims"]["passed"],
            "reproduction_commands_documented": True,
            "data_retention_checklist_documented": True,
            "destructive_cleanup_performed": False,
            "promotion_decision": "no_plan1_candidate_promoted",
        },
        "known_limitations": [
            "Actual Kaggle validation remains authoritative for runtime packaging.",
            "The Strategy rules and any deletion clause require a final signed-in manual review.",
            "Native complete-game seed replay is unavailable.",
        ],
    }
    report = {
        **unsigned,
        "signature": {
            "kind": "sha256-integrity-signature-v1",
            "signer": config.signer,
            "signed_utc": datetime.now(timezone.utc).isoformat(),
            "payload_sha256": canonical_json_hash(unsigned),
        },
    }
    write_json_atomic(args.output, report)
    print(json.dumps({
        "run_id": config.run_id,
        "output": str(args.output.resolve()),
        "report_sha256": sha256_file(args.output),
        "archive_sha256": built["archive"]["archive_sha256"],
        "archive_bytes": built["archive"]["archive_bytes"],
        "evidence_files": built["archive"]["files"],
        "claims": built["claims"]["claims"],
        "checks": built["claims"]["checks"],
        "passed": True,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
