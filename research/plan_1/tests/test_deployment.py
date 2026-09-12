from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _path import SOURCE_ROOT
from plan1.deployment.config import DeploymentConfigError, load_deployment_config
from plan1.deployment.package import build_submission_package, verify_submission_package


class DeploymentTests(unittest.TestCase):
    def _fixture(self, root: Path) -> Path:
        (root / "deck.csv").write_text("\n".join(["1"] * 60) + "\n", encoding="utf-8")
        (root / "fallback.py").write_text("def agent(obs): return []\n", encoding="utf-8")
        (root / "search.json").write_text("{}\n", encoding="utf-8")
        (root / "model.json").write_text("{}\n", encoding="utf-8")
        (root / "frozen.json").write_text("{}\n", encoding="utf-8")
        config = {
            "schema_version": 1,
            "run_id": "test-phase11",
            "package_name": "submission",
            "deck_path": str(root / "deck.csv"),
            "fallback_path": str(root / "fallback.py"),
            "search_config_path": str(root / "search.json"),
            "checkpoint_path": str(root / "model.json"),
            "frozen_evaluation_path": str(root / "frozen.json"),
            "output_root": str(root / "output"),
            "archive_path": str(root / "output" / "submission.zip"),
            "shadow_games": 2,
            "max_steps": 10,
            "signer": "test",
            "runtime_limits": {
                "maximum_archive_bytes": 1000000,
                "maximum_import_ms": 1000,
                "maximum_model_load_ms": 500,
                "maximum_decision_p95_ms": 50,
                "maximum_decision_ms": 250
            }
        }
        path = root / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def test_package_is_deterministic_and_manifest_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = load_deployment_config(self._fixture(root))
            first = build_submission_package(config, source_root=SOURCE_ROOT)
            second = build_submission_package(config, source_root=SOURCE_ROOT)
            self.assertEqual(first["archive_sha256"], second["archive_sha256"])
            self.assertTrue(verify_submission_package(Path(second["package_root"]))["passed"])

    def test_manifest_detects_file_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = load_deployment_config(self._fixture(root))
            result = build_submission_package(config, source_root=SOURCE_ROOT)
            package = Path(result["package_root"])
            (package / "deck.csv").write_text("2\n", encoding="utf-8")
            self.assertFalse(verify_submission_package(package)["passed"])

    def test_unknown_config_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._fixture(root)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["unexpected"] = True
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(DeploymentConfigError):
                load_deployment_config(path)


if __name__ == "__main__":
    unittest.main()
