# Plan 1 implementation

This directory implements the information-set MCTS and policy-value RL track
specified in [`../Plan_1.md`](../Plan_1.md).

The active competition submission is not imported or modified by this package.
Plan 1 candidates are promoted only after the evaluation and packaging gates in
the specification pass.

## Current phase

- Phase 0: environment, configuration, and reproducibility foundation.
- Phase 1: native search lifecycle wrapper and conformance probes.
- Phase 2: immutable public observations, card catalog, and complete legal-action candidates.
- Phase 3: versioned handcrafted evaluator, score breakdowns, tactical fixtures, and live-state performance gate.
- Phase 4: bounded UCT, lifecycle-safe simulation, conservative fallback, traces, soak validation, and horizon ablation.
- Phase 5: public-card accounting, constrained deck-mixture beliefs, public information-set keys, root-sampled ISMCTS, and an offline-only oracle diagnostic.
- Phase 6: strict game/decision schemas, deterministic compressed trajectories, atomic publication, hash-chained manifests, game-level splits, replay validation, quarantine, retention, and resumable heuristic corpus generation.
- Phase 7: dependency-free hashed policy-value bootstrap, legal-action masking, game-isolated train/validation/test data, validation-only value calibration, checksum-protected checkpoints, CPU inference, and optional PUCT integration.
- Phase 8: spawned self-play workers, one-writer immutable trajectories, visit-temperature exploration, bounded historical replay, warm-start learning, validation-only calibration, candidate/champion evaluation, atomic resume state, and reproducible internal promotion/rejection.
- Phase 9: frozen historical-checkpoint league, development/held-out deck separation, Plan 2 specialist integration, seat-balanced cross-deck matches, atomic matchup resume, Wilson-strength gates, forgetting checks, and dominance-cycle analysis.
- Phase 10: measured search telemetry, causal selective-root/budget ablations, fresh multi-deck confirmation, Phase 9 transfer screen, frozen-corpus model-size comparison, and deterministic gzip export verification.
- Phase 11: deterministic exact-candidate package, strict file manifest, clean-process import/model/fallback probes, complete shadow games, runtime limits, frozen-evidence binding, and an integrity-signed promotion decision.
- Phase 12: evidence-backed Strategy report, model card, reproducibility guide, data-retention checklist, structured claim verification, deterministic evidence archive, and integrity-signed archival report.
- Next: Plan 1 requires a new model/training candidate before another Phase 9 promotion attempt. Final signed-in competition-rules review and actual Kaggle package validation remain manual release gates.
- Phase 4 is infrastructure-complete but its heuristic-MCTS candidate was not promoted: the bounded Hydrapple screen was 15-25 against the current agent.
- Phase 5 is infrastructure-complete but not promoted: its 64-decision validation establishes consistency and leakage safety, not playing strength or deployment latency.
- Phase 6 is data-infrastructure complete. Exact canonical record replay is verified; native game re-simulation remains unavailable because the local engine exposes no battle-seed input.
- Phase 7 passes its supervised and PUCT non-inferiority gates but remains an isolated research candidate; its 20-game 12-8 screen is not a submission promotion result.
- Phase 8 passes its three-iteration infrastructure gates and verified interruption/resume. Its 5-3 / 3-5 / 4-4 evaluation screens are too small for submission promotion, and only 10.54% of stored decisions currently carry completed PUCT targets.
- Phase 9's promotion-sized rerun used 960 games across 40 matchups. The Phase 10 selective-budget candidate was conclusively rejected: 139-186 with 35 draws on development and 184-282 with 14 draws on held-out decks; both aggregate Wilson lower bounds missed their mandatory strength floors. Six draw-heavy Grass matchups remained below the per-match decisive minimum, but that cannot reverse the powered aggregate strength failure.
- Phase 10 selects `mcts_selective_budget.json` for further research after a fresh 30-23 / 7-draw confirmation and improved Phase 9 transfer screen. The result is not statistically conclusive (`p=0.336`) and does not clear Phase 9 promotion. A 2,048-feature checkpoint is the packaging-size recommendation, not a playing candidate.
- Phase 11 packages the exact rejected Phase 9 candidate rather than substituting the separate 2,048-feature experiment. Its 144,042-byte archive passed manifest integrity, fresh-process import/model loading, missing/corrupt-model fallback, and 12/12 shadow games. Across 815 packaged-agent decisions, p95 latency was 19.24 ms and maximum latency was 80.64 ms. Packaging passed; promotion remains rejected on the 960-game Phase 9 evidence.
- Phase 12 verifies 10 Strategy claims through 20 exact evidence checks and archives 189 reproducibility files in a deterministic 896,933-byte ZIP. Two builds matched SHA-256 `6a4bae2cc717f20645fdc9268c3cc3d0bd57c8ac38418a98958094916db5ef41`. The report is complete, but it honestly concludes that no Plan 1 policy cleared promotion.
- Neural-model and RL dependencies are intentionally not installed yet. The Phase 7 bootstrap uses only the Python standard library.

## Commands

Run these from the repository root with Python 3.11 or newer:

```powershell
python plan_1/scripts/verify_environment.py
python plan_1/scripts/capture_baseline.py
python plan_1/scripts/run_conformance.py --deck Decs/Hydrapple.csv
python plan_1/scripts/run_phase1_suite.py
python plan_1/scripts/run_process_probe.py --workers 2 --sessions 500
python plan_1/scripts/run_phase2_suite.py
python plan_1/scripts/run_phase3_suite.py
python plan_1/scripts/run_phase4_suite.py soak --games 500 --output plan_1/artifacts/reports/phase4-soak-final-v4.json
python plan_1/scripts/run_phase4_suite.py ablation --deck Decs/Hydrapple.csv --games 40 --output plan_1/artifacts/reports/phase4-bounded-screen-h0-v2.json
python plan_1/scripts/run_phase4_suite.py horizon-ablation --deck Decs/Hydrapple.csv --games 60 --output plan_1/artifacts/reports/phase4-horizon-ablation-bounded-v2.json
python plan_1/scripts/run_phase5_suite.py --decisions 64 --determinizations 4 --time-budget-ms 80 --cleanup-reserve-ms 16 --simulations 16 --nodes 96 --output plan_1/artifacts/reports/phase5-suite.json
python plan_1/scripts/run_phase6_suite.py --games 8 --evaluation-games 2 --run-id phase6-final-v3 --corpus-root plan_1/artifacts/trajectories/phase6-validation-v3 --scratch-root plan_1/artifacts/tmp/phase6-corruption-v3 --output plan_1/artifacts/reports/phase6-suite.json
python plan_1/scripts/run_phase7_suite.py --corpus-games 48 --screen-games 20 --run-id phase7-bootstrap-v1 --corpus-root plan_1/artifacts/trajectories/phase7-bootstrap --checkpoint plan_1/artifacts/checkpoints/phase7-bootstrap-v2.json --output plan_1/artifacts/reports/phase7-suite-v2.json
python plan_1/scripts/run_phase8_loop.py --config plan_1/configs/phase8_reinforcement.json --stop-after-stage selfplay
python plan_1/scripts/run_phase8_loop.py --config plan_1/configs/phase8_reinforcement.json
python plan_1/scripts/run_phase9_suite.py --config plan_1/configs/phase9_league.json --validate-only
python plan_1/scripts/run_phase9_suite.py --config plan_1/configs/phase9_league.json --output plan_1/artifacts/reports/phase9-suite.json
python plan_1/scripts/run_phase10_suite.py --config plan_1/configs/phase10_optimization.json --output plan_1/artifacts/reports/phase10-suite.json
python plan_1/scripts/run_phase10_suite.py --config plan_1/configs/phase10_confirmation.json --output plan_1/artifacts/reports/phase10-confirmation.json --search-only
python plan_1/scripts/run_phase9_suite.py --config plan_1/configs/phase9_optimized_screen.json --output plan_1/artifacts/reports/phase9-optimized-screen.json
python plan_1/scripts/run_phase9_suite.py --config plan_1/configs/phase9_promotion_gate.json --output plan_1/artifacts/reports/phase9-promotion-gate.json --workers 4
python plan_1/scripts/run_phase11_suite.py --config plan_1/configs/phase11_deployment.json --validate-only
python plan_1/scripts/run_phase11_suite.py --config plan_1/configs/phase11_deployment.json --output plan_1/artifacts/reports/phase11-shadow-validation.json
python plan_1/scripts/run_phase12_archive.py --config plan_1/configs/phase12_archive.json --validate-only
python plan_1/scripts/run_phase12_archive.py --config plan_1/configs/phase12_archive.json --output plan_1/artifacts/reports/phase12-archive.json
python -m unittest discover -s plan_1/tests -v
```

Generated manifests and conformance reports are written under
`plan_1/artifacts/`. Large future checkpoints, traces, and trajectories are
ignored by Git.
