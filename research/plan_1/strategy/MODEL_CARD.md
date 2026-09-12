# Model Card: Phase 8 Candidate i001

## Identity

- Model family: hashed linear policy-value model.
- Model version: `hashed-linear-policy-value-v1`.
- Feature dimension: 8,192.
- Checkpoint: `plan_1/artifacts/phase8/phase8-validation-v1/checkpoints/candidate-i001.json`.
- Checkpoint SHA-256: `201111f01da276b4fe8e0c4ab623d563fa0ad5da0f81f4b96368b8bae1ead36c`.
- Search configuration: `plan_1/configs/mcts_selective_budget.json`.
- Status: research candidate; rejected for submission promotion.

## Intended use

The checkpoint supplies legal-action priors and a bounded leaf value to Plan
1's PUCT search. It is intended for controlled Pokemon TCG simulator research,
ablation, and reproducibility. It is not approved as a replacement for the
active competition agent.

## Training data

The model was warm-started from the Phase 7 heuristic corpus and updated in the
first Phase 8 self-play iteration. Data is split by complete game, not by
individual decision. Evaluation games are excluded from training readers.
Inputs contain public observations and legal action features; sampled oracle
hidden-card identity is excluded from policy features.

The complete Phase 8 run accumulated 24 new games and 2,648 decisions. Only 279
decisions had completed PUCT targets, while 2,369 used fallback/teacher targets.
This teacher dominance is a central limitation.

## Evaluation

The candidate won its small Phase 8 internal screen 5-3 and became the internal
champion. That result was not considered submission-grade evidence. With the
Phase 10 selective-budget search configuration, the exact checkpoint was later
evaluated in Phase 9 across 960 multi-deck games and conclusively rejected:

- Development: 139 wins, 186 losses, 35 draws.
- Held-out: 184 wins, 282 losses, 14 draws.
- Worst matchup decisive win rate: 11.11%.
- Promotion decision: rejected.

## Deployment profile

Phase 11 packaged the model as strict JSON with checksum validation. Local
fresh-process model load was 4.11 ms. Twelve shadow games completed without
faults; 815 agent decisions measured 19.24 ms p95 and 80.64 ms maximum. Missing
or corrupt model files disable learned inference and retain heuristic MCTS.

## Limitations and risks

- The model mostly learned teacher/fallback behavior.
- Its linear representation has limited capacity for long tactical sequences.
- Value estimates are weakly calibrated across heterogeneous deck engines.
- Search can amplify evaluator error rather than correct it.
- Results do not generalize reliably across the frozen deck field.
- The checkpoint must not be called a promoted champion or leaderboard gain.

## Decision

Retain for reproducibility and future ablation. Do not submit without a new
training mechanism and a fresh Phase 9 promotion pass.
