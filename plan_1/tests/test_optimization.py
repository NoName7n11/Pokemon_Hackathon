from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401

from plan1.optimization.config import load_optimization_config
from plan1.optimization.suite import _gzip_export, _head_to_head_statistics, _search_analysis


class OptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[2]
        cls.config = load_optimization_config(root / "plan_1" / "configs" / "phase10_optimization.json")

    def test_config_preserves_causal_variant_order(self) -> None:
        self.assertEqual(
            [variant.name for variant in self.config.search_variants],
            ["full_root_baseline", "selective_root", "selective_budget"],
        )

    def test_gzip_export_is_exact_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "model.json"
            source.write_text('{"test":1}\n', encoding="ascii")
            first = _gzip_export(source, root / "first.json.gz")
            second = _gzip_export(source, root / "second.json.gz")
            self.assertTrue(first["roundtrip_exact"])
            self.assertEqual(first["gzip_sha256"], second["gzip_sha256"])

    def test_small_search_screen_cannot_clear_evidence_gate(self) -> None:
        matches = []
        variants = [variant.name for variant in self.config.search_variants]
        for index, (left, right) in enumerate(((variants[0], variants[1]), (variants[0], variants[2]))):
            trace = {
                "searched_decisions": 10,
                "full_root_coverage": 10,
                "chose_non_fallback": 10,
                "hard_deadline_overruns": 0,
                "fallback_reasons": {},
            }
            timing = {"p95_ms": 10.0}
            matches.append({
                "matchup_id": str(index), "left_variant": left, "right_variant": right,
                "left_wins": 0, "right_wins": 2, "draws": 0,
                "left_search": trace, "right_search": trace,
                "left_timing": timing, "right_timing": timing,
                "faults": {}, "errors": [],
            })
        result = _search_analysis(self.config, matches)
        self.assertIsNone(result["recommended_research_variant"])
        self.assertEqual(result["decision"], "keep_baseline")

    def test_head_to_head_statistics_report_uncertainty(self) -> None:
        result = _head_to_head_statistics(30, 23)
        self.assertLess(result["wilson_95"][0], 0.5)
        self.assertGreater(result["p_value_two_sided"], 0.05)


if __name__ == "__main__":
    unittest.main()
