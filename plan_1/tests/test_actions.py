from __future__ import annotations

import unittest

import _path  # noqa: F401

from plan1.game.actions import ActionGenerationError, ActionGenerator, validate_action
from plan1.game.records import OptionRecord, SelectionRecord


def option(card_id: int) -> OptionRecord:
    return OptionRecord(3, None, 2, 0, 0, None, None, None, None, None, None, card_id, card_id, None)


def selection(count: int, minimum: int, maximum: int, context: int = 0, select_type: int = 1) -> SelectionRecord:
    return SelectionRecord(select_type, context, minimum, maximum, 0, 0, tuple(option(i + 1) for i in range(count)), None, None, None)


class ActionTests(unittest.TestCase):
    def test_single_choice_is_exhaustive(self) -> None:
        result = ActionGenerator().generate(selection(3, 1, 1))
        self.assertTrue(result.exhaustive)
        self.assertEqual([candidate.indices for candidate in result.candidates], [(0,), (1,), (2,)])

    def test_optional_selection_includes_empty_action(self) -> None:
        result = ActionGenerator().generate(selection(2, 0, 1))
        self.assertEqual([candidate.indices for candidate in result.candidates], [(), (0,), (1,)])

    def test_unordered_multi_select_is_canonical(self) -> None:
        result = ActionGenerator().generate(selection(3, 2, 2), preferred_indices=[2, 0])
        self.assertEqual(result.candidates[0].indices, (0, 2))
        self.assertEqual(result.total_action_count, 3)

    def test_skill_order_preserves_permutations(self) -> None:
        result = ActionGenerator().generate(selection(3, 2, 2, context=34, select_type=5))
        self.assertTrue(result.ordered)
        self.assertEqual(result.total_action_count, 6)
        values = {candidate.indices for candidate in result.candidates}
        self.assertIn((0, 1), values)
        self.assertIn((1, 0), values)

    def test_large_space_is_bounded_deterministically(self) -> None:
        generator = ActionGenerator(max_candidates=32)
        first = generator.generate(selection(20, 10, 10), seed=44)
        second = generator.generate(selection(20, 10, 10), seed=44)
        self.assertFalse(first.exhaustive)
        self.assertEqual(len(first.candidates), 32)
        self.assertEqual(first.candidates, second.candidates)
        self.assertEqual(len({candidate.fingerprint for candidate in first.candidates}), 32)

    def test_unknown_pattern_is_logged_but_still_safe(self) -> None:
        result = ActionGenerator().generate(selection(2, 1, 1, context=99, select_type=99))
        self.assertIn("unknown_select_type:99", result.issues)
        self.assertIn("unknown_select_context:99", result.issues)
        for candidate in result.candidates:
            validate_action(selection(2, 1, 1, context=99, select_type=99), candidate.indices)

    def test_invalid_bounds_fail_closed(self) -> None:
        with self.assertRaises(ActionGenerationError):
            ActionGenerator().generate(selection(2, 3, 3))

    def test_masks_match_selected_indices(self) -> None:
        candidate = ActionGenerator().generate(selection(3, 2, 2), preferred_indices=[0, 2]).candidates[0]
        self.assertEqual(candidate.option_mask, (True, False, True))


if __name__ == "__main__":
    unittest.main()
