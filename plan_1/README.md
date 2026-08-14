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
- Next: Phase 8 AlphaZero-style reinforcement loop.
- Phase 4 is infrastructure-complete but its heuristic-MCTS candidate was not promoted: the bounded Hydrapple screen was 15-25 against the current agent.
- Phase 5 is infrastructure-complete but not promoted: its 64-decision validation establishes consistency and leakage safety, not playing strength or deployment latency.
- Phase 6 is data-infrastructure complete. Exact canonical record replay is verified; native game re-simulation remains unavailable because the local engine exposes no battle-seed input.
- Phase 7 passes its supervised and PUCT non-inferiority gates but remains an isolated research candidate; its 20-game 12-8 screen is not a submission promotion result.
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
python -m unittest discover -s plan_1/tests -v
```

Generated manifests and conformance reports are written under
`plan_1/artifacts/`. Large future checkpoints, traces, and trajectories are
ignored by Git.
