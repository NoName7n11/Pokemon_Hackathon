# Plan 1 - Information-Set MCTS and Policy-Value Reinforcement Learning

## Document status

- **Status:** Active. Phases 0 through 4 are implemented and verified. Phase 5,
  the belief model and information-set MCTS boundary, is next. The Phase 4
  heuristic-MCTS candidate remains isolated because it did not clear the
  playing-strength promotion gate.
- **Primary objective:** Build a competition-ready agent that combines information-set Monte Carlo Tree Search (MCTS) with a learned policy-value model, using the existing simulator and legal-action API.
- **Development rule:** The active submission remains unchanged until a candidate clears every correctness, performance, generalization, and packaging gate in this document.
- **Relationship to Plan 2:** Plan 1 supplies the shared search and learning system. Plan 2 deck specialists can later supply decks, heuristic policies, replay reviews, and evaluation opponents, but Plan 1 must remain independently reproducible.

## 1. Definition of success

Plan 1 is complete only when all of the following are true:

1. A legal-action environment adapter can reproduce games deterministically from recorded seeds and inputs.
2. A time-bounded MCTS agent can play complete games without illegal actions, leaked hidden information, unreleased search states, or timeout failures.
3. Hidden cards are handled through explicit beliefs and root sampling rather than oracle information.
4. A policy-value network can train from versioned trajectories and improve MCTS search efficiency or playing strength.
5. Self-play training is stable, resumable, measurable, and protected against overfitting to one deck or one opponent.
6. Candidate promotion is decided by a frozen, seat-balanced, multi-deck evaluation suite with statistical reporting.
7. The final inference package works in the actual Kaggle runtime without network access and within measured time, memory, and package-size constraints.
8. Every released model is traceable to its code commit, configuration, card-data hash, training-data manifest, seeds, and evaluation report.
9. The final Strategy report can reproduce the system, experiments, ablations, and conclusions without relying on undocumented manual steps.

## 2. Competition outcomes

### 2.1 Primary outcomes

- Improve the Model Score through stronger tactical planning and learned position evaluation.
- Generalize across multiple viable decks and opposing archetypes.
- Use search to reduce tactical mistakes such as missed attacks, poor promotions, avoidable knockouts, bad prize races, and wasteful energy placement.
- Produce defensible evidence that separates improvements from variance.

### 2.2 Secondary outcomes

- Reuse the same engine adapter and evaluation framework for deck-specialized agents.
- Produce interpretable search traces for human review.
- Create a reusable self-play corpus for future supervised and reinforcement-learning experiments.

### 2.3 Non-goals for the first release

- Reimplementing the Pokemon TCG simulator.
- Training a large language model.
- Learning directly from card images.
- Replacing legal-action generation supplied by the engine.
- Optimizing deck construction and game policy in one uncontrolled loop.
- Claiming an AlphaZero-equivalent system before information-set search, training, and evaluation are actually complete.

## 3. Known constraints and assumptions

### 3.1 Engine constraints

- Decisions are exposed as `SelectData` with variable `SelectType`, `SelectContext`, `minCount`, `maxCount`, and a variable option list.
- Actions are lists of selected option indices, not one fixed discrete action space.
- `search_begin`, `search_step`, `search_release`, and `search_end` expose forward simulation.
- Hidden zones must be supplied to `search_begin`; therefore the search system must maintain and sample a belief over hidden cards.
- The native search pointer appears process-global. Search workers must use separate processes until a conformance test proves a safer execution model.
- Search states must always be released. `search_end` must execute in a `finally` block for every root decision.
- Coin flips and other chance events must remain unbiased. `manual_coin` must never be used to select favorable outcomes in a competition agent.

### 3.2 Current machine constraints

- Development host: Windows, Python 3.11, Intel i7-1260P, 16 logical processors, NVIDIA MX550 and Intel integrated graphics.
- NumPy, PyTorch, ONNX Runtime, Gymnasium, and TensorBoard are not currently installed in the inspected environment.
- CPU execution is the required baseline. GPU acceleration is optional and cannot be assumed in deployment.
- Windows process spawning must be supported; workers cannot depend on Unix-only `fork` behavior.

### 3.3 Competition constraints

- The Simulation submission is `main.py` plus `deck.csv`; the active submission must remain compact and self-contained.
- External network access must not be required at inference time.
- The actual Kaggle Python packages, import rules, package-size limit, and runtime budget must be measured before choosing the final model format.
- Pokemon-derived models and data must follow the competition's stated usage and deletion rules.
- Reproducibility, generalization, deck quality, and report quality affect the final outcome, not only a local mirror win rate.

### 3.4 Current evidence

- Existing one-turn search is fast enough locally to justify an MCTS prototype.
- A previous one-ply lookahead regressed because its evaluator was myopic. More search is not automatically stronger without a sound evaluator and opponent response model.
- Existing self-play results show that deck-specific behavior matters, but mirror-only evaluation is insufficient.

## 4. Core design decisions

1. **Algorithm:** Start with root-sampled Information-Set MCTS (ISMCTS). Upgrade its UCT selection to PUCT when a learned policy prior is available.
2. **Learning approach:** Use an AlphaZero-style policy-improvement loop: MCTS visit counts are policy targets and final game outcomes are value targets.
3. **Action model:** Score legal options conditionally instead of allocating one output neuron per global action. Complete multi-select actions are generated from legal options under strict caps.
4. **Hidden information:** Use belief sampling and information-set node keys. Oracle hidden information is allowed only as a diagnostic upper bound, never as a deployable policy.
5. **Training architecture:** Separate self-play workers, replay storage, learner, evaluator, and checkpoint registry.
6. **Parallelism:** Use processes, not threads, around the native simulator.
7. **Deployment:** Keep a deterministic heuristic fallback. Learned inference is optional at runtime only until the Kaggle environment is verified.
8. **Promotion:** No candidate replaces the active agent based on training loss or a single mirror matchup.

## 5. Planned repository structure

```text
plan_1/
  README.md
  pyproject.toml
  requirements-plan1.in
  requirements-plan1.lock
  configs/
    schema.json
    mcts_baseline.json
    selfplay.json
    training.json
    evaluation.json
    deployment.json
  src/plan1/
    engine/
      adapter.py
      lifecycle.py
      conformance.py
    game/
      observation.py
      entities.py
      actions.py
      action_generator.py
      rewards.py
    belief/
      card_accounting.py
      priors.py
      sampler.py
      information_set.py
    search/
      node.py
      tree.py
      uct.py
      puct.py
      rollout.py
      time_manager.py
      transposition.py
    evaluation/
      features.py
      heuristic_value.py
      tactical_checks.py
    model/
      vocabulary.py
      encoder.py
      policy_value.py
      inference.py
      export.py
    data/
      trajectory.py
      replay_buffer.py
      manifests.py
      validation.py
    selfplay/
      worker.py
      coordinator.py
      league.py
    training/
      dataset.py
      learner.py
      losses.py
      checkpoint.py
    benchmark/
      match.py
      suite.py
      statistics.py
      ablation.py
    deployment/
      submission_agent.py
      fallback.py
      package.py
    telemetry/
      events.py
      search_trace.py
  scripts/
    bootstrap.ps1
    verify_environment.py
    run_conformance.py
    run_selfplay.py
    train.py
    evaluate.py
    export_model.py
    build_submission.py
  tests/
    unit/
    integration/
    regression/
    property/
  artifacts/
    manifests/
    reports/
    checkpoints/
    traces/
```

Generated trajectories and large checkpoints must live outside Git or under ignored artifact directories. Only manifests, small fixtures, promoted compact weights, and reproducibility metadata should be committed.

## 6. Environment and reproducibility

### 6.1 Bootstrap

- Create an isolated Plan 1 virtual environment.
- Verify the engine under the selected Python version before installing ML packages.
- Pin all direct and transitive dependencies with hashes after compatibility testing.
- Install a CPU-compatible numerical stack first.
- Test optional CUDA acceleration separately; never make it a correctness dependency.
- Record package licenses and reject dependencies that conflict with competition terms.
- Add one environment verification command that reports Python, OS, CPU, GPU, package versions, engine import, and a simulator smoke test.

### 6.2 Reproducibility identity

Every run receives a unique `run_id` and records:

- Git commit and dirty-worktree indicator.
- Configuration hash.
- Card-data and deck hashes.
- Engine version or binary hash.
- Python and dependency versions.
- Global seed and worker-specific derived seeds.
- Model/checkpoint hash.
- Belief-model version.
- Host information and start/end timestamps.

### 6.3 Configuration rules

- Configuration files are schema-validated before a run starts.
- Unknown keys are errors.
- Defaults are explicit and included in the archived resolved configuration.
- Training, self-play, evaluation, and deployment settings are separate to prevent accidental evaluation noise or exploration in production.

## 7. Engine adapter and conformance layer

### 7.1 Required adapter behavior

- Translate engine objects into immutable Plan 1 observation records.
- Start a search from an observation and one sampled hidden-state determinization.
- Apply one complete legal selection and return the resulting search observation.
- Detect terminal outcomes.
- Release individual search states as soon as they are no longer reachable.
- End the native search session reliably on success, exception, timeout, or cancellation.
- Expose simulator timings and allocation counters.

### 7.2 Conformance questions that must be answered experimentally

1. Does `search_step` preserve the parent state for additional branches, or consume/mutate it?
2. Can multiple child states coexist safely?
3. Are state identifiers stable only within one `search_begin` session?
4. Which selections are ordered, and which multi-select actions are unordered sets?
5. How are optional selections, zero-count selections, duplicate indices, and cancel/pass represented?
6. When do chance events occur, and how are they seeded?
7. Can search advance across turn boundaries and both players' decisions without restarting?
8. What are the exact failure modes for invalid hidden-zone predictions?
9. Does calling `search_release` invalidate descendants or only the selected state?
10. What memory growth occurs over hundreds or thousands of branches?

The MCTS implementation must be based on measured answers, not assumptions. If parent states are consumed, branches must be reconstructed by replaying action paths from the root.

### 7.3 Engine safety tests

- One-step equivalence between real play and searched play for deterministic decisions.
- Repeated branching from one root.
- Deep path replay.
- Full-turn and cross-turn simulation.
- Forced coin-flip distribution sanity check without favorable manual outcomes.
- Invalid action rejection.
- Search-state release and memory-leak soak test.
- Exception cleanup test proving `search_end` is called.
- Multi-process isolation test.

## 8. Observation, entity, and action representation

### 8.1 Observation representation

Encode all legally observable information, including:

- Turn number, current player, first player, action count, phase/context, and once-per-turn flags.
- Prize counts, deck counts, hand counts, discard piles, stadium, status conditions, and result.
- Active and bench Pokemon with card ID, serial identity, current/max HP, damage, energy attachments, tool, evolution history, status, and appeared-this-turn state.
- The acting player's visible hand and all public revealed cards.
- Current selection metadata, context card, remaining damage counters, remaining energy costs, legal options, and count bounds.
- Running public-card accounting for both players.

Never encode opponent hidden cards from a sampled determinization as if they were observed. Determinization is used only by the simulator instance and hidden-state rollout policy.

### 8.2 Entity encoding

- Maintain a card vocabulary containing every dataset card plus `UNKNOWN`, `PAD`, and invalid sentinels.
- Store card metadata in a versioned table derived from the competition dataset.
- Encode Pokemon, Trainer, Energy, zones, and selection options as typed entities.
- Preserve active/bench slot identity because position affects legal choices.
- Use masking for absent fields rather than overloaded numeric sentinels.
- Normalize bounded numeric features and clip unbounded counts defensively.

### 8.3 Complete-action generation

MCTS children represent complete legal `list[int]` selections.

- For one-choice selections, emit each legal option.
- For fixed small multi-select choices, enumerate valid combinations or permutations according to verified engine semantics.
- For large combinatorial selections, use a candidate generator consisting of:
  - Existing heuristic action.
  - Top policy-ranked individual options.
  - Domain-specific legal combinations.
  - A small reproducibly sampled tail for exploration.
- Apply progressive widening as visit count grows.
- Never silently truncate mandatory choices below `minCount`.
- Canonicalize unordered sets and preserve order where order is meaningful.
- Use an action fingerprint containing selection type/context and option descriptors so raw option indices are not reused across unrelated states.
- Mask every invalid action before policy normalization.
- Fall back to the existing legal heuristic if generation or inference fails.

### 8.4 Action-generation tests

- Every emitted action is accepted by the simulator.
- Required actions satisfy `minCount` and `maxCount`.
- No duplicate action fingerprints.
- Canonicalization is stable.
- Masking leaves at least one action whenever the engine presents a valid decision.
- Large-option decisions remain within configured candidate and latency caps.

## 9. Hidden-information belief system

### 9.1 Card accounting

- Track known decklists where available in controlled evaluation.
- Subtract publicly observed cards from possible hidden-zone multisets.
- Treat own hidden prizes as unknown to the policy unless revealed by the game.
- Track opponent revealed cards without assuming unobserved copies.
- Enforce hand, deck, prize, and discard counts when sampling.

### 9.2 Belief tiers

1. **Tier 0 - Current mirror-fill baseline:** Retained only for comparison.
2. **Tier 1 - Public-card constrained generic prior:** Samples from the legal card pool or a deck-distribution prior while respecting observations.
3. **Tier 2 - Archetype posterior:** Updates deck/archetype probabilities from revealed cards and samples a consistent deck and hand.
4. **Oracle diagnostic:** Uses the actual hidden deck in offline tests to estimate the value lost to uncertainty. It is never deployable.

### 9.3 Root sampling ISMCTS

- Sample one hidden-state determinization at the start of each simulation.
- Share node statistics by public information-set key, not by the sampled hidden state.
- Prevent hidden information discovered in one determinization from changing legal policy features in another.
- Use multiple determinizations per root and report effective diversity.
- Reject impossible samples and log belief degeneracy.

### 9.4 Opponent hidden-hand behavior

- The opponent rollout policy may condition only on what that simulated opponent would legally know in the sampled world.
- Root-player policy features must remain observation-limited.
- Record belief calibration metrics: revealed-card likelihood, sample rejection rate, archetype entropy, and duplicate-determinization rate.

## 10. Handcrafted position evaluator

The first MCTS release uses a transparent evaluator before any learned model is trusted.

### 10.1 Feature groups

- Terminal win/loss/draw.
- Prize race and multi-prize Pokemon liability.
- Immediate legal attack availability and expected damage.
- Lethal attack and opponent lethal-next-turn risk.
- Active survivability after the opponent's likely response.
- Current HP, damage taken, status, retreat cost, and switching options.
- Attached energy value, stranded energy, attack-cost readiness, and energy acceleration.
- Board development: viable attackers, bench depth, evolution readiness, and stage bottlenecks.
- Hand quality, draw/search access, supporter availability, deck size, and decking risk.
- Ability availability and usage caps.
- Tempo: turns to attack, turns to evolve, avoidable pass, and action efficiency.
- Matchup features such as weakness/resistance only when exposed by game/card data.

### 10.2 Evaluator rules

- Terminal outcomes override every heuristic score.
- Score from the root player's perspective and verify player-swap negation where applicable.
- Keep reward shaping out of final RL outcome targets.
- Version every weight set.
- Do not tune constants against one Hydrapple mirror and call them general.

### 10.3 Evaluator tests

- A terminal win scores above every nonterminal state; a terminal loss scores below it.
- Taking a prize without losing compensating material is monotonic.
- Avoiding an immediate knockout is preferred when all other features are equal.
- Making a legal attack is preferred to an avoidable pass in equivalent positions.
- Added useful energy does not lower readiness in an otherwise identical state.
- Player-perspective conversion is consistent.
- Golden tactical positions capture known stall, promotion, retreat, and KO-back failures.

## 11. MCTS design

### 11.1 Baseline search stages

1. **Stage A:** UCT with handcrafted evaluator, current-turn horizon, heuristic opponent response.
2. **Stage B:** UCT with at least one opponent response and KO-back awareness.
3. **Stage C:** Root-sampled ISMCTS across hidden determinizations.
4. **Stage D:** PUCT using learned policy priors and learned leaf value.
5. **Stage E:** Deeper or more selective search using measured value accuracy and adaptive budgets.

Each stage must be evaluated independently. No learned component is needed to validate the search infrastructure.

### 11.2 Node statistics

Each information-set action edge stores:

- Visit count.
- Mean root-perspective value.
- Value sum.
- Policy prior when available.
- Immediate reward and terminal flag.
- Virtual loss only if parallel simulations within one root are later proven safe.
- Timing, expansion failures, and sampled-determinization count for diagnostics.

### 11.3 Selection and backup

- Use UCT before a policy prior exists.
- Use PUCT after policy calibration is adequate.
- At opponent decisions, use negamax/root-perspective backup consistently; do not maximize both players for the root.
- Back up final terminal values as `+1`, `0`, or `-1` from the root player's perspective.
- For horizon leaves, back up the bounded evaluator or learned value.
- Keep any discount factor explicit and default it to `1.0` for episodic outcomes.

### 11.4 Expansion and rollout

- Expand legal complete-action candidates lazily.
- Use progressive widening for combinatorial decisions.
- Use the existing heuristic as rollout policy v0.
- Replace opponent rollout with a frozen policy/model pool as those become available.
- Detect loops by public-state/action-path fingerprints and terminate with a configured neutral or evaluator value.
- Cap depth, nodes, simulations, and wall-clock time independently.

### 11.5 Chance events

- Prefer the simulator's unbiased random chance behavior.
- Derive and record simulation seeds where the API permits.
- If explicit chance branching is introduced for offline analysis, weight outcomes by their true probability.
- Never choose favorable coin outcomes during deployed search.

### 11.6 Transpositions

- Begin without cross-root transpositions.
- Add per-root public-information-set transpositions only after hash correctness tests.
- Include turn flags, selection context, visible zones, board serials, and all rule-relevant state in the key.
- Never include hidden determinization content in a shared information-set key.
- Detect hash collisions in debug builds by comparing full canonical records.

### 11.7 Time management

- Measure search overhead on representative decision types and option counts.
- Use a fixed safe per-decision wall-clock cap first.
- Reserve cleanup and fallback time.
- Skip search for forced single-action decisions.
- Use smaller budgets for low-impact setup selections and larger budgets for MAIN, attack, promotion, retreat, and prize-critical choices.
- Stop on time, simulation count, node count, or memory cap, whichever occurs first.
- Return the most visited legal root action; if no simulation completes, return the heuristic fallback.
- The deployment budget is selected only after Kaggle runtime profiling.

## 12. Policy-value model

### 12.1 Required outputs

- **Value head:** Scalar expected game outcome in `[-1, 1]` from the acting player's perspective.
- **Policy head:** Logits over the legal options or generated complete-action candidates for the current selection.

### 12.2 Initial architecture

- Versioned embeddings for card ID, entity type, zone, player ownership, selection type, and selection context.
- Numeric feature projection for HP, counts, damage, energy, turn flags, and other bounded values.
- Entity encoder over active Pokemon, bench slots, visible hand cards, discard summaries, and global state.
- Slot/zone embeddings where order or identity matters.
- Masked pooling or a small attention/set encoder for variable-size collections.
- Option encoder conditioned on the shared state representation.
- Policy score computed per legal action candidate.
- Value head computed from the shared state representation.

Start small enough for CPU inference. Increase capacity only when profiling and learning curves justify it.

### 12.3 Multi-select policy

- v0 scores generated complete-action candidates.
- If candidate generation becomes the bottleneck, v1 uses autoregressive option selection conditioned on prior picks and a stop token constrained by `minCount`/`maxCount`.
- Training and inference must use the same canonical ordering and legality mask.

### 12.4 Losses

- Policy cross-entropy or KL loss against normalized MCTS visit counts.
- Value regression loss against final game outcome, with optional bounded auxiliary targets.
- L2/weight decay configured explicitly.
- Optional auxiliary losses for immediate attack availability, prize differential, or terminal prediction only if ablation shows benefit.
- Log every component separately.

### 12.5 Model correctness tests

- Stable output shapes for every selection type.
- Invalid actions receive zero probability after masking.
- No NaN/Inf under empty, maximal, or unusual boards.
- Batched and unbatched inference agree within tolerance.
- Saved and loaded checkpoints reproduce outputs.
- Exported inference reproduces framework output within a declared tolerance.

## 13. Trajectory and replay data

### 13.1 Trajectory record

For every decision, store:

- Schema version, game ID, decision index, player/seat, seed, and timestamp.
- Public observation and selection metadata.
- Legal action fingerprints and masks.
- Chosen action.
- Root visit counts, priors, Q values, search depth, nodes, simulations, and elapsed time.
- Belief version and determinization diagnostics, but not hidden oracle data in policy input fields.
- Acting model/checkpoint and opponent identity.
- Deck IDs and hashes.
- Final result and terminal reason.

### 13.2 Storage guarantees

- Write one game to a temporary file and atomically rename it after validation.
- Compress records with a benchmarked standard format.
- Add checksums and manifest counts.
- Quarantine truncated, mismatched-schema, or invalid records.
- Split train/validation/test by complete games and seed groups, never by individual decisions.
- Hold out decks/archetypes for generalization tests.
- Enforce retention and disk-space caps.

### 13.3 Replay sampling

- Mix recent self-play with a bounded historical window to reduce forgetting.
- Prevent one long deck or selection context from dominating batches.
- Track outcome, deck, context, and model-version distributions.
- Add prioritized sampling only after a uniform baseline is stable.
- Never train on final evaluation games.

## 14. Supervised bootstrap

Before full RL:

1. Generate games using the current heuristic and heuristic MCTS.
2. Train a behavioral-cloning policy to reproduce legal heuristic choices as an initialization, not as the final objective.
3. Train the value head on complete-game outcomes.
4. Compare the learned policy to the heuristic on held-out decisions.
5. Use stronger MCTS visit distributions to improve policy targets.
6. Confirm that MCTS plus the learned model is at least as strong as MCTS plus the handcrafted evaluator before entering autonomous self-play.

The bootstrap avoids starting from random play while preserving the ability to exceed the teacher through search improvement.

## 15. AlphaZero-style self-play loop

### 15.1 Iteration lifecycle

1. Select the current champion and opponent mixture.
2. Generate seat-balanced self-play games with root exploration enabled.
3. Validate and commit trajectories to the replay manifest.
4. Train a candidate policy-value checkpoint.
5. Run offline sanity, calibration, and tactical tests.
6. Evaluate candidate versus champion and the frozen baseline field.
7. Promote only if all gates pass.
8. Add promoted and selected historical checkpoints to the league.
9. Archive the full iteration report and resume from the next iteration.

### 15.2 Exploration rules

- Root Dirichlet noise is allowed only during training self-play and is disabled in evaluation/deployment.
- Use a higher visit-count temperature in early turns and near-zero temperature later; tune by evidence.
- Disable resignation initially. Add it only after value calibration demonstrates a very low false-resignation rate.
- Preserve a fraction of games against historical opponents to prevent cyclic forgetting.

### 15.3 League composition

- Current champion.
- Recent checkpoints.
- Selected historical champions.
- Current shipped heuristic.
- Frozen pre-search baseline.
- Deck-specialized Plan 2 policies when stable.
- Optional scripted stress opponents for tactical patterns.

Opponent sampling weights must be recorded and must not silently change inside an iteration.

### 15.4 Worker architecture

- One coordinator allocates immutable game jobs.
- Each simulator worker is a separate spawned process with its own engine lifecycle.
- One writer validates and atomically records completed games.
- One learner reads immutable replay manifests and writes versioned candidate checkpoints.
- One evaluator uses a separate seed range and cannot write training data.
- Heartbeats, stale-job recovery, graceful shutdown, and resumable queues are required before long unattended runs.

## 16. Evaluation system

### 16.1 Frozen evaluation field

The suite must include:

- Current shipped agent.
- Previous promoted Plan 1 champion.
- Heuristic MCTS without learned policy/value.
- Learned policy without MCTS.
- At least one weaker sanity opponent.
- Multiple selected deck matchups, including mirror and cross-deck games.
- Plan 2 deck specialists when they become valid frozen opponents.

### 16.2 Match protocol

- Alternate seats and first player.
- Use paired or controlled seed schedules where valid, then confirm with fresh independent seeds.
- Use identical decks and opponents for direct candidate/champion comparisons.
- Run a small smoke stage, a medium screening stage, and an `n >= 500` confirmation stage for promotion claims.
- Increase samples when the effect is small or the confidence interval crosses the configured practical threshold.
- Report draws, crashes, timeouts, illegal actions, and forfeits separately.

### 16.3 Statistical protocol

- Report win rate and a 95% confidence interval.
- Use a predeclared two-proportion or paired test appropriate to the match design.
- Report effect size, not only p-value.
- Correct or acknowledge repeated looks and multiple candidate comparisons.
- Define a practical improvement margin before the run.
- Treat inconclusive evidence as inconclusive, not as a win.
- Preserve all raw match results and the exact analysis command.

### 16.4 Required metrics

- Wins, losses, draws, and score by matchup/seat/first-player status.
- Illegal-action, exception, timeout, and fallback rates.
- Mean, median, p95, and maximum decision time.
- Simulations/sec, nodes expanded, depth, branching factor, and memory use.
- Policy entropy, root visit concentration, and value calibration.
- Prize progression, attack rate, avoidable-pass rate, and game length.
- Belief sampling rejection/diversity metrics.

### 16.5 Required ablations

- Current heuristic versus heuristic MCTS.
- UCT versus PUCT.
- Handcrafted value versus learned value.
- Uniform prior versus learned policy prior.
- Mirror-fill belief versus constrained generic prior versus archetype posterior.
- Current-turn horizon versus opponent-response horizon.
- Simulation/time budgets.
- Root exploration on/off during training.
- Model sizes and inference formats.
- Per-deck and held-out-deck performance.

One experimental report should change one causal mechanism whenever practical.

### 16.6 Promotion gates

A candidate becomes champion only if:

- All correctness and tactical regression tests pass.
- Zero illegal actions and unhandled exceptions occur in the confirmation suite.
- Timeout/fallback rate is below the declared deployment threshold.
- It achieves the predeclared statistical and practical improvement against the current champion, or is demonstrably equal while substantially reducing runtime/size.
- It does not produce a material regression on any critical held-out deck group.
- Search and inference fit the measured deployment budget with safety margin.
- Its checkpoint, data, and run manifest are complete and reproducible.

Promotion to the actual submission requires an additional Kaggle packaging and runtime validation.

## 17. Human review

Human review is a quality-control layer, not the primary scoring method.

### 17.1 Review samples

- Candidate wins and losses against the champion.
- Highest value-error positions.
- Search roots where policy and visits strongly disagree.
- Long games, avoidable passes, repeated retreats, stalled boards, and fallback events.
- Belief-sensitive decisions and surprising opponent reads.
- Every newly added tactical regression fixture.

### 17.2 Review questions

- Was the action legal and based only on available information?
- Did the search consider the obvious tactical line?
- Did the chosen line expose an avoidable knockout?
- Was the value estimate directionally sensible?
- Did action generation omit a strong legal combination?
- Did hidden-state sampling bias the choice unrealistically?
- Is a failure caused by policy, value, belief, horizon, action generation, or engine integration?

Human findings become reproducible fixtures or tagged datasets before changing constants.

## 18. Deployment architecture

### 18.1 Runtime agent

The deployable agent will contain:

- Observation conversion.
- Belief sampler appropriate to available information.
- Time-bounded MCTS.
- Optional compact policy-value inference.
- Deterministic heuristic fallback.
- Strict lifecycle cleanup and minimal local telemetry.

### 18.2 Dependency spike

Before selecting the model export:

1. Inspect the real Kaggle runtime package inventory.
2. Measure allowed submission/package size.
3. Verify whether additional pure-Python files and binary model artifacts are accepted.
4. Measure import time, model-load time, memory, and per-decision latency.
5. Verify that no network access is needed.

Candidate inference formats, in order of lowest deployment risk:

1. Small pure-Python/standard-library inference with compact numeric weights.
2. NumPy inference if NumPy is confirmed available.
3. ONNX Runtime if confirmed available and package rules permit it.
4. PyTorch only if confirmed available and comfortably inside runtime limits.
5. Heuristic-value MCTS fallback if learned inference cannot be packaged safely.

### 18.3 Submission validation

- Build in a clean temporary directory from a manifest.
- Reject undeclared files and absolute paths.
- Start a fresh process and import the exact submission artifact.
- Run full games without development dependencies.
- Test missing/corrupt model behavior.
- Confirm deterministic evaluation mode.
- Measure cold and warm latency.
- Confirm every decision returns before the safety deadline.
- Keep a one-command rollback to the last accepted submission.

## 19. Reliability and failure handling

| Failure | Required response |
|---|---|
| Search initialization fails | Log reason, clean up, return heuristic action. |
| No MCTS simulation completes | Return heuristic action. |
| Model load/inference fails | Disable model for that process and use heuristic value/policy. |
| NaN/Inf output | Reject output, record checkpoint fault, use masked uniform or heuristic prior. |
| Illegal generated action | Drop it, record fixture, never send it to live play if another legal action exists. |
| Native state leak | Abort worker, preserve diagnostic manifest, restart clean process. |
| Worker heartbeat expires | Requeue job once with a new worker and mark original attempt. |
| Corrupt trajectory | Quarantine it; never train from partial data. |
| Corrupt checkpoint | Fall back to the previous verified checkpoint. |
| Disk limit approached | Stop assigning new self-play jobs and finish/flush active games. |
| Time budget approached | Stop expansion early and return most visited legal action. |
| Belief sampler cannot satisfy counts | Use a documented conservative fallback distribution and increment an error metric. |
| Schema mismatch | Refuse to train or evaluate until an explicit migration is run. |

Long-running processes must support graceful stop, crash recovery, resume, and an append-only operational report.

## 20. Security, integrity, and compliance

- No network calls from the competition agent.
- No reading files outside declared submission assets.
- No hidden-state oracle data in model inputs or policy logs used for training.
- Validate all imported deck, config, checkpoint, and trajectory paths.
- Treat checkpoints and trajectory files as untrusted input during loading.
- Record third-party licenses and data provenance.
- Follow competition restrictions for Pokemon-derived data and post-competition deletion.
- Keep evaluation seeds and held-out results separate from training selection where feasible.

## 21. Implementation phases

### Phase 0 - Baseline freeze and environment bootstrap

**Work**

- Freeze and hash the current shipped agent, decks, card data, engine, and benchmark configuration.
- Create the Plan 1 directory, isolated environment, pinned dependency process, configuration schema, and run-manifest format.
- Capture current baseline performance and runtime on the initial deck field.

**Exit criteria**

- A clean machine can run one baseline game and reproduce the environment manifest.
- No active submission file has changed.

### Phase 1 - Engine conformance and lifecycle

**Status:** Complete on 2026-08-14. Evidence is stored in
`plan_1/artifacts/reports/phase1-suite.json` and
`plan_1/artifacts/reports/phase1-process-isolation.json`.

**Work**

- Implement the engine adapter and answer every conformance question in Section 7.
- Add branch, replay, chance, cleanup, leak, and process-isolation tests.

**Exit criteria**

- Full games can be searched and replayed without leaked states or illegal lifecycle calls.
- The safe branching strategy is documented with measured memory and latency.

### Phase 2 - Canonical observations and legal actions

**Status:** Complete on 2026-08-14. Aggregate evidence is stored in
`plan_1/artifacts/reports/phase2-suite.json`; competition-derived fixture and
catalog files remain local and are identified by hashes in that report.

**Work**

- Implement immutable observations, entity/card vocabulary, action fingerprints, multi-select handling, masks, and fallback action generation.
- Build a corpus of real selection fixtures covering every observed type/context.

**Exit criteria**

- Every generated action in the fixture and random-game suite is legal.
- Unknown selection patterns fail safely and are logged.

### Phase 3 - Handcrafted evaluator and tactical suite

**Status:** Complete on 2026-08-14. Evidence:
`plan_1/artifacts/reports/phase3-suite.json` (SHA-256
`49f27228c74b827e6be1e4aecadef54a9b37d13c4f77071659ef4ca5d8bd098f`).

**Work**

- Implement the evaluator feature groups and invariants.
- Convert known stalling, promotion, retreat, target, and KO-back cases into golden fixtures.

**Exit criteria**

- All evaluator invariants and tactical fixtures pass.
- Evaluator computation is negligible relative to one simulator step.

### Phase 4 - Deterministic heuristic MCTS

**Status:** Complete on 2026-08-14 as an isolated search and validation
implementation; **not promoted** to the active submission. Definitive safety
evidence is `plan_1/artifacts/reports/phase4-soak-final-v4.json` (SHA-256
`270ac74a1e6c23de6b47dbfaeab816e49ec48771651904d8ef6fccf207ba8407`).
The bounded Stage A strength screen is
`plan_1/artifacts/reports/phase4-bounded-screen-h0-v2.json` (SHA-256
`850dfe4a1b7d1d6ed87c760d37d539b284c4c716abf8e561c4183fa54352c9e2`),
and the Stage A/Stage B horizon ablation is
`plan_1/artifacts/reports/phase4-horizon-ablation-bounded-v2.json` (SHA-256
`e97cd0cccdc8b545b01adc3922c0ced31c8347ab40cee7ee73e5b70060c7ce2c`).

The final safety profile used four simulations, 32 nodes, eight candidates, a
24 ms hard budget with 16 ms reserved for cleanup/native-call slack, complete
root coverage before overriding fallback, and deterministic greedy fallback.
It completed 500/500 games (125 per deck) with zero faults, illegal actions,
crashes, errors, or 2,000-step timeouts. Full-action timing was 12.701 ms p95
and 80.068 ms maximum against declared 35/500 ms host limits. Internal search
was 10.135 ms p95 and 47.504 ms maximum; 7/42,459 searches (0.0165%) crossed
the nominal hard deadline because a native engine call cannot be preempted.

Two failed soak reports are intentionally retained. `phase4-soak-final.json`
failed at 499/500 games and a 416 ms host tail; after correcting final-action
terminal accounting, `phase4-soak-final-v2.json` completed 500/500 but exposed
a 1.064 s host tail from composing UCT with the shipped one-ply fallback. The
final integration removed that nested search and uses bounded greedy fallback.
`phase4-soak-final-v3.json` was the first passing bounded-fallback soak, but its
telemetry compared the selected action with the first expanded edge instead of
the actual fallback. `v4` adds the fallback action to the result contract and
supersedes `v3` as the definitive report without changing gameplay behavior.

The candidate did not establish a strength gain: bounded Stage A scored 15-25
against the current agent over 40 seat-balanced Hydrapple games (`p=0.114`,
in the wrong direction). Stage B scored 33-27 against Stage A over 60 games,
but the difference was a tie (`p=0.439`). Only 16.22% of final-soak roots had
full coverage and MCTS changed the greedy fallback on 6.26% of searched
decisions. Phase 4 therefore validates the machinery and its failure modes,
not a stronger policy. Native chance remains engine-controlled and unbiased;
determinism here refers to candidate generation, UCT selection, and tie-breaks
given the observed search outcomes.

**Work**

- Implement UCT, expansion, backup, depth/loop limits, time manager, root action selection, traces, and fallback.
- Start at current-turn depth, then add one opponent response.

**Exit criteria**

- Zero illegal actions/faults in a 500-game soak test.
- Runtime caps hold at p95 and maximum.
- An ablation establishes whether heuristic MCTS improves over the current heuristic.

### Phase 5 - Belief model and ISMCTS

**Work**

- Implement public card accounting, generic prior, root sampling, information-set keys, and oracle diagnostic.
- Add belief consistency and leakage tests.

**Exit criteria**

- Samples always satisfy observable card/count constraints or use a measured fallback.
- Public policy features are identical across determinizations of the same information set.
- ISMCTS is compared against mirror-fill and oracle bounds.

### Phase 6 - Versioned trajectory pipeline

**Work**

- Implement schemas, atomic game files, manifests, validators, splits, replay reader, retention limits, and corruption recovery.

**Exit criteria**

- A generated corpus can be stopped, resumed, validated, and replayed exactly.
- Training/validation/test leakage checks pass.

### Phase 7 - Policy-value supervised bootstrap

**Work**

- Implement the model, dataset, legal masking, losses, checkpoints, inference, and calibration reports.
- Train from heuristic/MCTS games.

**Exit criteria**

- The model beats uniform baselines on held-out policy prediction and value calibration.
- MCTS using the model is no worse than heuristic MCTS in the screening suite.
- CPU inference meets the provisional latency budget.

### Phase 8 - AlphaZero-style reinforcement loop

**Work**

- Implement self-play coordinator/workers, root exploration, replay-window sampling, learner, candidate evaluation, and champion promotion.

**Exit criteria**

- At least three complete iterations run unattended and resume after interruption.
- Candidate promotion/rejection is reproducible from archived outputs.
- No evaluation games enter training data.

### Phase 9 - League and generalization

**Work**

- Add historical checkpoints, multiple decks, cross-deck matchups, held-out deck tests, and Plan 2 specialists.
- Measure catastrophic forgetting and cyclic dominance.

**Exit criteria**

- A promoted model clears the multi-deck generalization gate.
- Performance is not dependent on one mirror matchup or one opponent snapshot.

### Phase 10 - Search/model optimization

**Work**

- Profile bottlenecks, batch inference where useful, tune candidate widening and simulation budgets, compare model sizes, and test export formats.
- Optimize only measured hot paths.

**Exit criteria**

- The chosen configuration delivers the strongest validated score inside deployment limits with safety margin.

### Phase 11 - Submission packaging and shadow validation

**Work**

- Build the exact Kaggle artifact, verify clean-process execution, run the complete frozen suite, and shadow it without replacing the active submission.

**Exit criteria**

- Packaging, imports, model load, games, cleanup, fallback, and runtime pass in the closest available Kaggle-equivalent environment.
- A signed promotion report approves or rejects replacing the active submission.

### Phase 12 - Strategy report and archival

**Work**

- Document architecture, belief handling, experiments, ablations, failures, deck interaction, reproducibility, limitations, and compliance.
- Archive manifests and create the required post-competition data-deletion checklist.

**Exit criteria**

- Report claims map to preserved experiment artifacts.
- A reviewer can reproduce the promoted evaluation from documented commands.

## 22. Experiment order

Run experiments in this causal order:

1. Current heuristic baseline.
2. Handcrafted evaluator alone on tactical fixtures.
3. UCT current-turn search versus no search.
4. UCT with opponent response versus current-turn search.
5. ISMCTS generic belief versus mirror-fill.
6. Oracle hidden-state diagnostic to estimate remaining uncertainty cost.
7. Behavioral-cloned policy without search.
8. Learned value with uniform/heuristic policy in MCTS.
9. Learned policy prior with handcrafted value.
10. Combined policy-value PUCT.
11. Self-play iteration candidates versus frozen champion.
12. Multi-deck league and held-out generalization.
13. Model/search compression and deployment ablations.

Do not bundle belief, value, policy, search depth, and deck changes into one unexplained result.

## 23. Time plan

The local competition file lists the Simulation final on August 16, 2026 and Strategy final on September 13, 2026. Therefore Plan 1 has two different tracks.

### First 24 hours

- Complete Phase 0.
- Complete the critical Phase 1 conformance experiments.
- Build the observation/action fixtures.
- Establish whether native branching and multi-process isolation are reliable.

### First 72 hours

- Complete Phases 1-3.
- Produce a legal time-bounded heuristic UCT prototype.
- Run smoke and tactical comparisons.
- Do not submit it unless it independently clears the active-agent gate.

### Week 1

- Complete deterministic MCTS, opponent-response search, belief baseline, and the trajectory schema.
- Produce a rigorous heuristic MCTS/ISMCTS evaluation.

### Week 2

- Complete supervised policy-value bootstrap and the first controlled PUCT ablations.
- Start resumable self-play iterations.

### Week 3 and remaining Strategy time

- Build the league, tune only through ablations, test held-out decks, optimize deployment, and write the reproducible report.

The Simulation deadline should not force an unvalidated RL model into `main.py`. The Strategy submission can document and evaluate the full system even if the safest Simulation artifact remains a heuristic or heuristic-MCTS agent.

## 24. Compute and storage policy

- Benchmark games/sec, trajectory MB/game, and training examples/sec during Phase 6 before choosing large run counts.
- Start with one worker, then scale to available physical/logical cores while measuring contention.
- Reserve CPU capacity for the coordinator and writer.
- Limit native-engine workers based on memory soak tests, not logical-core count alone.
- Keep checkpoints on a retention schedule: champion, recent candidates, selected historical league members, and milestone snapshots.
- Stop automatically before free disk reaches a declared reserve.
- Record energy/time cost per training iteration for report transparency.

No permanent value is assigned to “24 hours nonstop” by itself. Progress is measured by validated games, useful training samples, successful iterations, and evaluation strength.

## 25. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Search API cannot branch as assumed | MCTS architecture invalid | Phase 1 conformance; replay paths from root if required. |
| Hidden-state leakage | Invalid competition agent and misleading results | Information-set keys, observation-only model inputs, leakage tests. |
| Variable multi-select action explosion | Search becomes too slow | Candidate generator, policy ranking, progressive widening, hard measured caps. |
| Poor evaluator makes deeper search worse | Strength regression | Tactical invariants, opponent-response features, independent ablations. |
| Self-play overfits one mirror | Weak leaderboard generalization | Multi-deck league, held-out decks, frozen field. |
| Model copies weak heuristic | Learning ceiling | Use heuristic only for bootstrap; train on improved visits and outcomes. |
| Nonstationary self-play collapses | Cycles/forgetting | Historical league, champion gates, replay mixture. |
| Native engine is not thread-safe | Crashes/corruption | Process isolation and worker restart. |
| Windows multiprocessing bugs | Workers fail to launch/resume | Spawn-safe entry points and early integration tests. |
| ML packages unavailable in Kaggle | Model cannot deploy | Dependency spike and pure-Python/heuristic fallback. |
| Runtime or model too large | Timeouts/package rejection | Small CPU-first model, profiling, compression, fixed safety caps. |
| Statistical false positives | Bad candidate promoted | Predeclared tests, fresh confirmation seeds, multiple-look accounting. |
| Training/evaluation leakage | Inflated evidence | Separate manifests, seed ranges, and held-out decks. |
| Data/checkpoint corruption | Lost runs or invalid training | Atomic writes, checksums, quarantine, resume tests. |
| Unbounded unattended jobs | Resource exhaustion | Heartbeats, disk/memory/time caps, graceful stop. |
| Plan 2 changes invalidate baselines | Comparisons drift | Frozen immutable agents/decks and hash-based identities. |
| Competition deadline pressure | Unsafe submission replacement | Shadow validation and explicit promotion gate. |

## 26. Required reports and artifacts

Every phase produces:

- Append-only implementation report.
- Resolved configuration.
- Test results.
- Runtime/resource profile.
- Known limitations.
- Artifact hashes.
- Decision: proceed, repeat, reject, or defer.

Every experiment produces:

- Hypothesis and changed mechanism.
- Frozen baselines and deck field.
- Seed schedule and sample size.
- Raw game output.
- Statistical analysis.
- Tactical/human review sample.
- Conclusion with uncertainty.

Every champion produces:

- Checkpoint and model-card summary.
- Training-data manifest.
- Full evaluation report.
- Deployment benchmark.
- Rollback target.

## 27. Immediate implementation backlog

The first implementation session should execute these items in order:

1. Create the Plan 1 skeleton and ignore rules for large artifacts.
2. Freeze baseline hashes and write the first run manifest.
3. Add environment verification and dependency compatibility checks.
4. Build engine lifecycle wrappers with unconditional cleanup.
5. Write branchability, state-release, chance, and cross-turn conformance probes.
6. Capture representative `SelectData` fixtures from complete games.
7. Implement canonical observation and action records.
8. Implement legal complete-action generation and its property tests.
9. Add tactical state fixtures and handcrafted evaluator v0.
10. Implement a single-process, fixed-simulation UCT root search.
11. Add wall-clock control, fallback behavior, and search traces.
12. Run the first no-search versus heuristic-MCTS ablation before adding neural code.

## 28. Decisions intentionally deferred

These choices require measurements from earlier phases:

- Exact ML package versions and CUDA use.
- Final network width, depth, and attention/set architecture.
- Final model export format.
- Number of parallel workers.
- Per-decision simulation/time budget.
- Progressive-widening constants.
- Replay-buffer size and training batch size.
- Root noise, temperature, and league sampling constants.
- Archetype prior complexity.
- Whether cross-root transpositions are worth their risk.

They are deferred, not omitted: each has a named phase, experiment, and acceptance gate above.

## 29. Plan 1 completion checklist

- [x] Baselines and data hashes frozen.
- [x] Isolated environment and dependency lock reproducible.
- [x] Engine branching/lifecycle behavior proven.
- [x] Observation schema complete and leakage-safe.
- [x] Legal action generation covers all observed selection types.
- [x] Tactical evaluator and regression suite pass.
- [x] Time-bounded heuristic MCTS completes 500-game soak test.
- [x] Opponent-response search ablated.
- [ ] Belief sampler and information-set search validated.
- [ ] Trajectory pipeline is atomic, resumable, and versioned.
- [ ] Policy-value model trains and exports reproducibly.
- [ ] PUCT improves or accelerates search under controlled evaluation.
- [ ] Three unattended self-play iterations complete successfully.
- [ ] League and held-out generalization gates pass.
- [ ] Kaggle dependency/package/runtime spike passes.
- [ ] Exact submission artifact passes clean-process games.
- [ ] Champion promotion report is approved.
- [ ] Strategy report maps claims to archived evidence.
- [ ] Competition data-retention/deletion obligations are documented.

## 30. Final decision rule

Plan 1 is an evidence-driven development track, not an automatic replacement for the current agent. The deployable result may be:

1. Policy-value PUCT/ISMCTS, if it is strong and package-safe.
2. Heuristic-value ISMCTS, if learned inference does not generalize or cannot deploy safely.
3. The existing heuristic agent, if neither search candidate clears the promotion gates before the relevant deadline.

The strongest validated, reproducible, legal, and deployable agent wins promotion. Architectural ambition alone does not.
