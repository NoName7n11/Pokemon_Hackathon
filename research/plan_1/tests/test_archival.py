from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from plan1.archival import (
    ArchiveError,
    build_evidence_archive,
    json_path_value,
    load_archive_config,
    verify_archive,
    verify_claims,
)


class ArchivalTests(unittest.TestCase):
    def _fixture(self, root: Path) -> Path:
        (root / "docs").mkdir()
        (root / "evidence").mkdir()
        (root / "docs" / "report.md").write_text("# Report\n", encoding="utf-8")
        (root / "evidence" / "result.json").write_text(
            json.dumps({"gate": {"passed": True}, "games": 10}), encoding="utf-8"
        )
        claims = {
            "schema_version": 1,
            "claims": [{
                "id": "test",
                "statement": "fixture passed",
                "evidence": [{
                    "path": "evidence/result.json",
                    "json_path": "gate.passed",
                    "expected": True,
                }],
            }],
        }
        (root / "claims.json").write_text(json.dumps(claims), encoding="utf-8")
        config = {
            "schema_version": 1,
            "run_id": "archive-test",
            "claims_path": "claims.json",
            "manifest_path": "output/manifest.json",
            "archive_path": "output/evidence.zip",
            "signer": "test",
            "include_globs": ["docs/*.md", "evidence/*.json", "claims.json"],
        }
        path = root / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def test_json_path_value_supports_objects_and_lists(self) -> None:
        self.assertEqual(json_path_value({"a": [{"b": 3}]}, "a.0.b"), 3)

    def test_claim_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = load_archive_config(self._fixture(root))
            evidence = root / "evidence" / "result.json"
            evidence.write_text(json.dumps({"gate": {"passed": False}}), encoding="utf-8")
            claims = verify_claims(root / config.claims_path, repo_root=root)
            self.assertFalse(claims["passed"])
            with self.assertRaises(ArchiveError):
                build_evidence_archive(config, repo_root=root)

    def test_archive_is_deterministic_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = load_archive_config(self._fixture(root))
            first = build_evidence_archive(config, repo_root=root)
            second = build_evidence_archive(config, repo_root=root)
            self.assertEqual(first["archive"]["archive_sha256"], second["archive"]["archive_sha256"])
            self.assertTrue(verify_archive(root / config.archive_path, root / config.manifest_path)["passed"])


if __name__ == "__main__":
    unittest.main()
