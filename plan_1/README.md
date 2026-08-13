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
- Next: Phase 5 belief model and information-set MCTS.
- Phase 4 is infrastructure-complete but its heuristic-MCTS candidate was not promoted: the bounded Hydrapple screen was 15-25 against the current agent.
- Neural-model and RL dependencies are intentionally not installed yet.

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
python -m unittest discover -s plan_1/tests -v
```

Generated manifests and conformance reports are written under
`plan_1/artifacts/`. Large future checkpoints, traces, and trajectories are
ignored by Git.
