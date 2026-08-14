# Plan 1 Reproducibility Guide

## Environment

- Python 3.11 or newer.
- Windows-compatible process spawning.
- Competition `cg` simulator available under
  `sample_submission/sample_submission/cg` for local runs.
- No neural framework is required; the learner and inference path use the
  Python standard library.

Create or activate the Plan 1 environment, then verify it:

```powershell
python plan_1/scripts/verify_environment.py
python -m unittest discover -s plan_1/tests -v
```

## Core validation

```powershell
python plan_1/scripts/run_conformance.py --deck Decs/Hydrapple.csv
python plan_1/scripts/run_phase3_suite.py
python plan_1/scripts/run_phase4_suite.py soak --games 500 --output plan_1/artifacts/reports/phase4-soak-final-v4.json
python plan_1/scripts/run_phase5_suite.py --decisions 64 --determinizations 4 --time-budget-ms 80 --cleanup-reserve-ms 16 --simulations 16 --nodes 96 --output plan_1/artifacts/reports/phase5-suite.json
```

## Data, learning, and self-play

```powershell
python plan_1/scripts/run_phase6_suite.py --games 8 --evaluation-games 2 --run-id phase6-final-v3 --corpus-root plan_1/artifacts/trajectories/phase6-validation-v3 --scratch-root plan_1/artifacts/tmp/phase6-corruption-v3 --output plan_1/artifacts/reports/phase6-suite.json
python plan_1/scripts/run_phase7_suite.py --corpus-games 48 --screen-games 20 --run-id phase7-bootstrap-v1 --corpus-root plan_1/artifacts/trajectories/phase7-bootstrap --checkpoint plan_1/artifacts/checkpoints/phase7-bootstrap-v2.json --output plan_1/artifacts/reports/phase7-suite-v2.json
python plan_1/scripts/run_phase8_loop.py --config plan_1/configs/phase8_reinforcement.json
```

## Frozen evaluation

The Phase 9 runner resumes matching cached matchup files only when config hash,
pairing identity, and game count match. To reproduce the preserved report from
the current archive:

```powershell
python plan_1/scripts/run_phase9_suite.py --config plan_1/configs/phase9_promotion_gate.json --output plan_1/artifacts/reports/phase9-promotion-gate.json --workers 4
```

To force genuinely fresh evidence, create a new config with a new `run_id` and
fresh output path. Do not delete the preserved run merely to bypass resume.

## Packaging and archive verification

```powershell
python plan_1/scripts/run_phase11_suite.py --config plan_1/configs/phase11_deployment.json --output plan_1/artifacts/reports/phase11-shadow-validation.json
python plan_1/scripts/run_phase12_archive.py --config plan_1/configs/phase12_archive.json --output plan_1/artifacts/reports/phase12-archive.json
```

The Phase 12 command verifies every structured claim before publishing the
archive. It then writes a deterministic ZIP and an integrity-signed report.

## Reproduction boundaries

Native battle seed control is not exposed, so complete games are not guaranteed
to replay bit-for-bit. Reproducibility instead covers source/config/checkpoint
identity, deterministic schedules, seat balancing, immutable raw outcomes,
strict resume checks, and statistical recomputation. The actual Kaggle runtime
remains the authority for final package validation.
