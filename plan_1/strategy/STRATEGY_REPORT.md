# Plan 1 Strategy Report

## Executive summary

Plan 1 investigated whether a root-sampled information-set Monte Carlo Tree
Search (ISMCTS) policy, guided by a compact learned policy-value model, could
improve a deterministic Pokemon TCG agent under the competition simulator's
legal-action API.

The project produced a complete research pipeline: native-search conformance,
immutable public observations, bounded legal-action generation, a transparent
position evaluator, time-bounded UCT/PUCT, constrained hidden-card beliefs,
versioned trajectories, a dependency-free policy-value learner, resumable
self-play, a frozen multi-deck league, causal search ablations, and deterministic
submission packaging.

The final research candidate was deployable but not strong enough. Its
promotion-sized Phase 9 evaluation contained 960 games across 40 seat-balanced
matchups. It scored 139-186 with 35 draws on development decks and 184-282 with
14 draws on held-out decks. The promotion gate conclusively rejected it. Phase
11 subsequently proved that this exact rejected candidate could be packaged and
run safely, but did not replace the active submission.

This distinction is the main conclusion: search and RL infrastructure can be
correct, reproducible, and deployment-safe while the learned policy still fails
to improve playing strength.

## Problem formulation

The agent receives an observation containing public game state and a bounded
selection of legal options. It returns option indices. Hidden hands, decks, and
prizes make the game an imperfect-information planning problem. The legal action
space is also state-dependent and includes optional and multi-select decisions.

Plan 1 therefore treated the task as an information-set search problem rather
than a fixed-action classification problem:

1. Convert only legally observable state into immutable records.
2. Generate complete legal selections under explicit candidate limits.
3. Sample hidden states consistent with public card accounting.
4. Share search statistics by public information-set identity.
5. Use MCTS visit counts as policy targets and game outcomes as value targets.
6. Keep deterministic heuristic fallback behavior available at every boundary.

## System architecture

The system is divided into six operational layers.

### Engine safety

`plan1.engine` wraps native search sessions with explicit ownership and cleanup.
Every entered search session calls `search_end`, including exceptions. Parent,
child, release, chance, and process-isolation behavior was measured before MCTS
was built on top of the API.

### Public state and legal actions

`plan1.game` converts simulator objects into immutable public records. Opponent
hidden-card identities are excluded from policy observations and information-set
keys. `ActionGenerator` emits complete legal index tuples, preserves order only
for verified ordered contexts, and limits combinatorial decisions through
deterministic prefix generation plus seeded sampling.

### Evaluation and search

The handcrafted evaluator scores terminal outcomes, prize race, survivability,
attack readiness, board development, tempo, and immediate KO risk from one
declared player perspective. UCT supplies the initial tree policy; PUCT uses
learned legal-action priors when a checkpoint is available. Search is bounded by
time, nodes, simulations, depth, candidate count, and a reserved cleanup window.

### Hidden-information beliefs

The belief system subtracts public cards from declared deck multisets and
samples hidden zones while preserving observed counts. Root-sampled ISMCTS uses
one determinization per simulation while sharing node statistics by public
information-set key. An oracle extractor exists only for offline diagnostics and
is not reachable from the deployable policy.

### Learning and self-play

The model is a standard-library hashed linear policy-value model. It conditions
policy scores on legal action features and produces a bounded value estimate.
Trajectories are immutable, checksum-protected, game-split, and stored through a
single-writer replay pipeline. Phase 8 ran three resumable self-play/training
iterations and retained the first candidate as its internal champion.

### Evaluation and deployment

The league uses frozen checkpoints, deck splits, specialist agents, alternating
seats, Wilson intervals, minimum evidence counts, worst-matchup floors,
forgetting checks, and cycle detection. Deployment packages source, deck,
checkpoint, search config, and fallback behind a strict manifest. Learned model
failure disables inference and leaves heuristic MCTS available; broader runtime
failure falls back again to deterministic legal selection.

## Experimental progression

### Conformance before optimization

Phases 0-3 established environment identity, native lifecycle behavior, public
state conversion, action validity, and tactical evaluator invariants. These
phases intentionally made no playing-strength claim.

### Bounded search

Phase 4 showed that a lifecycle-safe, time-bounded UCT agent could complete a
500-game soak test. Its early strength screen lost to the existing heuristic.
Opponent-response search and KO-back awareness were retained as infrastructure,
not presented as a validated leaderboard improvement.

### Information-set search

Phase 5 validated constrained public-card sampling and shared information-set
statistics. This closed the hidden-information architecture gap but did not
establish that sampled beliefs improved win rate.

### Data and policy-value bootstrap

Phases 6-7 produced atomic trajectories and a compact dependency-free model.
The model beat uniform policy and constant-value references on its frozen
validation corpus. A small 12-8 search screen established non-inferiority only;
its sample was not large enough for submission promotion.

### Reinforcement loop

Phase 8 completed three self-play iterations. Only 279 of 2,648 new decisions
contained completed PUCT targets; the remaining 2,369 retained fallback/teacher
targets. Candidate screens were 5-3, 3-5, and 4-4. These were infrastructure
checks, not reliable strength evidence.

### Search optimization

Phase 10 isolated root-coverage and budget changes. The selective-budget variant
improved search exercise substantially and won a fresh 60-game confirmation
30-23 with seven draws. Its two-sided p-value was 0.336, so it was selected for
a larger rescreen rather than declared superior. A separate model-size study
found that 2,048 features reduced package size without degrading frozen-corpus
metrics, but that model was not substituted into the playing candidate.

### Generalization gate

Phase 9's final promotion run used the exact selective-budget candidate with the
8,192-feature Phase 8 checkpoint. Development and held-out aggregate samples
both failed their mandatory strength floors. The worst matchup win rate was
11.11%. No dominance cycle explained the failure. The candidate was rejected.

### Shadow deployment

Phase 11 packaged that exact rejected policy into a 144,042-byte archive. It
passed manifest checks, fresh-process import and model load, missing/corrupt
model degradation, and 12 full shadow games. Across 815 packaged-agent
decisions, latency was 19.24 ms p95 and 80.64 ms maximum. Packaging passed while
promotion remained rejected.

## Deck interaction

Deck choice and policy quality are coupled. The active heuristic was developed
around Hydrapple behavior, while the Plan 1 league deliberately added Grass,
Fire, Mega Lopunny, and Mega Gardevoir decks and deck-specific specialists.
Results varied sharply by deck: the final candidate was even on Hydrapple,
substantially weaker on Grass and Fire, and inconsistent on held-out decks.

This means a mirror-only benchmark would have hidden the main failure. The
research system does not claim deck independence, and it does not treat one
shared evaluator as equally calibrated for every ability loop, energy engine,
or attacker-development pattern.

## Important failures and lessons

1. More search was not automatically better. Early one-ply and bounded-MCTS
   variants exposed evaluator and horizon weaknesses.
2. Conservative full-root coverage made the search policy mostly reproduce its
   fallback. Phase 10 improved exercise, but greater policy control still did
   not produce reliable generalization.
3. The self-play corpus was dominated by fallback targets. A learner cannot
   substantially exceed its teacher when most targets encode teacher behavior.
4. Small internal promotion screens were too weak to predict the 960-game
   multi-deck result.
5. Grass ability loops and long games stressed generic assumptions that worked
   on bounded Hydrapple decisions.
6. Packaging success is orthogonal to playing strength. Phase 11 passed every
   local deployment gate for an agent that Phase 9 correctly rejected.

## Reproducibility

Every major configuration, report, checkpoint, source module, test, and deck
needed by the frozen evaluation is indexed by SHA-256 in the Phase 12 evidence
manifest. `claims.json` maps report statements to exact JSON paths and expected
values. `run_phase12_archive.py` refuses publication if a claim changes, an
evidence file is missing, or a file hash changes while the archive is built.

See `REPRODUCIBILITY.md` for commands and environment assumptions. The native
competition engine remains an external runtime dependency and must match the
competition SDK closely enough for exact game reproduction.

## Limitations

- The final Plan 1 candidate was rejected and is not the active submission.
- The learned model is a small linear bootstrap, not a mature AlphaZero-scale
  network.
- Hidden-card priors are constrained but not a calibrated opponent-archetype
  posterior.
- Native battle seed control is unavailable, so seat balancing and sample size
  reduce variance but do not provide bit-identical game replay.
- Several Grass games reached the step limit or drew, reducing per-match
  decisive evidence even though aggregate rejection was conclusive.
- Local shadow validation approximates Kaggle; an actual Kaggle validation
  episode is still the authoritative packaging test.
- The current public Strategy rules and judging rubric must be manually checked
  immediately before report submission.

## Compliance and data handling

The packaged agent requires no network access and reads only declared package
assets plus the competition-provided `cg` runtime. Oracle hidden state is not an
input to deployment or training records. Competition-derived raw data,
trajectories, checkpoints, and logs are inventoried in
`DATA_RETENTION_CHECKLIST.md`.

The official Simulation overview retrieved on 2026-08-14 specifies a top-level
`main.py` and `deck.csv` in a `.tar.gz`, a 197.7 MiB submission limit, 2 vCPUs,
12.2 GiB RAM, and an August 16, 2026 final submission deadline. The public rules
page did not expose a machine-readable post-competition deletion deadline.
Therefore no unsupported deletion date is asserted: a manual final-rules review
is a blocking checklist item before destructive cleanup or long-term retention.

Official sources:

- https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/overview/description
- https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/rules

## Final decision

Plan 1 is complete as a documented research track. It demonstrates a rigorous
way to build, test, reject, and package an information-set MCTS/RL agent. It does
not demonstrate a stronger submission policy. The active submission remains
unchanged until a future model or training iteration clears the frozen Phase 9
generalization gate and then repeats Phase 11 packaging validation.
