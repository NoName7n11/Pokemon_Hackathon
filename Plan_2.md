# Plan 2: Deck-Specific Development Agents

## Objective

Build a controlled experimentation platform in which independent coding agents improve private `main.py` implementations for specific decks, while a shared benchmark and tournament system determines which deck-agent pair is strong enough to become the submission candidate.

The coding agents are development workers. They inspect games, propose changes, edit private files, and run experiments. They are not used during a Kaggle battle. Every submitted `main.py` must remain self-contained and operate only through the competition environment.

## System Shape

```text
                         Human review
                              |
                              v
Deck registry -> Specialist workers -> Standard benchmarks
                       |                    |
                       v                    v
               Private experiments -> Central tournament
                                            |
                                            v
                                   Submission candidate
```

Each specialist owns one deck and its private battle logic. Shared tooling controls validation, measurement, comparison, and promotion.

## 1. Agent Contract

Every development worker must follow the same rules:

- Work only inside its assigned specialist directory.
- Never modify `sample_submission/sample_submission/main.py` or `deck.csv`.
- Keep an independently runnable `main.py` after every accepted experiment.
- Prefer one strategic hypothesis per experiment so gains can be attributed.
- Run the required validation and benchmarks before accepting a change.
- Record accepted and rejected experiments with evidence.
- Never claim success from mirror play alone.
- Request human review for meaningful strategic changes.
- Obey experiment, game-count, command, and runtime limits.
- Keep temporary or generated files outside the submission package.
- Never promote itself into the active submission.

The enforceable version of these rules belongs in `sub-agents/shared/AGENT_CONTRACT.md`.

## 2. Directory Structure

```text
sub-agents/
  README.md
  registry.json

  shared/
    AGENT_CONTRACT.md
    benchmark_config.json
    baseline/
      main.py
    prompts/
      specialist.md
      reviewer.md
    tools/
      create_specialist.py
      validate_agent.py
      run_experiment.py
      compare_results.py
      run_tournament.py
      promote_candidate.py
    schemas/
      experiment.schema.json
      result.schema.json

  specialists/
    Hydrapple/
      deck.csv
      main.py
      PROGRESS.md
      config.json
      status.json
      experiments/
      benchmarks/
      battle_traces/
      rejected/
      snapshots/

  tournaments/
    tournament_config.json
    results/
    reports/

  human-review/
    pending/
    approved/
    rejected/
```

A specialist directory is generated automatically whenever a new deck is registered.

## 3. Specialist Configuration

Each `config.json` records:

- Deck name and local deck path.
- Coding-agent provider: Codex, Claude Code, or Antigravity.
- Provider model or worker profile.
- Baseline `main.py` version and origin.
- Maximum experiments per run.
- Screening, main, and confirmation game counts.
- Command and decision timeout limits.
- Required mirror and cross-deck opponents.
- Human-review policy.
- Current accepted version.
- Permitted files and commands.
- Deck-specific strategy notes.

The worker provider is configuration, not hardcoded behavior. A deck can therefore be assigned to a different coding agent without rebuilding the platform.

## 4. Specialist Creation

The creation tool should support a command such as:

```powershell
python sub-agents/shared/tools/create_specialist.py `
  --deck Codex_Decks/MyDeck.csv `
  --provider claude
```

It must:

1. Validate that the source deck exists and is structurally usable.
2. Create a safe, predictable specialist directory name.
3. Copy the deck into the specialist directory.
4. Copy the selected baseline agent into the specialist directory.
5. Generate `config.json`, `status.json`, and `PROGRESS.md`.
6. Create experiment, benchmark, trace, rejection, and snapshot directories.
7. Register the specialist in `registry.json`.
8. Run syntax and import validation.
9. Refuse accidental overwrite of an existing specialist.

## 5. Bounded Worker Loop

Each coding agent follows the same finite experiment cycle:

1. Read the deck, private agent, specialist progress, and recent traces.
2. Identify one concrete gameplay weakness.
3. Record a hypothesis and expected measurable effect.
4. Snapshot the current accepted implementation.
5. Edit only the private `main.py` and approved specialist files.
6. Run syntax, import, legality, timeout, and action-validity checks.
7. Run a small screening benchmark.
8. Reject clear regressions early.
9. Run the main benchmark when screening passes.
10. Cross-check against other reference decks.
11. Generate representative decision traces.
12. Request human review when behavior changed materially.
13. Accept or reject the experiment and record the evidence.
14. Stop after the configured experiment or runtime budget.

No coding CLI receives an unrestricted or indefinite background loop.

## 6. Shared Benchmark Standard

Every specialist is evaluated under the same measurement policy:

- Mirror match against the specialist's frozen previous version.
- Cross-deck matches against at least two reference deck-agent pairs.
- Seat-balanced games with alternating first player.
- Shared seed policy and game counts.
- Crash, draw, timeout, and illegal-action tracking.
- Decision-time measurements.
- Win rate with a 95% confidence interval.
- A direct head-to-head 50% null test when candidate and baseline play each other.
- A two-proportion z-test when comparing independent benchmark arms.
- A fresh-seed confirmation run before promotion.

Suggested stages:

| Stage | Games | Purpose |
|---|---:|---|
| Smoke | 10-20 | Catch crashes and invalid behavior |
| Screening | 50-100 | Reject obvious regressions cheaply |
| Main evaluation | 300+ | Estimate the likely gameplay delta |
| Confirmation | 500+ | Verify accepted gains on fresh seeds |
| Final tournament | Configured per pairing | Rank deck-agent pairs against the field |

Statistical significance alone is not enough. A candidate must also show a meaningful practical improvement and avoid unacceptable cross-deck regressions.

## 7. Reference Opponents

The evaluation pool should contain:

- A frozen shared baseline agent.
- The previous accepted version of the same specialist.
- At least two cross-deck reference agents.
- The current tournament champion.
- A random agent only as a basic sanity check.

Historical baselines remain immutable so old results can be reproduced. A newly confirmed champion can be added to the reference pool without deleting earlier opponents.

## 8. Human-in-the-Loop Review

Human review should examine informative decisions rather than complete benchmark runs. Each candidate should generate a compact review pack containing:

- Turns where candidate and baseline selected different actions.
- Missed or delayed attacks.
- Retreat decisions.
- Forced Active promotion choices.
- Energy attachment and evolution choices.
- Trainer sequencing.
- Ignored lethal attacks.
- Unusually slow decisions.
- Final board states from representative losses.
- The scoring or reason that caused each selected move to win.

Workflow states:

```text
AUTOMATIC
    -> validation, benchmarks, trace extraction, and report generation

REVIEW_REQUIRED
    -> a strategically meaningful behavior changed

PROMOTION_REQUIRED
    -> a candidate may enter the final promotion process
```

The reviewer can approve, reject, or request another experiment.

## 9. Experiment Attribution

Every experiment must have a machine-readable record, for example:

```json
{
  "id": "hydrapple-EXP-0042",
  "hypothesis": "Prefer free promotion of an immediately ready attacker",
  "files_changed": ["main.py"],
  "mechanisms": ["promotion_scoring"],
  "baseline_version": "v12",
  "screening_result": {},
  "full_result": {},
  "cross_deck_result": {},
  "decision": "accepted",
  "reason": "Meaningful measured gain without a cross-deck regression"
}
```

When an experiment changes multiple mechanisms, it should normally run ablations before assigning credit to any one mechanism.

## 10. Central Tournament

Specialists do not select themselves as winners. The central tournament must:

- Load both the private deck and private agent module for every contestant.
- Swap the complete deck-agent pair correctly between seats.
- Alternate first player.
- Run every configured pairing in both orientations.
- Record wins, losses, draws, crashes, timeouts, and illegal actions.
- Produce a matchup matrix and overall ranking.
- Keep mirror performance separate from field performance.
- Rank robustness and field performance, not raw aggregate wins alone.

Final ranking should consider:

- Cross-deck win rate.
- Confidence and sample size.
- Worst matchup.
- Crash and illegal-action rate.
- Decision-time compliance.
- Generalization across deck archetypes.

## 11. Controlled Promotion

Promotion is a separate, explicit operation. It must:

1. Verify human approval.
2. Re-run final validation.
3. Preserve the current submission candidate as a recoverable snapshot.
4. Copy the selected deck and agent into the required submission paths.
5. Verify filenames and package structure.
6. Run smoke games from the actual submission directory.
7. Produce a manifest containing the source specialist and exact versions.

Development workers are not allowed to invoke promotion themselves.

## 12. Coding-Agent Roles

- **Codex:** platform coordination, benchmark integration, independent review, and optionally one specialist.
- **Claude Code:** independent deck-specialist experiments and strategic analysis.
- **Antigravity CLI:** another independent specialist using Gemini or Claude, preferably exploring a different deck or hypothesis.

The coding agent improves the source offline. The final battle agent is still the self-contained `main.py` selected by the tournament.

## 13. Progress and Evidence

Each specialist `PROGRESS.md` records:

- Date and worker identity.
- Reason for implementation.
- Hypothesis.
- Exact behavior changed.
- Test commands and sample sizes.
- Statistical and cross-deck results.
- Human-review status.
- Keep or reject decision.
- Known limitations.
- Next experiment.

Machine-readable JSON is authoritative for automated comparison. Markdown is the human-readable research journal.

The root `PROGRESS.md` records only major Plan_2 milestones and promoted findings, not every private experiment.

## 14. Implementation Order

1. Write the shared contract and benchmark policy.
2. Create the directory structure and registry.
3. Build specialist creation and validation.
4. Integrate existing benchmark scripts through stable adapters.
5. Add standardized experiment and result storage.
6. Build one specialist workflow using one coding CLI.
7. Add snapshots, bounded execution, and failure recovery.
8. Generate human-review reports.
9. Verify the complete flow with two specialists.
10. Add Claude Code and Antigravity provider adapters.
11. Build the deck-agent central tournament.
12. Add controlled submission promotion.
13. Run the first two-specialist pilot.
14. Refine the system before adding more decks or an MCTS/RL engine.

## First Implementation Milestone

The first milestone is deliberately narrower than the complete system:

- Create the shared contract, benchmark policy, schemas, registry, and directory structure.
- Implement safe specialist creation and static validation.
- Create one pilot specialist from the current Hydrapple deck and current agent baseline.
- Do not modify the active submission files.
- Do not launch an autonomous coding-agent loop yet.

This milestone succeeds when a new private specialist can be created repeatably, validated, registered, and prepared for experiments without risking the active submission.

## Implementation Status — 2026-08-12

### Phase 1: Specialist foundation — complete

- Shared contract, benchmark policy, schemas, registry, and directory structure.
- Safe specialist creation with deck and Python-interface validation.
- Private baseline and Hydrapple pilot specialist.
- Duplicate-name and active-submission protection.

### Phase 2: Bounded experiment lifecycle — complete

- One active experiment per specialist.
- Immutable versioned baseline snapshots.
- Per-experiment candidate copies; accepted files remain untouched during editing and testing.
- Ordered `smoke -> screening -> main -> confirmation` benchmark gates.
- Seat-balanced candidate-versus-previous-agent engine benchmark.
- Configured game caps, maximum steps, subprocess timeout, and preserved logs.
- Win/loss/draw, timeout, illegal-action, crash, step-count, and decision-time collection.
- Wilson confidence interval and head-to-head null-test statistics in JSON results.
- Machine-readable experiment history with candidate/baseline hashes and changed-file detection.
- Explicit human `accept` or `reject`; acceptance requires confirmation, cross-deck evidence, and final review.
- Rejected candidates remain archived without requiring rollback because accepted files were never replaced.
- Accepted candidates use recoverable snapshots and atomic per-file replacement inside the private specialist.

The Hydrapple infrastructure experiment used an unchanged candidate and completed a two-game, seat-balanced smoke run at 1-1 with no draw, timeout, illegal action, or crash. It was deliberately rejected because it tested infrastructure rather than a gameplay improvement.

### Phase 3: Coding-provider adapters — complete

- Provider-neutral discovery and command construction for Codex CLI, Claude Code, and the configured Antigravity slot.
- The Antigravity slot resolves explicitly to Gemini CLI on this machine because the installed Antigravity desktop application exposes no headless PATH command. Every audit record names the real backend.
- Per-experiment provider and dry-run budgets plus a wall-clock execution timeout.
- Disposable worker workspace containing only the candidate pair and copied experiment, specialist, rules, contract, progress, and baseline context.
- Experiment-specific prompt generation with a single-mechanism scope and an explicit `main.py`-only edit boundary.
- Codex workspace-write sandboxing, Claude Code restricted edit tools and safe mode, and Gemini sandbox/auto-edit mode.
- Provider stdout, stderr, prompt, resolved command, backend, timing, changed files, and validation outcome retained under the experiment.
- Post-run fingerprint enforcement: modifications outside root `main.py`, an unchanged agent, invalid deck, invalid Python syntax, failed process, or timeout prevent candidate import.
- Valid output is copied atomically into the staged experiment candidate only. It never updates the accepted specialist or active submission.
- Dry-run verification passed for all three configured provider slots using equivalent Hydrapple workspaces. No coding model was called and the infrastructure experiment was rejected without changing Hydrapple.

A real Codex provider call was verified in Phase 4. Its candidate was safely imported, benchmarked, and rejected on measured evidence.

### Phase 4: Bounded worker-cycle orchestration — complete

- Added an atomic per-specialist orchestration lock, preventing concurrent cycles from operating on one specialist.
- Added resumable orchestration over the existing experiment and provider CLIs rather than duplicating their safety logic.
- A new cycle performs `start -> provider -> smoke -> screening -> human review` and persists every command, transition, failure, and result.
- Provider failure, process timeout, engine failure, crash, illegal action, engine timeout, a screening win rate below 45%, or a statistically significant screening loss triggers explicit automatic rejection and evidence preservation.
- Surviving candidates stop in `REVIEW_REQUIRED`; neither benchmark success nor a favorable screening result accepts the candidate.
- Human-review packages contain the hypothesis, mechanism, provider record, benchmark statistics, failure counts, decision-time measurements, a bounded unified diff, and mechanism-aware review questions.
- The review gate can reject and archive a candidate or authorize deep evaluation. Final private acceptance is a separate confirmation-stage human action and cannot promote the active submission.
- Added separate `auto_accept: false` and `auto_promote: false` policy controls to make those boundaries explicit.
- Verified the complete local success path with Hydrapple `EXP-0003`, an intentionally behavior-neutral comment fixture. Smoke finished 9-11 over 20; screening finished 54-46 over 100 (`p=0.424`), with zero draws, timeouts, illegal actions, or crashes. A review package was generated, mechanism-aware wording was checked, and the fixture was rejected and archived. Hydrapple remained `v000-baseline`.
- The first attempted live Codex worker was blocked before experiment creation because sending private project source/context to an external provider required explicit authorization. After the user explicitly authorized that transmission, the live path proceeded.
- Codex's nested Windows sandbox initially could not spawn PowerShell (`CreateProcessAsUserW failed: 5`). The adapter now uses Codex's managed `--approve-for-me` policy, which reports `workspace-write` and `on-request`, while the disposable workspace, outer timeout, and post-run fingerprint gate remain authoritative. A harmless comment-only probe verified that Codex could read context and edit only root `main.py`; the probe was rejected.
- The authorized live strategic run, Hydrapple `EXP-0006`, generated a valid `attack_readiness_attachment` candidate and changed only `main.py`. Smoke finished 9-11 over 20 with no failures. Screening finished 40-60 over 100 (`95% CI 30.9-49.8%`, `z=-2.00`, `p=0.0455`) with zero draws, timeouts, illegal actions, or crashes. The controller automatically rejected it below the 45% floor before human review.
- Postmortem: the generated 100,000-point readiness bonus applied to Bench targets even though they normally cannot attack that turn, overwhelming the existing Active preference and recreating the previously measured harmful bench-first Energy-routing behavior. The provider/benchmark pipeline worked; the gameplay hypothesis implementation failed.

Phase 4 is complete because a real provider-generated candidate traversed provider isolation, changed-file validation, local engine smoke, screening, statistical policy, and automatic rejection without changing the accepted specialist or active submission.

### Phase 5: Central deck-agent tournament — complete

- Added an isolated pair runner that binds each private agent to its own private deck, swaps the complete pair between seats, and alternates first player game by game.
- Matchup results separate strategic wins/losses from agent crashes, illegal actions, engine failures, and step-cap timeouts. Per-pair and per-seat timing, orientation results, Wilson interval, and head-to-head null-test statistics are retained.
- Added the central tournament coordinator, readiness and active-experiment gates, immutable entrant hashes, per-match subprocess isolation and logs, matchup matrix, field ranking, and Markdown report.
- Ranking gives fault-free operation priority, then field win rate, worst matchup, and average decision time. Results are advisory: `auto_promote` is fixed to false and the tool has no submission-copy operation.
- A successful smoke benchmark now records static, runtime-import, and smoke validation in specialist status, closing a lifecycle-state gap found while preparing the second entrant.
- Created `Claude_Grass_Venusaur` from the existing legal deck and the shared baseline. Its unchanged infrastructure experiment passed runtime play at 13-7 over 20 games with no failures and was rejected because it contained no strategic change. Both pilot entrants are now `READY_FOR_EXPERIMENT`.
- Final infrastructure pilot: Hydrapple 13, Claude Grass Venusaur 7 over 20 games, with exactly 10 games per seat orientation and zero draws, timeouts, illegal actions, agent crashes, or engine crashes. Hydrapple's 65% result had a 95% Wilson interval of 43.3-81.9% and `p=0.180`; it is explicitly inconclusive and does not justify promotion.
- Python compilation, matchup/tournament JSON Schema validation, game-accounting invariants, registry/status consistency, and active-submission hash checks passed.

Phase 5 is complete as infrastructure. A real selection tournament still needs more independently tuned specialists and the configured powered sample size; the 20-game pilot is not gameplay evidence.

### Phase 6: Controlled submission promotion — implementation complete, real promotion correctly unavailable

- Added a separate promotion policy and `promote_candidate.py` lifecycle: `request -> approve -> execute -> optional rollback`.
- A request requires a privately accepted specialist, at least 500 confirmation games, two cross-deck opponents, exact registry/status/tournament hashes, rank one without agent faults, at least three tournament entrants, and at least 300 games per seat.
- Approval requires an explicit reviewer, reason, and acknowledgement that the active submission will change. Approval and execution are separate commands; no tournament or specialist worker can invoke promotion automatically.
- Execution snapshots the current submission pair, atomically replaces both files, validates deck and Python interfaces, runtime-imports from the competition environment, runs a complete-pair smoke plus `benchmark.py` from the real submission directory, and writes a manifest. Any failure restores both snapshot files before returning an error.
- Explicit rollback restores the preserved pair and verifies both hashes. Promotion requests, approvals, executions, failures, and rollbacks are retained in an append-only report.
- Isolated tests passed for successful pair replacement, explicit rollback, and automatic rollback after a simulated partial-copy failure. The real controller rejected the current pilot at 10 games per seat against a 300-per-seat requirement before creating a request or touching submission files.

Phase 6 is code-complete, but no real promotion has occurred because no candidate currently meets its evidence requirements.

### Phase 7: Decision-difference evidence — complete

- Added a bounded shadow-policy trace that runs the candidate in real engine games and asks a separate baseline module what it would choose from each exact candidate-controlled observation.
- The candidate alone advances the game. The trace therefore measures where policy choices differ without pretending to simulate counterfactual outcomes for the baseline choice.
- Each retained difference includes the selection type/context, candidate and baseline choices, compact option metadata, and a live board summary. Trace and option counts are capped by policy.
- Screening and confirmation review-pack generation now requires an error-free trace and includes aggregate difference rates, context counts, and representative examples.
- Trace artifacts have a JSON Schema and are included in the consolidated platform verifier.
- A 20-game Hydrapple `EXP-0006` fixture captured 76 different choices across 1,296 candidate decisions in 18 games, with no trace errors. It also exposed indirect MAIN-action differences caused by the candidate's changed attachment logic inside search.

Phase 7 is evidence infrastructure. Its 20-game trace is for human logic inspection and behavioral attribution, not statistical proof that a candidate wins more games.

### Phase 8: Scalable multi-provider worker pool — complete; execution paused for deck selection

- Expanded the scheduler from two global specialist processes to five.
- Added enforced provider ceilings: two concurrent Codex jobs, three concurrent Claude jobs, and one optional Antigravity/Gemini job subject to the five-process global cap.
- Provider saturation no longer blocks other queued providers: a third Codex job waits while an available Claude job can still start.
- One active experiment per specialist remains mandatory, so concurrency scales across decks without allowing two workers to overwrite one deck specialist.
- Scheduler status now reports global capacity, provider ceilings, and active jobs per provider.
- Specialist onboarding remains dynamic: a newly validated deck specialist can be queued without changing scheduler code. Unused slots remain empty rather than inventing deck strategies.
- After explicit human source-egress authorization, Hydrapple `JOB-00001` started under Codex and Claude Grass Venusaur `JOB-00002` started under Claude. Both entered bounded screening; three global slots remain available for future specialists.
- The live scheduler was subsequently stopped at a safe boundary so deck selection could precede further agent tuning. Both jobs are closed and their evidence is retained. Hydrapple remains the only confirmed deck choice; no replacement candidate was activated.

The worker pool changes throughput, not the evidence bar. Every specialist still follows independent `20 -> 200 -> human review -> 300 -> 500 -> cross-deck` gates, and acceptance and promotion remain human-controlled.

The first selected four-deck cycle is now active: Hydrapple and Fire run on pinned
Codex `gpt-5.5`, while Grass and Dark run on pinned Claude `opus`. Each uses the
exact evaluated deck CSV in a separate specialist directory. New specialists first
passed runtime import and an unchanged 20-game smoke readiness check; those neutral
experiments were rejected before strategic workers started.

Tournament reporting is now progressive: every result directory keeps its immutable detailed `REPORT.md`, while `sub-agents/tournaments/REPORT.md` is an append-only cross-run ledger. It backfills existing runs once, prevents duplicate tournament IDs, records version/hash changes, and compares rank, field win rate, and worst-matchup rate with the latest same-field run. Unchanged code/deck hashes make clear when an observed delta is benchmark variation rather than implementation progress.

### Phase 5 extension: Continuous evidence scheduler — implemented, live start awaiting source-egress approval

- Added a persistent hypothesis queue with one experiment per specialist, two-specialist concurrency, daily start budgets, stored fresh seeds, subprocess logs, scheduler/state locks, graceful stop requests, and append-only transition history.
- A live job must explicitly authorize sending its isolated `main.py`, `deck.csv`, and copied strategy/rules context to its configured external coding provider. The scheduler refuses unauthorized jobs.
- The automatic path is now 20-game smoke followed by 200-game screening. Survivors stop at human review. Human approval authorizes 300-game main evaluation, a fresh-seed 500-game confirmation, and 200 total games against each available cross-deck opponent.
- Private acceptance now requires confirmation, two completed cross-deck opponents, and a separate final human approval. Automatic rejection remains allowed; automatic acceptance and active-submission promotion remain forbidden.
- Two grounded jobs are staged: Hydrapple active-only attack-readiness attachment and Venusaur attacker concentration. Both remain `awaiting_provider_authorization`; no source was sent and no coding provider was called.

### Not implemented yet

- Live end-to-end confirmation, multi-opponent evaluation, and promotion using a candidate that actually clears every gate.
