from __future__ import annotations

import math
import unittest
from dataclasses import replace

import _path  # noqa: F401

from plan1.evaluation import NONTERMINAL_BOUND, TERMINAL_SCORE, HandcraftedEvaluator
from plan1.evaluation.tactical import run_tactical_suite, synthetic_catalog, tactical_fixtures
from plan1.game.records import CardRecord, PublicObservationRecord


class HandcraftedEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluator = HandcraftedEvaluator(synthetic_catalog())

    def test_all_named_tactical_fixtures_pass(self) -> None:
        report = run_tactical_suite(self.evaluator)
        failed = [fixture for fixture in report["fixtures"] if not fixture["passed"]]
        self.assertEqual(failed, [])
        self.assertTrue(report["passed"])

    def test_perspective_is_exactly_antisymmetric(self) -> None:
        for fixture in tactical_fixtures():
            for observation in (fixture.preferred, fixture.rejected):
                score0 = self.evaluator.evaluate(observation, 0).total
                score1 = self.evaluator.evaluate(observation, 1).total
                self.assertAlmostEqual(score0, -score1, places=9, msg=fixture.name)

    def test_terminal_scores_override_nonterminal_bound(self) -> None:
        fixture = tactical_fixtures()[0]
        win = self.evaluator.evaluate(fixture.preferred, 0)
        nonterminal = self.evaluator.evaluate(fixture.rejected, 0)
        self.assertEqual(win.total, TERMINAL_SCORE)
        self.assertLess(abs(nonterminal.total), NONTERMINAL_BOUND)

    def test_component_values_reconstruct_total(self) -> None:
        observation = tactical_fixtures()[2].preferred
        result = self.evaluator.evaluate(observation, 0)
        self.assertAlmostEqual(result.total, sum(component.value for component in result.components), places=9)
        self.assertTrue(math.isfinite(result.total))

    def test_scalar_path_matches_detailed_breakdown(self) -> None:
        for fixture in tactical_fixtures():
            for observation in (fixture.preferred, fixture.rejected):
                for perspective in (0, 1):
                    self.assertAlmostEqual(
                        self.evaluator.score(observation, perspective),
                        self.evaluator.evaluate(observation, perspective).total,
                        places=9,
                        msg=fixture.name,
                    )

    def test_missing_state_is_neutral_and_diagnostic(self) -> None:
        result = self.evaluator.evaluate(PublicObservationRecord(1, None, (), None), 0)
        self.assertEqual(result.total, 0.0)
        self.assertEqual(result.diagnostics, ("missing_state",))

    def test_dynamic_attack_text_is_reported(self) -> None:
        fixture = next(item for item in tactical_fixtures() if item.name == "evolution_in_hand_ready")
        state = fixture.preferred.state
        evolved = replace(state.players[0].active[0], card_id=6, hp=170, max_hp=170, energies=(1,))
        player = replace(state.players[0], active=(evolved,))
        observation = replace(fixture.preferred, state=replace(state, players=(player, state.players[1])))
        result = self.evaluator.evaluate(observation, 0)
        self.assertIn("dynamic_attack_damage_approximated", result.diagnostics)

    def test_sleep_blocks_active_attack_readiness(self) -> None:
        fixture = next(item for item in tactical_fixtures() if item.name == "stall_break_ready_attacker")
        state = fixture.preferred.state
        asleep = replace(state.players[0], asleep=True)
        observation = replace(fixture.preferred, state=replace(state, players=(asleep, state.players[1])))
        awake_score = self.evaluator.evaluate(fixture.preferred, 0)
        asleep_score = self.evaluator.evaluate(observation, 0)
        self.assertLess(asleep_score.component("ready_attackers"), awake_score.component("ready_attackers"))
        self.assertLess(asleep_score.component("retreat_flexibility"), awake_score.component("retreat_flexibility"))

    def test_new_pokemon_is_not_counted_as_evolution_ready(self) -> None:
        fixture = next(item for item in tactical_fixtures() if item.name == "evolution_in_hand_ready")
        state = fixture.preferred.state
        fresh_active = replace(state.players[0].active[0], appear_this_turn=True)
        player = replace(state.players[0], active=(fresh_active,))
        observation = replace(fixture.preferred, state=replace(state, players=(player, state.players[1])))
        result = self.evaluator.evaluate(observation, 0)
        self.assertEqual(result.component("evolution_ready"), 0.0)

    def test_used_once_per_turn_actions_lose_availability(self) -> None:
        fixture = next(item for item in tactical_fixtures() if item.name == "retreat_escape_available")
        state = fixture.preferred.state
        supporter_card = CardRecord(card_id=21, serial=20_001, player_index=0)
        supporter = replace(state.players[0], hand=(supporter_card,), hand_count=1)
        base = replace(fixture.preferred, state=replace(state, players=(supporter, state.players[1])))
        used = replace(base, state=replace(base.state, supporter_played=True, retreated=True))
        self.assertLess(
            self.evaluator.evaluate(used, 0).component("supporter_access"),
            self.evaluator.evaluate(base, 0).component("supporter_access"),
        )
        self.assertLess(
            self.evaluator.evaluate(used, 0).component("retreat_flexibility"),
            self.evaluator.evaluate(base, 0).component("retreat_flexibility"),
        )

    def test_invalid_perspective_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.evaluator.evaluate(tactical_fixtures()[0].preferred, 2)


if __name__ == "__main__":
    unittest.main()
