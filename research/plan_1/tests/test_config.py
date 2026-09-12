from __future__ import annotations

import copy
import unittest

import _path  # noqa: F401

from plan1.config import ConfigError, parse_config


VALID = {
    "schema_version": 1,
    "search": {
        "max_simulations": 10,
        "max_depth": 5,
        "max_nodes": 50,
        "max_candidates": 8,
        "time_budget_ms": 100,
        "exploration_constant": 1.4,
        "horizon_turns": 1,
        "progressive_widening_base": 2.0,
        "progressive_widening_exponent": 0.5,
        "value_scale": 10000.0,
        "discount_factor": 1.0,
        "require_full_root_coverage": True,
    },
    "safety": {"cleanup_reserve_ms": 10, "allow_manual_coin": False, "fallback_on_error": True},
    "reproducibility": {"seed": 0, "record_dirty_worktree": True},
}


class ConfigTests(unittest.TestCase):
    def test_valid_config(self) -> None:
        config = parse_config(copy.deepcopy(VALID))
        self.assertEqual(config.search.max_simulations, 10)
        self.assertEqual(config.search.horizon_turns, 1)
        self.assertFalse(config.safety.allow_manual_coin)

    def test_unknown_key_rejected(self) -> None:
        value = copy.deepcopy(VALID)
        value["search"]["surprise"] = 1
        with self.assertRaisesRegex(ConfigError, "unknown keys"):
            parse_config(value)

    def test_manual_coin_cannot_be_enabled(self) -> None:
        value = copy.deepcopy(VALID)
        value["safety"]["allow_manual_coin"] = True
        with self.assertRaisesRegex(ConfigError, "must be false"):
            parse_config(value)

    def test_cleanup_reserve_must_fit_budget(self) -> None:
        value = copy.deepcopy(VALID)
        value["safety"]["cleanup_reserve_ms"] = 100
        with self.assertRaisesRegex(ConfigError, "smaller"):
            parse_config(value)

    def test_progressive_widening_exponent_is_bounded(self) -> None:
        value = copy.deepcopy(VALID)
        value["search"]["progressive_widening_exponent"] = 1.1
        with self.assertRaisesRegex(ConfigError, "must be in"):
            parse_config(value)

    def test_full_root_coverage_flag_must_be_boolean(self) -> None:
        value = copy.deepcopy(VALID)
        value["search"]["require_full_root_coverage"] = 1
        with self.assertRaisesRegex(ConfigError, "must be boolean"):
            parse_config(value)


if __name__ == "__main__":
    unittest.main()
