# Pokémon Hackathon — Progress Log

Local change log for this repo. Every implementation gets recorded here, newest first,
signed with the implementer's name at the end of the entry.

**APPEND-ONLY.** Never edit or delete an existing entry — only add new ones. This log is
a permanent record; past entries stay exactly as written, even if later reverted (note
the reversal as a new entry instead).

---

## 2026-08-15

- **Dreepy-first setup finally tested for real and rejected; tempo diagnostics
  found a far larger gap (`EXP-0011`)**:
  - `EXP-0011` passed the new non-inertness gate (4 of 20 `SETUP_ACTIVE_POKEMON`
    selections differed; Dreepy picked 13 vs baseline 10, Fezandipiti ex 1 vs
    3), making it the first genuine test of the replay-derived opening
    hypothesis after three inert attempts. Smoke `12/20` (60.0%); screening
    `95/200` (47.5%, `z=-0.707`, `p=0.480`); 0 draws, illegal actions, or
    crashes.
  - Rejected. The hypothesis is now tested and unsupported: the replay
    correlation between Dreepy openings and wins reflects deck draw rather than
    a decision advantage. The baseline already picks Dreepy whenever it is
    offered against worse options, and roughly 80% of setup Active selections
    are single-option forced, so the reachable headroom was always small.
  - Added `sub-agents/shared/tools/tempo_census.py` for the next diagnostic:
    first-use turn of named attacks and first turn a named Pokemon becomes
    Active, split by win and loss. Its first run crashed in 17 of 30 games
    (`player.active[0]` is `None` in the window between a knockout and its
    replacement), which truncated those games and biased every statistic; fixed
    and re-run clean before anything was read from it.
  - Verified the `turn` field is a **ply counter** — it alternates acting seat
    on each increment, so a player's Nth turn is roughly ply `2N`. The replay
    analyzer reads the same raw `current["turn"]` field, so replay and
    simulator numbers are directly comparable.
  - Baseline over 30 clean games versus curated replays, on winning games:

    | Metric | Replays | Local baseline |
    |---|---|---|
    | First Phantom Dive | 9.08 | 13.64 |
    | First Dragapult ex Active | 8.00 | 11.42 |

    The local pilot is about 4.6 ply (~2 full turns) slower to its first
    Phantom Dive and about 3.4 ply slower to get Dragapult ex Active. Replays
    attack roughly one ply after Dragapult arrives; locally it takes 2.2. So
    the agent is slower both at assembling the Dragapult line and at attacking
    once it is assembled.
  - Phantom Dive usage tracks winning strongly in local play too (37 uses
    across 12 wins vs 11 across 18 losses), while Itchy Pollen dominates losses
    (32 vs 22) — consistent with the replay report.
  - Caveat on the comparison: local games are mirror matches against the same
    agent, while replays are against varied opponents, so absolute turn numbers
    are not strictly equivalent. The size of the gap, not its exact value, is
    what motivates the next hypothesis.
  - **Next hypothesis:** accelerate the Dragapult line (evolution and Energy
    prioritization toward Dreepy → Drakloak → Dragapult ex) rather than any
    further setup-selection work. This is the first PalSystem lever with a
    measured multi-turn gap behind it.

  — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Root-caused three inert PalSystem setup candidates and built the tooling
  that catches them (`EXP-0009`, `EXP-0010`, `EXP-0011`)**:
  - Built `sub-agents/shared/tools/setup_census.py` to answer the question
    `decision_trace.py` structurally cannot: it records *every* selection
    context an agent is asked plus what it picks during setup, instead of only
    candidate-vs-baseline differences. A candidate whose hook silently no-ops
    produces an empty difference table, which is indistinguishable from a
    candidate that works — that blind spot is what let `EXP-0007` and
    `EXP-0008` each burn 220 games measuring nothing.
  - The census proved setup selections *do* reach the agent (~3 per game) and
    that `SelectContext.SETUP_ACTIVE_POKEMON == 1` — so `EXP-0007` (named
    contexts) and `EXP-0008` (numeric contexts) had tested the identical
    condition. The real defect was different: **setup options carry
    `option.cardId is None`**. Both candidates ranked every option equally and
    the stable sort reproduced baseline order exactly. Setup options identify
    their card by `area == HAND (2)` plus `index` into
    `current.players[yourIndex].hand`.
  - `EXP-0009` never ran: the `codex` CLI disappeared from the machine
    (`where.exe codex` finds nothing; absent from PATH, npm global, and the
    hermes venv), so the provider stage failed with exit 2 and the orchestrator
    auto-rejected it. Infrastructure failure, not evidence.
  - `EXP-0010` was written by Codex from a prompt supplied by Claude, then
    staged manually with `run_experiment.py start` since no provider was
    available. It was **inert because of a wrong engine fact in that prompt**:
    Claude asserted hand entries were Card objects exposing `.name`. They are
    `Card(id, serial, playerIndex)` and expose only those three fields; the
    name requires an `all_card_data()` lookup keyed on `hand[index].id`. The
    patch read `getattr(hand[i], "name", None)`, got `None`, and fell back to
    baseline on every setup selection. Direct A/B on identical observations:
    20/20 setup choices identical. Trace: 124 differences, all `MAIN`.
    Screening `101/200` (50.5%, `p=0.888`) measured nothing. Rejected.
  - The census's own `card_name()` helper had masked the flaw by trying `.name`
    first and falling through to an id lookup, so resolved names appeared in
    the report and Claude read that as proof the attribute existed. The helper
    now resolves *only* via `hand[index].id`, matching what an agent must do,
    and both tools document the trap.
  - Added `sub-agents/shared/tools/context_ab.py`: asks candidate and baseline
    for a choice on the *same* observation, restricted to one context, and
    reports agreement plus resolved card names on both sides. It exits non-zero
    on `inert` or `no_observations`. All three failed candidates would have been
    caught by it in under a minute, before any benchmark.
  - `EXP-0011` is Codex's `EXP-0010` patch with the one-line resolution fix
    (`_card_data().get(hand[opt.index].id)`, the idiom already used at line 138
    of the baseline). It **passes the non-inertness gate**: 4 of 20 setup
    selections differ from baseline, Dreepy picked 13 vs 10 and Fezandipiti ex
    1 vs 3 — the intended shift. Smoke `12/20` (60.0%), 0 draws, 0 crashes.
    Screening pending.
  - Known ceiling: most `SETUP_ACTIVE_POKEMON` selections offer a single forced
    option, so only ~20% are genuine choices. Even a correct Dreepy-first rule
    can only move a minority of openings, and the effect should be expected to
    be small.
  - Operational note: Codex edited
    `snapshots/v000-baseline/main.py` directly — that snapshot is the immutable
    comparison target. The patch was extracted and the baseline restored, but
    `git restore` rewrote it with CRLF endings and broke the `agent_sha256`
    gate (`existing snapshot does not match accepted v000-baseline`). Restoring
    the blob with LF bytes returned it to `dba17948…`. Worker prompts should
    name the candidate path, never the snapshot.
  - **Reason:** three consecutive candidates passed validation while changing
    no behavior, and one of those was caused by a wrong fact Claude supplied to
    the worker. Verifying a mechanism actually fires now precedes spending
    games on it.

  — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>
  / <span style="background-color:rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **PalSystem numeric setup-context retry (`EXP-0008`) tested and rejected**:
  - Context: `EXP-0007` failed because it checked named setup contexts
    (`SETUP_ACTIVE_POKEMON` etc.) while raw replay observations use numeric
    contexts. Before retrying, the replay analyzer
    (`palsystem_games/analyze_replay_patterns.py`) was corrected twice: it now
    identifies the PalSystem seat from the actual submitted deck action instead
    of visualizer deck data, and it uses the raw option constants
    (`SELECT_MAIN=0`, `SELECT_CARD=1`, setup Active context `1`, setup Bench
    context `2`, `PLAY=7`, `ATTACH=8`, `EVOLVE=9`, `ABILITY=10`, `RETREAT=12`,
    `ATTACK=13`, `END=14`).
  - Corrected report over 87 usable replays (58 wins / 29 losses) supports
    Dreepy-first: opening Active in wins was Dreepy 31, Budew 17, Munkidori 16,
    Meowth ex 7, Fezandipiti ex 4; setup Bench in wins was Dreepy 14,
    Munkidori 4, Meowth ex 1. First Phantom Dive turn averaged 9.08 in wins vs
    9.58 in losses.
  - `EXP-0008` ran that hypothesis narrowly against numeric contexts only:
    `sel.type == 1` with context `1` → Active priority Dreepy, Munkidori,
    Budew, Meowth ex, Fezandipiti ex; context `2` → Bench priority Dreepy,
    Munkidori, Meowth ex, Fezandipiti ex, Budew. No MAIN-phase play, Energy,
    Trainer, Ability, attack, evolution, or damage-target logic was touched.
  - The Codex candidate diff was clean and on-mechanism: it added
    `_raw_enum_value` to unwrap enums to ints, `_card_name`, and
    `_setup_replay_priority_choice`, called from three lines ahead of the MAIN
    cascade and returning `None` for every other context.
  - Results: smoke 8-12 over 20 games (40.0%); screening 104-96 over 200 games
    (52.0%, `z=0.566`, `p=0.572`), zero draws, timeouts, illegal actions, or
    crashes; mean/max decision time 8.43 ms / 673.50 ms.
  - The trace gate failed again for the same reason as `EXP-0007`: all 118
    retained differences over 20 trace games were `MAIN/MAIN`, with zero
    differences in CARD context `1` or `2`. Switching from named to numeric
    contexts did not make the setup decision observable, so the screening
    number is still measuring cascade noise, not Dreepy-first setup.
  - `EXP-0008` was rejected without escalating to deep evaluation.
  - Operational note: the earlier interrupt did not kill the orchestrator —
    pid 20616 stayed alive and held `.orchestrator.lock`, so a `resume` attempt
    correctly refused with `specialist is locked by another orchestrator`. The
    original run finished screening on its own at 08:01 UTC. Also note that
    `kill -0 <pid>` in Git Bash cannot see Windows PIDs; use `Wait-Process`.
  - **Next sequence:** (1) build setup-trace tooling that records whether
    `_setup_replay_priority_choice` fires at all and what it picks, by card
    name — two consecutive rejections on the same blind spot mean the tooling,
    not the hypothesis, is the bottleneck; (2) separate first-Phantom-Dive
    tempo diagnostics; (3) isolated Energy routing (never bundled with setup —
    prior bundled attempts regressed); (4) Phantom Dive spread targeting. The
    analyzer still reports ability source as `unknown`; resolving ability
    options via area/index is a later improvement.

  — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **PalSystem replay-inspired setup hypothesis tested and rejected in the
  specialist loop**:
  - Closed the paused disruption-timing experiment (`EXP-0006`) before starting
    new work. Its evidence was weak (`107/200`, 53.5%, `p=0.322`) and the
    independent review requested mechanism-level traces, so it was rejected to
    unblock the next isolated PalSystem hypothesis.
  - Started `EXP-0007` from the replay curation signal: test Dreepy-first
    opening Active / setup Bench discipline only, with no intended change to
    MAIN-phase play, Energy, Trainers, Abilities, attacks, evolution, or damage
    targeting.
  - The candidate passed legality but failed the evidence gate: smoke was
    10-10, screening was 96-104 over 200 games (48.0%, `p=0.572`), with zero
    draws, timeouts, illegal actions, or crashes.
  - Decision traces showed the important implementation flaw: all 127 retained
    differences were `MAIN/MAIN`, not opening/setup CARD selections. That means
    the candidate did not isolate the replay hypothesis; it changed ordinary
    MAIN sequencing through cascade effects and therefore could not answer
    whether Dreepy-first setup is good.
  - `EXP-0007` was rejected. The replay hypothesis remains plausible, but the
    next attempt needs simulator-verified setup context detection before any
    benchmark, or a dedicated decision-trace tool that captures initial setup
    selections by card name.
  - **Reason:** keep the PalSystem specialist loop evidence-driven. A losing
    candidate that does not exercise the intended decision context should be
    closed quickly, not escalated into deeper games.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **PalSystem replay curation pass — setup signal found, but no `main.py`
  change retained**:
  - Reviewed the curated `palsystem_games/replays/` logs by identifying the
    PalSystem seat from the submitted 60-card deck. The usable sample covered
    87 non-error games: 58 wins and 29 losses. The clearest gameplay signal was
    setup discipline: PalSystem wins opened Dreepy far more often than any other
    Basic, while generic static-card ranking can overvalue higher-printed-stat
    support Pokémon such as Fezandipiti ex, Meowth ex, or Munkidori.
  - Tried converting that replay signal into a PalSystem-detected `main.py`
    branch. The first version bundled setup priority, Basic Bench play priority,
    and Energy routing. It was legal but clearly regressed in the specialist
    smoke benchmark: 5-15 over 20 games against the frozen PalSystem baseline
    (`replay_policy_smoke_shared_main.json`).
  - Narrowed the branch to setup-only Dreepy-first Active/Bench choices. That
    removed the immediate regression in smoke (10-10 over 20 games), but the
    standard screening run did not justify keeping it: 97-103 over 200 games,
    no draws, no timeouts, no illegal actions, no crashes
    (`replay_setup_only_screen200_shared_main.json`, `p=0.671`).
  - The attempted policy was therefore removed from `main.py`; the active agent
    is unchanged. The useful retained knowledge is tactical, not shipped code:
    future PalSystem work should target Dreepy-first setup, but only through an
    isolated specialist experiment with decision traces proving the setup branch
    actually fires and improves results. Also note the earlier ID trap:
    Munkidori is card `112`; Budew is card `235`.
  - **Reason:** replay curation is valuable only if the resulting heuristic
    survives measurement. This pass prevented a speculative deck-specific branch
    from entering the shared submission after screening showed no improvement.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **PalSystem Dragapult progressive specialist campaign started**:
  - Added `sub-agents/continuous/campaigns/PalSystem_Dragapult.json` with five
    ordered, deck-specific hypotheses: Recon Directive before evolution,
    Crispin/Fire-Psychic-Darkness routing, Phantom Dive live spread targeting,
    Munkidori Adrena-Brain damage transfer, and timing-sensitive disruption.
  - The campaign uses isolated `gpt-5.5` Codex workers and the existing
    cross-provider review rule, so Codex-generated candidates are independently
    screened by Opus before deep evaluation.
  - The evidence path remains 20 smoke -> 200 screening -> AI review -> 300
    main -> 500 confirmation -> cross-deck checks -> final review. One mechanism
    is tested at a time; automatic acceptance, tournament promotion, and writes
    to the active shared `main.py` remain disabled.
  - **Reason:** begin measurable, continuous specialization of the selected
    Dragapult deck without bundling heuristics or risking the current submission
    before a candidate proves that it is stronger.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **PalSystem Dragapult dedicated specialist prepared with powered deck
  baselines**:
  - Created and registered the isolated `PalSystem_Dragapult` Codex specialist
    from `Decs/PalSystem_Dragapult.csv` and the frozen active-policy baseline.
    Static deck validation, Python validation, runtime import, and a fault-free
    20-game readiness smoke passed. The unchanged readiness experiment was
    explicitly rejected because it was infrastructure evidence, not a gameplay
    improvement.
  - Corrected the `.txt` headings from 14/36 to the actual 17 Pokemon and 33
    Trainers without changing the 60-card CSV. Added dataset-grounded specialist
    strategy notes covering Dreepy setup, Recon Directive ordering, Dragapult ex
    Fire/Psychic preparation, Munkidori Darkness routing, Phantom Dive spread
    targeting, support-card timing, and six narrow experiment families.
  - Ran two 500-game, seat-balanced comparisons with the exact same frozen agent
    on both sides. Dragapult lost 191-309 to Hydrapple (38.2%, 95% CI
    34.05-42.53%, `p=1.31e-7`) and beat No_Name_Grass 308-192 (61.6%, 95% CI
    57.26-65.76%, `p=2.13e-7`). Both runs had zero draws, timeouts, illegal
    actions, agent crashes, or engine crashes.
  - Results are retained under the specialist `benchmarks/` directory and are
    explicitly labeled deck-plus-generic-policy baselines. Hydrapple is the
    first improvement target; No_Name_Grass is the initial regression guard.
  - **Reason:** prepare one reproducible, deck-specific research target and
    measure its starting matchup position before specialized policy changes can
    confound deck strength with agent strength.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-08-14

- **Plan 1 Phase 12 complete — Strategy report claims verified and research
  evidence archived deterministically**:
  - Added `plan_1/strategy/STRATEGY_REPORT.md`, documenting the actual Plan 1
    outcome across architecture, public observations, legal-action generation,
    hidden-card beliefs, UCT/PUCT, self-play, deck interaction, causal
    experiments, failures, reproducibility, limitations, and compliance. The
    report explicitly concludes that the infrastructure succeeded while the
    final playing candidate failed generalization and was not promoted.
  - Added `MODEL_CARD.md` for the exact 8,192-feature Phase 8 candidate. It
    records training provenance, intended use, Phase 8 teacher-target dominance,
    the 960-game Phase 9 rejection, Phase 11 runtime behavior, and a clear
    `do not submit` decision until a new candidate passes the frozen gate.
  - Added `REPRODUCIBILITY.md` with environment assumptions, phase commands,
    fresh-versus-resumed Phase 9 guidance, archive verification, and the native
    engine's complete-game seed-replay boundary.
  - Added `DATA_RETENTION_CHECKLIST.md`, inventorying competition card/deck
    data, simulator files, raw games, trajectories, checkpoints, reports,
    submission packages, and external card images. No deletion was performed.
    The checklist requires a final signed-in review of both competition rule
    pages because no machine-readable post-competition deletion clause could be
    verified; it does not invent a deadline or authorize broad deletion.
  - Added `claims.json` and `plan1.archival`: 10 major report claims are bound to
    20 exact JSON paths and expected values. The publisher fails closed on
    missing evidence, value drift, unsafe paths, unmatched include patterns,
    manifest corruption, undeclared archive entries, or content-hash mismatch.
    All 20 checks passed.
  - Added strict `phase12_archive.json`, `run_phase12_archive.py`, and three
    archival regression tests. The deterministic evidence ZIP contains 189
    files covering Strategy documents, configs, source, tests, preserved phase
    reports, manifests, checkpoints, frozen evaluation decks, and specialist
    policies. A stale empty fixture glob was caught by the fail-closed builder
    and removed. The report glob was then narrowed to Phases 0-11 so a rerun
    cannot ingest its own prior Phase 12 report.
  - Two consecutive archive builds were byte-identical: 896,933 bytes, SHA-256
    `6a4bae2cc717f20645fdc9268c3cc3d0bd57c8ac38418a98958094916db5ef41`.
    The final integrity-signed archival report SHA-256 is
    `66bfe889f38a6446743ca34c2e49931e4c93905ed8ed913267668d8804960663`.
    All 114 Plan 1 tests pass; active `main.py` and `deck.csv` remain unchanged.
  - **Reason:** make every important Strategy claim independently checkable,
    preserve enough code/data identity to reproduce the rejected evaluation,
    document negative results as carefully as successful infrastructure, and
    leave compliance cleanup explicit without deleting evidence prematurely.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 Phase 11 complete — exact candidate packaged and shadow-validated;
  promotion remains rejected on strength**:
  - Added `plan_1/src/plan1/deployment/` with strict deployment configuration,
    deterministic package assembly, a complete per-file hash manifest, path and
    undeclared-file validation, and deterministic ZIP output. The package
    contains the exact 8,192-feature checkpoint used by the Phase 9 candidate,
    its selective-budget search configuration, Hydrapple deck, bundled Plan 1
    source, and the frozen heuristic policy as fallback. The independent
    2,048-feature Phase 10 size experiment was deliberately not substituted
    because it lacks the exact candidate's playing-strength evidence.
  - Added a Kaggle-style lazy runtime entry point with three levels of failure
    handling: learned PUCT when the checkpoint loads, heuristic MCTS when the
    model is missing or corrupt, and deterministic greedy/minimal legal fallback
    if search or imports fail. The competition API remains a runtime-provided
    dependency and the package performs no network calls.
  - Added `phase11_probe.py`, `run_phase11_suite.py`, and strict
    `phase11_deployment.json`. Fresh isolated Python processes verified imports,
    exact 60-card loading, model initialization, missing-model degradation, and
    corrupt-model degradation. Both model fault injections reached
    `ready_heuristic` instead of crashing or forfeiting.
  - Built `plan1-shadow-submission.zip`: 66 declared files, 144,042 bytes,
    SHA-256 `de72e6339b2dabd602fd686e762e92546cabf2e0416f149d51b3a0f3bf7f0057`.
    Import measured 3.25 ms and model load 4.11 ms in the local clean-process
    probe.
  - Ran 12 seat-alternated full shadow games against the active heuristic using
    the exact packaged entry point. All 12 completed without faults. The package
    made 815 measured decisions at 19.24 ms p95 and 80.64 ms maximum, inside the
    declared 50 ms p95 and 250 ms hard validation limits.
  - Bound the package to the immutable 960-game, 40-matchup Phase 9 evaluation
    by candidate-checkpoint hash. Packaging and runtime gates pass, but that
    frozen report conclusively rejects development and held-out strength. The
    integrity-signed report therefore records `shadow_validation_passed=true`,
    `promotion.decision=rejected`, and `replace_active_submission=false`.
    Report SHA-256:
    `1753e34442b46ba3e114fd7cead812c4b408a781e58142c5ed612a726573eddf`.
    All 111 Plan 1 tests pass; active `main.py` and `deck.csv` remain unchanged.
  - **Reason:** separate deployability from playing strength. This phase proves
    that the exact research policy can be packaged, loaded, fault-contained,
    and run inside local deployment limits without turning successful packaging
    into a false claim that the rejected agent should replace the submission.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 Phase 9 resolved at promotion sample size — selective-budget
  candidate rejected**:
  - Added process-isolated parallel execution to the Phase 9 league runner.
    Match workers execute battles independently while the coordinator alone
    validates cached artifacts and publishes reports, preserving deterministic
    resume and avoiding concurrent writes. Added `--workers` to
    `run_phase9_suite.py` and regression coverage for the promotion config.
  - Added `plan_1/configs/phase9_promotion_gate.json`: 40 seat-balanced
    matchups at 24 games each, for 960 games total. Twenty-four games per
    matchup leaves room for draws while targeting the declared minimum of 20
    decisive games. The same frozen three-deck development field, two held-out
    decks, checkpoints, specialists, search configuration, and gate thresholds
    were retained. Four workers completed the run in 885 seconds with zero
    safety failures.
  - The candidate scored 139-186 with 35 draws on development (42.77%; Wilson
    95% lower bound 37.51%) and 184-282 with 14 draws on held-out decks (39.48%;
    lower bound 35.15%). Its worst matchup win rate was 11.11%. Checkpoint
    round-robin play was 115-105 with 20 draws, cross-deck specialist play was
    169-289 with 22 draws, and same-deck specialist play was 39-74 with seven
    draws. No dominance edge or cycle was detected.
  - Per-deck results were Hydrapple 84-84, Grass 32-87 with 49 draws, Fire
    60-108, LiamK Mega Lopunny 60-108, and Claude Mega Gardevoir 87-81. Six
    Grass-related matchups remained below 20 decisive games because each drew
    9-11 times. The aggregate development and held-out samples nevertheless
    exceeded 100 decisive games and independently failed mandatory strength
    floors, so additional games cannot rescue this candidate's gate result.
  - Corrected gate semantics to distinguish aggregate evidence from per-match
    evidence. A safety-clean candidate with powered aggregate samples is now
    `rejected` when a mandatory aggregate strength floor fails, rather than
    being mislabeled `insufficient_evidence` due to an unrelated draw-heavy
    pairing. The small Phase 9 screen remains correctly classified as
    `insufficient_evidence`.
  - Definitive report:
    `plan_1/artifacts/reports/phase9-promotion-gate.json` (SHA-256
    `0b1656e49e88b4dfa678d97654c3e1f5256b6d231a59cd53893c0416b1710500`).
    All 108 Plan 1 tests pass. Active `main.py` and `deck.csv` remain unchanged.
  - **Reason:** the earlier 80-game transfer screen could not settle
    generalization. This promotion-sized run supplies enough aggregate evidence
    to make the decision honestly: the current candidate is not strong enough
    across development or held-out opponents, so packaging must not be confused
    with promotion and the next playing candidate needs a model/training change.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 Phase 10 complete — selective-budget search chosen for research;
  compact model format measured**:
  - Added `plan_1/src/plan1/optimization/`, strict optimization/confirmation
    configurations, resumable per-match artifacts, causal search-variant
    round robins, latency/fallback/coverage aggregation, confidence intervals,
    head-to-head tests, frozen-corpus model-size training, and deterministic
    gzip export with exact round-trip checks. Added
    `plan_1/scripts/run_phase10_suite.py` and four optimization regression tests.
  - Phase 9 telemetry identified one dominant hot path: 3,749/4,425 searched
    decisions fell back for incomplete root coverage; only 8.50% reached full
    root coverage and 2.24% changed the heuristic choice. Direct model
    inference was already negligible relative to native simulation, so search
    coverage was optimized first and model compression stayed isolated.
  - The 90-game Hydrapple/Grass/Fire round robin separated two mechanisms.
    `selective_root` changed only `require_full_root_coverage`; it raised
    nonfallback choices to 79.85% but went 22-31 in the three-way field.
    `selective_budget` additionally changed the 24 ms allocation from an 8 ms
    search window/16 ms cleanup reserve to 16/8 ms and raised simulation/node
    caps. It led the field at 32-21, reached 79.38% full-root coverage, and used
    nonfallback choices on 75.16% of searched decisions. Both were 14-13 with
    three draws directly against baseline, and neither was accepted because the
    predeclared 30-decisive-game gate was not met.
  - A fresh 60-game confirmation compared only full-root baseline and
    selective-budget with the same checkpoint and three decks. Selective-budget
    won 30-23 with seven draws, reached 82.30% full-root coverage and 81.52%
    nonfallback choices, measured 20.62 ms maximum matchup p95, and had 0.034%
    hard overruns. It cleared the research-rescreen gate. The direct result is
    not statistically conclusive: 56.60% decisive, Wilson 95%
    43.27%-69.05%, two-sided `p=0.336`.
  - The unchanged 80-game Phase 9 transfer screen improved development from
    10-20 to 11-16 with three draws, held-out from 9-31 to 17-23, cross-deck
    specialist play from 10-30 to 17-23, and same-deck specialist play from 2-8
    to 5-4 with one draw. Checkpoint-peer play remained weak at 6-12 with two
    draws. Therefore `mcts_selective_budget.json` is the next research config,
    but Phase 9 remains `insufficient_evidence` and nothing is promoted.
  - Trained 2,048/4,096/8,192-feature models on identical frozen Phase 7 splits.
    The 2,048 model had the best held-out policy loss (`0.5725`), matched 82.71%
    top-1 and `0.1600` value Brier, measured `0.0476 ms` p95, and reduced JSON
    from 174,374 to 50,798 bytes. Deterministic gzip was 6,541 bytes (SHA-256
    `737a006db2c81c553303454a4672bdf8fede9907a96c1766d4e13eaf829d0912`)
    with exact restoration. This is a packaging recommendation only and was not
    substituted into search evidence.
  - Reports: `phase10-suite.json` SHA-256
    `bedd95bcf9d2d4a6022702e36c0c9def3ab6ec4525acb050bfafedeb1ed98451`;
    `phase10-confirmation.json` SHA-256
    `75239c11e2b08dcee1a59a62f7eced4ba75391daafa921d574c11ce70fd98716`;
    `phase9-optimized-screen.json` SHA-256
    `0924d357f62d6597447b2625334a5c2c433e5ef1beeaf26f2732b14a8458c061`.
    All 106 Plan 1 tests pass; active submission files remain unchanged.
  - **Reason:** the reinforcement loop was mostly replaying heuristic behavior
    because conservative full-root coverage discarded almost every bounded
    search. Phase 10 converts search into an actually exercised policy while
    preserving safety and latency, measures transfer before escalation, and
    reduces future package size without confounding playing-strength evidence.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 Phase 9 league/generalization framework complete; Phase 8 champion
  blocked from promotion**:
  - Added `plan_1/src/plan1/league/` with strict frozen-field configuration,
    checkpoint and external-module policy registration, development/held-out
    deck separation, deterministic matchup construction, seat-balanced engine
    games, Wilson intervals, per-category/per-deck summaries, historical
    regression checks, directed dominance evidence, and cycle detection. The
    promotion gate now requires safety, declared evidence minimums, multi-deck
    strength floors, a worst-matchup floor, and no catastrophic forgetting.
  - Added atomic per-matchup artifacts under
    `plan_1/artifacts/phase9/phase9-validation-v1/matches/`. A resumed run checks
    the full config identity, pairing identity, and game count before reusing
    evidence; stale or changed fields fail closed. Added
    `plan_1/scripts/run_phase9_suite.py`, strict
    `plan_1/configs/phase9_league.json`, and five league regression tests.
  - The frozen field uses Hydrapple, No Name Grass, and No Name Fire as
    development decks, with LiamK Mega Lopunny and Claude Mega Gardevoir held
    out. It compares the Phase 8 iteration-1 champion with the Phase 7
    checkpoint and Phase 8 iteration-2 league member, and integrates the
    Hydrapple/Grass/Fire Plan 2 specialists plus generic held-out opponents in
    same-deck and cross-deck pairings.
  - Completed 40 matchups / 80 seat-balanced games in 108.9 seconds with zero
    faults. The current Phase 8 champion scored 10-20 on development (33.3%,
    Wilson lower 19.2%), 9-31 on held-out matchups (22.5%, lower 12.3%), 7-13
    against checkpoint peers, 10-30 cross-deck against specialists, and 2-8
    against same-deck specialists. Its weakest individual pairing was 0%;
    Claude Mega Gardevoir was the weakest piloted deck at 2-12. Phase 8
    iteration 2 led the checkpoint table at 14-6, ahead of Phase 7 at 9-11 and
    the iteration-1 champion at 7-13.
  - The gate correctly returned `insufficient_evidence`, not promotion. Two
    games per pairing are below the declared 20-game matchup and 100-game
    aggregate minimums; the candidate also missed the strength floors. No
    dominance cycle is claimed because checkpoint pairs did not reach the
    configured 20-decisive-game threshold. This validates the league machinery
    while showing that a larger confirmation run on this candidate would be a
    poor use of compute.
  - Definitive report:
    `plan_1/artifacts/reports/phase9-suite.json` (SHA-256
    `e927f011139bb06d1d506cc18282e4fad07e08f3b16e305e62e89c31c599af2e`).
    All 102 Plan 1 tests pass. The active submission remains unchanged.
  - **Reason:** Phase 8's Hydrapple-only 5-3 screen could not measure historical
    regression, deck transfer, specialist strength, held-out archetypes, or
    cyclic dominance. Phase 9 creates that missing yardstick and supplies
    concrete evidence that search/model optimization must precede any larger
    promotion evaluation.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 Phase 8 complete — resumable three-iteration policy-value self-play
  loop**:
  - Added `plan_1/src/plan1/selfplay/` with strict reinforcement configuration,
    spawned native-simulator jobs, one-writer trajectory commits, bounded replay
    selection, warm-start candidate training, validation-only value calibration,
    deterministic candidate/champion evaluation, explicit promotion decisions,
    and an atomic coordinator ledger. Added
    `plan_1/scripts/run_phase8_loop.py` and the frozen validation configuration
    `plan_1/configs/phase8_reinforcement.json`.
  - Extended search traces with learned policy priors and self-play capture with
    legal-action priors, root visits, Q values, search diagnostics, checkpoint
    identities, and final outcome targets. Early turns may sample from completed
    root visit distributions; evaluation remains deterministic. Evaluation
    matches never receive a corpus writer and their IDs are checked against the
    training manifest.
  - Proved real interruption/resume: the first invocation generated and
    atomically committed iteration-1's eight games, then paused after self-play.
    Restarting the identical config incremented `resume_count` to one, skipped
    the committed batch, resumed at training, and completed all three iterations
    unattended.
  - Generated 24 Hydrapple mirror self-play games / 2,648 decisions with 18
    train and six validation games. The corpus has zero test or
    evaluation-purpose records, no evaluation-ID intersection, a valid complete
    manifest chain, and zero worker errors. Replay mixed the retained Phase 7
    bootstrap with recent self-play and stayed at complete-game boundaries.
  - Search-signal accounting is explicit: 279/2,648 decisions (10.54%) stored
    completed PUCT targets, 184 contained multi-visit policy distributions, and
    14 temperature-selected early actions differed from the visit argmax. The
    other 2,369 decisions used fallback/teacher targets because the conservative
    24 ms/full-root-coverage search did not clear. This proves the reinforcement
    path but shows it is still mostly behavioral cloning under the current
    budget.
  - Archived research decisions under one fixed rule (`safety`, candidate wins
    more games, and decisive win rate >=55%): iteration 1 scored 5-3 and was
    promoted internally; iteration 2 scored 3-5 and was rejected; iteration 3
    tied 4-4 and was rejected. The final internal champion is iteration 1
    checkpoint SHA-256
    `201111f01da276b4fe8e0c4ab623d563fa0ad5da0f81f4b96368b8bae1ead36c`.
    These eight-game screens validate state transitions; they do not establish
    statistically reliable superiority or authorize submission promotion.
  - Definitive report:
    `plan_1/artifacts/phase8/phase8-validation-v1/phase8-suite.json`
    (SHA-256
    `c76dbca3cc9ed8a31943738b135bee483ede717cf88714751069777c72a7c0c9`,
    report identity
    `cab6216ff981e4ce5b9a54343157fe0f5dc94a1e09497e418452764694575c31`).
    All 97 Plan 1 tests pass; explicit `py_compile` and `git diff --check` pass.
    The active `main.py` and `deck.csv` remain unchanged.
  - **Reason:** Phase 9 needs a proven feedback loop before adding historical
    opponents, multiple decks, held-out archetypes, and larger confirmation
    matches. This phase establishes resumability, data isolation, candidate
    lineage, and controlled promotion/rejection while exposing search coverage
    as the next technical ceiling.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 Phase 7 complete — supervised policy-value bootstrap and optional
  PUCT integration**:
  - Added an isolated, dependency-free policy-value learning stack under
    `plan_1/src/plan1/model/` and `plan_1/src/plan1/training/`. It uses
    deterministic hashed public-state/action features, masked softmax over only
    the generated legal actions, tanh outcome-value regression, strict
    checksum-protected JSON checkpoints, exact reload validation, and
    observation-limited live inference. No NumPy, PyTorch, ONNX Runtime, or
    network access is required for this bootstrap.
  - Extended `UCTSearch` and `Plan1MCTSAgent` with an optional policy-value
    interface. When supplied, learned legal-action priors order expansion and
    PUCT exploration is used; learned leaf value is conservatively blended with
    the handcrafted evaluator. The existing UCT path remains the default and
    its prior tests continue to pass unchanged.
  - Generated a fresh 48-game four-deck corpus through the immutable Phase 6
    store: 33 train games / 3,298 decisions, 10 validation games / 1,378
    decisions, and five untouched test games / 457 decisions. Split assignment
    remains at complete-game/seed-group granularity; evaluation data is never
    exposed to the learner.
  - Retained two instructive failures. The first broad value model overfit exact
    card/hand features and failed held-out Brier (`0.4027` vs `0.2451` constant).
    Calibration alone still failed (`0.2368` vs `0.2334`). The final value head
    therefore uses only general strategic signals: prize race, Active/board HP,
    attached Energy, Bench depth, hand/deck/discard counts, status, turn, and
    self-opponent differences. Card-specific public features remain available
    to the policy head.
  - Final untouched-test evidence: policy log loss `0.5393` vs `1.2583`
    uniform; top-1 policy accuracy `82.49%` vs `38.76%` uniform expectation;
    value Brier `0.1430` vs `0.2334` training-mean constant. Checkpoint reload
    reproduced predictions exactly. Direct inference was `0.0148 ms` median and
    `0.0633 ms` p95 under the provisional `5 ms` limit.
  - Final seat-balanced Hydrapple screen: learned PUCT 12 / heuristic UCT 8 /
    draw 0, zero faults, passing the predeclared 20-point non-inferiority gate
    (`p=0.0017` against the 30% null). This clears Phase 7's “no worse” screen;
    it is not treated as proof of superiority or as authorization to replace the
    active submission.
  - Definitive report:
    `plan_1/artifacts/reports/phase7-suite-v2.json` (SHA-256
    `2a0a983a5ddc909beadd2c270a25e2f4234b11135b871d8a9b6b9fb4b1b2b093`).
    Checkpoint: `plan_1/artifacts/checkpoints/phase7-bootstrap-v2.json` (file
    SHA-256
    `9d08d218f0625f0ab2698d3c0fc944d6a8d07e2c020b16f957e3fdae791c4e2a`).
    All 93 Plan 1 tests pass; `py_compile` and `git diff --check` pass. The live
    `main.py` and `deck.csv` have no diff, and the Grass campaign remained
    running independently during this work.
  - **Reason:** Phase 8 needs a reproducible learned policy/value baseline and a
    proven PUCT integration before unattended self-play can generate improved
    targets. Separating policy-rich features from low-variance strategic value
    features corrected measured overfitting while preserving legal masking,
    deployment simplicity, and causal evidence.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 2 Grass specialist campaign loop started for progressive hypotheses**:
  - Added campaign/backlog support to the continuous scheduler. Enabled
    campaigns live under `sub-agents/continuous/campaigns/` and enqueue the next
    pending hypothesis only when the specialist is idle, registered, and
    `READY_FOR_EXPERIMENT`. The one-active-experiment-per-specialist lock still
    applies, so a campaign cannot run two Grass edits at the same time.
  - Added `sub-agents/continuous/campaigns/Grass.json` for the `No_Name_Grass`
    specialist. The campaign uses Claude Opus and contains ordered, narrow
    hypotheses for core Bench-role construction, Yanmega/Buzzing Boost
    promotion, Mega Meganium Giant Bouquet live damage, and Solar Transfer
    minimum-lethal Energy movement.
  - Campaign jobs retain the normal evidence path: provider isolation, smoke,
    200-game screening, independent AI review, deeper evidence only after
    approval, and no active-submission promotion. Campaign hypothesis state is
    synced from the scheduler job state, so rejected/completed work advances the
    backlog instead of silently looping the same failed idea.
  - Restarted the visible scheduler with campaign support. It auto-enqueued
    Grass `JOB-00009` from `grass-campaign-001` and started screening with
    Claude Opus. Current first hypothesis:
    `grass_core_bench_role_priority`.
  - Updated README, Plan 2, and platform verification to document/check enabled
    campaigns. Active submission files were not changed.
  - **Reason:** Grass should continue making progress without requiring a manual
    enqueue after every rejected experiment, but the loop must still work from
    explicit hypotheses and preserve the same review/evidence gates.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 2 automatic independent AI review added to the continuous scheduler**:
  - Added `auto_review.py`, a dedicated review runner that reads the active
    pending review pack, invokes the assigned independent reviewer, stores the
    complete reviewer output under the specialist experiment, appends a bounded
    Markdown review note, classifies the recommendation as `reject`,
    `approve_deep_evaluation`, `more_evidence`, or `unclassified`, and can apply
    the existing auditable `review_gate.py` commands for clear reject/approve
    decisions.
  - Extended the continuous scheduler with `running_ai_review` and
    `waiting_more_evidence`. When `auto_ai_review` is enabled, a job that
    reaches `waiting_screening_review` now automatically starts the assigned AI
    reviewer. A clear reject closes the experiment, a clear screening approval
    authorizes deep evaluation, and `MORE_EVIDENCE` pauses the job instead of
    looping or spending more games.
  - Restarted the scheduler in a visible PowerShell window so the active loop
    uses the new code. It picked up Fire `JOB-00008`, ran the assigned Opus
    review, saved the artifact at
    `sub-agents/specialists/Fire/experiments/EXP-0003/reviews/screening-opus-auto-review.json`,
    and moved the job to `waiting_more_evidence`.
  - The automatic Opus review agreed the Fire candidate should not advance yet:
    107/200 screening is inconclusive, the first trace divergence happens with
    no Charizard in play, and regex/hardcoded Charizard damage estimates must be
    checked against engine-resolved damage before trusting lethal decisions.
  - Updated config, schema, contract, README, Plan 2, and platform verification
    so the auto-review phase is documented and checked. Active submission files
    were not changed.
  - **Reason:** the sub-agent loop should not stall until a human manually asks
    another AI to review every screening pack; independent AI review can safely
    reject, authorize deeper evidence, or pause for more evidence while keeping
    final acceptance and promotion human-controlled.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 2 review workflow executed and queue hardened for reviewer artifacts**:
  - Ran the independent review gate workflow on the current pending review
    packs. Codex-reviewed Grass `EXP-0003` and Dark `EXP-0002` were rejected
    through `review_gate.py` after written review evidence was added to their
    pending Markdown packs.
  - Sent Fire `EXP-0003` to the assigned Opus/Claude reviewer. Opus returned
    `MORE_EVIDENCE`, not approval or rejection, citing inconclusive 107/200
    screening evidence, broad MAIN trace differences, and the need to validate
    regex/hardcoded Charizard damage estimates against engine-resolved damage
    before trusting lethal decisions. The full Opus output is retained beside
    the review pack.
  - Hardened `review_queue.py` so auxiliary reviewer-output files in
    `human-review/pending/` do not break queue listing. The queue now cleanly
    shows only Fire `EXP-0003` as pending, assigned to Opus.
  - **Reason:** the new cross-review workflow must be usable in practice:
    reviewed experiments should close through the gate, while non-final reviewer
    artifacts should not corrupt the pending review queue.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 2 independent AI review routing added for sub-agent human-review
  gates**:
  - Review packs now record both the implementation worker identity and the
    assigned independent reviewer. Codex-authored experiments are routed to
    Opus/Claude review; Opus/Claude-authored experiments are routed to Codex
    review; unmapped providers default to Codex review until explicitly
    configured.
  - Added `sub-agents/shared/tools/review_queue.py`, which lists pending review
    packs globally or by reviewer with `--reviewer codex` / `--reviewer opus`.
    This gives a direct workflow for asking one AI agent to review the other
    agent's candidate without guessing from filenames.
  - Updated the shared agent contract, reviewer prompt, Plan 2 plan, and
    workspace README so reviewers inspect evidence, recommend approve/reject/
    more-evidence, and do not edit candidates or promote submissions.
  - Backfilled the current pending review packs with reviewer assignment
    metadata. Fire `EXP-0003` is Codex-authored and assigned to Opus; Dark
    `EXP-0002` and Grass `EXP-0003` are Opus/Claude-authored and assigned to
    Codex. Existing experiment decisions were not changed.
  - **Reason:** the same model family should not grade its own candidate. This
    keeps the sub-agent workflow independent while preserving explicit,
    auditable gate commands for final human-controlled accept/reject decisions.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 Phase 6 completed: atomic, resumable, versioned trajectory and replay
  pipeline validated on live native games**:
  - Added strict versioned records for terminal games and individual decisions.
    Each decision stores the public observation, selection/information-set
    identities, complete generated legal-action fingerprints and masks, chosen
    action, heuristic or search targets, belief diagnostics, acting/opponent
    policy identities, deck hashes, seed group, final result, and seat-relative
    value target. Hidden oracle state is not a policy field.
  - Added deterministic gzip JSON game files with bounded decompression, atomic
    flush/rename publication, file and canonical-content SHA-256 checks, and
    strict rejection of unknown schema fields. Incomplete games remain in
    memory and are never published; unrelated temporary files are ignored.
  - Added revisioned corpus manifests and a `CURRENT.json` pointer. Every
    revision links to the previous manifest hash, and loading now verifies the
    entire chain back to revision zero. Duplicate IDs are idempotent only when
    content hashes match; conflicting reuse is rejected.
  - Added deterministic complete-game/seed-group train, validation, test, and
    evaluation splits. The replay reader accepts only training-family splits
    and cannot request evaluation data. It reports outcome, deck, policy, and
    selection-context distributions for later sampling controls.
  - Added corruption recovery and retention. Damaged files are copied to a
    collision-safe quarantine before the repaired manifest is published;
    retention copies oldest training games to a recoverable retired archive
    before removing live entries and does not choose evaluation games first.
  - Added resumable heuristic-bootstrap generation using stable game IDs. The
    definitive run generated four games, reopened and extended to eight, then
    reran as a no-op with all eight recognized and zero duplicate writes. Two
    separately purposed evaluation games were added and remained absent from
    the training reader.
  - The definitive four-deck corpus contains **10 complete games / 1,111
    decisions**: eight training-purpose and two evaluation-purpose games. All
    records replay to their exact canonical content hashes, all 10 manifest
    revisions validate, and deliberate gzip truncation in a copied corpus was
    detected, quarantined, repaired, and followed by passing recoverable
    retention. The full Plan 1 suite passes **87/87** tests.
  - Compressed storage is **671,105 bytes**, **6.49%** of raw JSON, about **604
    bytes per decision**. Generation measured **0.347 games/s / 38.56
    decisions/s**. The small validation corpus populated train, test, and
    evaluation but happened not to populate validation; it proves plumbing and
    isolation, not dataset representativeness.
  - Exact replay currently means immutable record/schema/checksum replay. The
    local native `battle_start` has no seed argument, so exact native battle
    re-simulation cannot be claimed. Stored derived seeds identify jobs and
    split groups but do not control the native shuffle.
  - Definitive report SHA-256 is
    `74ffc965b337665f5037cdc9c311b237773418d547d06d014b29724a680b0a48`.
    No active submission or Plan 2 specialist file was changed. Phase 7, the
    supervised policy-value bootstrap, is next.
  - **Reason:** learning cannot be evaluated responsibly until complete games,
    legal policy targets, final value targets, data provenance, split isolation,
    interruption recovery, and corruption handling are reproducible and
    independently verifiable.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Phase 5 definitive evidence corrected after serial-leakage review**:
  - A final static review found that synthetic native card serial allocation
    could split otherwise identical public information sets because tuple-backed
    records were not traversed by the serial sanitizer. The sanitizer now
    traverses tuples as well as lists/dictionaries, and a regression test proves
    public information-set identity is invariant to native serial allocation.
  - Mirror-fill now also preserves revealed prize identities and their original
    zone positions, matching the corrected constrained sampler and native search
    input contract. The complete Plan 1 suite now passes **74/74** tests.
  - Regenerated the definitive 64-decision/four-deck report after both fixes:
    constrained belief sampled **256/256** valid and unique worlds with zero
    belief fallbacks, errors, or native faults; **206/256 (80.47%)** inner
    searches contributed root statistics. Generic agreement is **81.25%** with
    mirror-fill and **87.50%** with the offline oracle. Generic four-world
    latency is **233.55 ms median / 265.40 ms p95** under the research-only
    80 ms per-world budget.
  - This entry supersedes only the numeric evidence and hash in the immediately
    following Phase 5 entry; that historical entry remains unchanged under the
    append-only rule. The definitive report SHA-256 is
    `d7760895b7ae0bee86460d2eb274e64519acdfb76df2d5840dc6b0d93b090f9c`.
  - **Reason:** native allocation serials and revealed prize placement are
    reconstruction details, not hidden-world policy signals; correcting them is
    required before Phase 5 can honestly claim information-set safety.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 Phase 5 completed: constrained belief sampling and root-sampled
  ISMCTS validated without promoting a new submission agent**:
  - Added public-card accounting that subtracts visible board, discard, hand,
    stadium, and revealed-prize cards from declared 60-card deck mixtures, then
    samples hidden deck, prize, hand, and face-down Basic Active identities
    while preserving all public zone counts and revealed-prize positions.
  - Added public information-set keys and policy payloads that exclude sampled
    opponent hands, hidden deck/prize identities, private look data, logs, and
    option descriptors while retaining the acting player's legitimately visible
    hand and public board facts. The existing public record still never reads
    the opaque native `search_begin_input` payload.
  - Added root-sampled ISMCTS aggregation. Every determinization gets a fresh
    lifecycle-safe native search session; root statistics are shared only by
    public information-set and action fingerprints. Inner searches that return
    Phase 4's legal fallback are measured and excluded from aggregate evidence.
  - Added explicit comparison modes: the old repeated-card mirror-fill baseline,
    constrained generic deck-mixture belief, and an oracle that requires exact
    hidden zones injected through a separate local-visualizer extractor. Oracle
    state is therefore an offline diagnostic and cannot enter deployable policy
    features accidentally.
  - Added belief/ISMCTS unit coverage for conservation, impossible-state
    rejection, reported prior fallback, deterministic/diverse sampling,
    revealed prizes, public-key leakage, duplicate worlds, aggregate statistics,
    and safe fallback. The full Plan 1 suite passes **73/73** tests.
  - Definitive four-deck validation captured 64 decisions and sampled **256/256**
    valid generic worlds with 100% effective diversity, zero belief fallbacks,
    zero errors, and zero native faults. **201/256 (78.52%)** generic inner
    searches contributed root statistics; action agreement was **89.06%** versus
    mirror-fill and **85.94%** versus oracle. Generic four-world latency was
    **225.01 ms median / 265.13 ms p95** under a research-only 80 ms per-world
    budget. Report SHA-256 is
    `6e2e1bc684eeb10b804ae03112eb2b51b145cc4ae1d65040813495d2ed7b6591`.
  - Preserved the failed low-budget diagnostic, where fallback telemetry showed
    that most inner searches lacked root coverage, instead of presenting those
    fallbacks as ISMCTS evidence. Its SHA-256 is
    `a1980ebfc5bfe89f37e8aa92c3a15920b8b56c57740d5c34432a71c90e6c77d0`.
  - No active `main.py`, `deck.csv`, or Plan 2 specialist file was changed.
    Phase 5 validates the hidden-information boundary and exposes action
    sensitivity; it does **not** claim a strength gain or deployment readiness.
    Phase 6, the atomic/versioned trajectory pipeline, is next.
  - **Reason:** replace Phase 4's knowingly invalid repeated-card hidden-zone
    assumptions with a reproducible, leakage-safe uncertainty boundary before
    generating trajectories or training a policy-value model.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Fire and rebased Grass specialist screening authorized and started; Dark
  remains human-paused**:
  - After explicit human authorization, enqueued Grass `JOB-00007` for Claude
    and Fire `JOB-00008` for Codex. Each provider received only its specialist's
    isolated `main.py`, `deck.csv`, and standard copied context; Grass also
    received the revised `No_Name_Grass_Logic.txt` as `context/STRATEGY.md`.
  - Grass is testing the narrow `kangaskhan_active_yanma_bench_opening`
    hypothesis in `EXP-0003`: prefer Mega Kangaskhan ex as the opening Active
    when Run Errand is usable while preserving Yanma on the Bench for a later
    Buzzing Boost transition. Fire is testing the narrow
    `charizard_effect_damage_evaluation_v2` hypothesis in `EXP-0003`: account
    for Mega Charizard X/Y ex effect-driven damage and required Energy discard
    in lethal, attack, and immediate-attacker ranking without changing other
    Pokemon.
  - Started exactly one hidden persistent scheduler. At launch verification,
    Grass screening was alive as PID `2040` and Fire screening as PID `32732`;
    scheduler capacity recorded one active Claude worker and one active Codex
    worker. Historical Grass `EXP-0002` was reconciled as rejected because it
    was superseded by the revised deck baseline.
  - Dark was not relaunched. Its preserved `EXP-0002` evidence explicitly
    records `orchestration.state = PAUSED_BY_HUMAN`, so the scheduler leaves it
    at its existing human-review boundary until an explicit resume.
  - The quiescent-state platform verifier is intentionally not green during
    this run: it reports Fire/Grass active experiments and their live scheduler
    locks. Provider availability and stored experiment/JSON validation still
    pass; a complete clean verification must be rerun after the workers stop.
  - **Reason:** run the two authorized, deck-specific hypotheses in isolated
    workspaces while preserving Dark's pause and all prior evidence, with a
    single scheduler enforcing provider capacity and review gates.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Grass strategy/deck rebased, Dark explicitly paused, and Fire/Grass worker
  relaunch prepared but awaiting explicit provider payload authorization**:
  - Rewrote `No_Name_Decks/No_Name_Grass_Logic.txt` as a legal,
    state-dependent strategy specification. It now keeps Yanma on the Bench for
    Buzzing Boost, treats the two-Yanmega relay as a multi-turn plan, sequences
    Ciphermaniac before Run Errand, accounts for Kangaskhan's retreat/prize
    exposure, reserves Bench roles, calculates Mega Meganium lethal damage from
    live HP and attached Energy cards, and gates Boss's Orders/Solar Transfer by
    the live prize and retaliation state.
  - Replaced both Buddy-Buddy Poffin IDs (`1086`) with Bug Catching Set IDs
    (`1094`) in `No_Name_Grass.csv`. The revised list validates as exactly 60
    cards and contains two Bug Catching Set and zero Poffin.
  - Closed Grass EXP-0002 as superseded rather than comparing its 110-90 result
    against a changed deck. Added a reusable specialist rebase command and
    created `Grass/v001-deck-rebase`; revised Grass deck SHA-256 is
    `f6cadd59a7e6741e96f18754c0866f87e97ed85f87b3a4486e510f4ea0ae2448`.
    Historical `v000-baseline` and EXP-0002 evidence remain preserved.
  - Added optional `source_strategy` worker context. Future Grass workers receive
    the revised strategy as `context/STRATEGY.md` in their isolated workspace.
  - Added a reversible human pause/resume command and paused Dark EXP-0002 with
    its pending review and experiment evidence intact. The scheduler will not
    advance it while its orchestration state is `PAUSED_BY_HUMAN`.
  - Diagnosed Fire EXP-0002 as an orchestration failure, not a strategy result:
    Windows `cp1252` decoding crashed on UTF-8 Codex output before any candidate
    or games existed. `run_worker.py` now captures provider output explicitly as
    UTF-8 with replacement handling. Fire and rebased Grass both pass static and
    runtime validation; the complete sub-agent platform verifier passes.
  - Gracefully stopped two duplicate persistent scheduler loops before changing
    state. No scheduler currently runs. Fresh Grass and Fire jobs were prepared
    but **not enqueued and no source was transmitted** because provider launch
    requires explicit authorization for the exact private payload and external
    destination.
  - **Reason:** the new human Grass strategy and deck invalidate the old Grass
    baseline, Dark must pause without losing evidence, and Fire must not be
    retried through the same broken provider-output boundary. Explicit source
    egress remains a separate human-controlled security gate.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Phase 4 strength and horizon evidence regenerated with corrected fallback
  telemetry schema**:
  - Repeated the 40-game seat-balanced Hydrapple strength screen and 60-game
    Stage A/Stage B comparison after adding the actual fallback action to every
    `SearchResult`. The bounded Stage A candidate scored **15-25** against the
    unchanged current agent (`p=0.114`), so it still does not qualify for
    promotion. Stage B scored **33-27** against Stage A (`p=0.439`), still a
    statistical tie and therefore not justified as the default horizon.
  - Definitive strength evidence is
    `phase4-bounded-screen-h0-v2.json`, SHA-256
    `850dfe4a1b7d1d6ed87c760d37d539b284c4c716abf8e561c4183fa54352c9e2`.
    Definitive horizon evidence is
    `phase4-horizon-ablation-bounded-v2.json`, SHA-256
    `e97cd0cccdc8b545b01adc3922c0ced31c8347ab40cee7ee73e5b70060c7ce2c`.
  - **Reason:** all definitive Phase 4 reports should use the same corrected
    result contract; simulator chance means regenerated win counts may differ,
    but both new samples preserve the original non-promotion conclusions.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Phase 4 definitive-evidence correction — fallback overrides now compare
  against the actual fallback action**:
  - The Phase 4 completion entry below reported a **3.02%** fallback-change
    rate from `phase4-soak-final-v3.json`. That collector compared the chosen
    action with the first expanded root edge, not with the greedy fallback
    supplied to search, so that specific rate was not valid. Gameplay, action
    legality, timing, cleanup, and the strength/horizon outcomes were unaffected.
  - `SearchResult` now carries the actual root fallback action and
    `TraceCollector` compares directly against it. A regression test verifies a
    searched winning action is counted as an override when it differs from the
    supplied fallback. The complete Plan 1 suite now passes **61/61 tests**.
  - The superseding run used the same bounded Stage A profile through the newly
    aligned defaults and completed **500/500 games**, **125 per deck**, with
    **zero faults, illegal actions, crashes, errors, or 2,000-step timeouts**.
    Across 69,851 decisions, full-action timing was **12.701 ms p95 / 80.068 ms
    max**. Internal search was **10.135 ms p95 / 47.504 ms max**, with only
    **7/42,459 (0.0165%)** hard-deadline overruns. Root coverage was **16.22%**,
    and MCTS actually changed the greedy fallback on **2,659/42,459 (6.26%)**
    searched decisions.
  - Definitive safety evidence is now
    `plan_1/artifacts/reports/phase4-soak-final-v4.json`, SHA-256
    `270ac74a1e6c23de6b47dbfaeab816e49ec48771651904d8ef6fccf207ba8407`.
    The earlier `v3` report remains preserved as the first passing safety run
    but is superseded for fallback-override telemetry.
  - **Reason:** promotion and later learning work need trustworthy intervention
    rates; comparing with an arbitrary expanded edge could misstate how often
    MCTS changes policy even when all game-level results are correct.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 Phase 4 complete as bounded MCTS infrastructure, but rejected for
  submission promotion on current strength evidence**:
  - Implemented isolated `uct-v1` search with root-perspective UCT selection,
    opponent-node minimization, progressive widening, expansion and backup,
    terminal/heuristic leaf values, deterministic fingerprints and tie-breaks,
    current-turn and one-opponent-response horizons, loop/depth/node/simulation
    limits, wall-clock management, complete-root-coverage protection, legal
    fallback, and lifecycle-safe native-state cleanup. Search traces record root
    edge visits/values, cutoff and fallback reasons, coverage, overrides,
    errors, native steps, and deadline overruns.
  - Added `Plan1MCTSAgent`, four-deck soak/strength/horizon runners, exception
    containment, seat isolation, per-deck results, Wilson intervals and
    two-sided head-to-head z-tests. Added regression coverage for terminal
    backup, opponent minimization, KO-back horizon behavior, loops, hard caps,
    incomplete coverage, cleanup-on-error, deterministic ties, fingerprinting,
    and terminal state reached on the final permitted harness action. All
    **60/60 Plan 1 tests pass**.
  - The definitive bounded soak completed **500/500 games**, exactly **125 each**
    for Hydrapple, Fire, Grass, and Dark, with **zero faults, illegal actions,
    crashes, errors, or 2,000-step timeouts**. Across 65,943 decisions,
    full-action timing was **18.597 ms p95 / 73.721 ms max**, passing the
    predeclared **35/500 ms** host envelope. Internal search was **13.982 ms p95
    / 48.958 ms max**; **59/40,913 (0.144%)** searches crossed the nominal hard
    deadline, under the predeclared 1% limit. Evidence:
    `phase4-soak-final-v3.json`, SHA-256
    `161011e5e40652da552e7e321d4b9dd702ccb4992afb28aacf2ea993da44f9b4`.
  - Two failed profiles remain in the evidence trail. The first completed
    499/500 and exceeded a 350 ms maximum; the second completed 500/500 after a
    final-action terminal-accounting fix but exposed a **1.064 s** full-action
    tail. Internal UCT max was only 34.953 ms, identifying the nested shipped
    one-ply fallback as the unbounded component. The final candidate replaces
    that composition with deterministic greedy fallback and retains full-root
    coverage before any MCTS override.
  - Playing strength did **not** clear promotion. Bounded Stage A scored
    **14-26** against the unchanged current agent in 40 seat-balanced Hydrapple
    games (`p=0.0578`, negative direction). Stage B scored **32-28** against
    Stage A in 60 games, but this was a statistical tie (`p=0.606`). Final-soak
    full-root coverage was only **8.70%**, and MCTS changed fallback on only
    **3.02%** of searched decisions. The machinery is ready for later belief
    and learned-value work, but this heuristic candidate is not stronger.
  - Horizon evidence: `phase4-horizon-ablation-bounded.json`, SHA-256
    `99e7a3b7302e49cd4a7531f21b5b59c14bcbdce3627bc6136809f42a4367a2e1`.
    Strength-screen evidence: `phase4-bounded-screen-h0.json`, SHA-256
    `3bdb96f258ed367d394458eb7c411b4979dbb522c987d3800ed0c20ce57285ab`.
  - **Reason:** Phase 1 proved the simulator can branch safely and Phase 3
    supplied a public-state evaluator, but Plan 1 still needed a bounded search
    implementation and direct evidence of whether added depth helps. The
    failed runtime profiles also showed that a fallback must itself be bounded;
    composing bounded MCTS with an unbounded fallback defeats the time manager.
    Phase 4 records that correction and the honest non-promotion result before
    hidden-information or learning complexity is introduced.
  - The active `sample_submission/main.py`, active deck, and Plan 2 agents were
    not modified.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Phase 3 evidence-hash transcription correction**:
  - The exact SHA-256 of the definitive
    `plan_1/artifacts/reports/phase3-suite.json` is
    `49f27228c74b827e6be1e4aecadef54a9b37d13c4f77071659ef4ca5d8bd098f`.
    The immediately following correction entry omitted `cad` while transcribing
    that hash; its game, test, and timing results remain unchanged.
  - **Reason:** preserve an exact, machine-verifiable evidence pointer without
    rewriting the append-only historical entry.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 Phase 3 final evidence correction — once-per-turn legality added after
  the initial completion entry**:
  - Evolution readiness now excludes targets that entered play this turn, and
    Supporter/retreat availability now respects whether the acting player has
    already used that once-per-turn action. Dedicated regression tests cover
    both corrections.
  - The superseding verification is **46/46 unit tests**, **13/13 tactical
    fixtures**, and **40/40 live games** across Hydrapple, Fire, Grass, and Dark:
    **4,569 decisions**, **9,218 seat evaluations**, and zero perspective,
    scalar/breakdown, finite-value, bound, error, or timeout failures.
  - Scalar medians are **0.044-0.077 ms** and p95 is **0.074-0.114 ms** by deck.
    The definitive `phase3-suite.json` SHA-256 is
    `49f27228c74b827e6be1e4aef54a9b37d13c4f77071659ef4ca5d8bd098f`; this
    supersedes the report hash in the immediately following Phase 3 completion
    entry while preserving that entry under the append-only rule.
  - **Reason:** readiness features must represent actions that are legal now;
    otherwise MCTS would overvalue impossible evolution, Supporter, or retreat
    lines.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 Phase 3 complete — versioned handcrafted evaluator and tactical
  regression suite implemented without changing the active submission**:
  - Added `plan1.evaluation` with a catalog-indexed `handcrafted-v1` evaluator.
    Search uses an allocation-light scalar `score()` path, while `evaluate()`
    returns a component-by-component breakdown, metrics, and diagnostics for
    traces and human review. Terminal results have a hard override and every
    nonterminal term is built as root-minus-opponent, so switching perspective
    negates the score exactly.
  - Covered prize race and multi-prize liability, live HP and damage, immediate
    attack pressure, lethal and KO-back risk, survivability, status and retreat
    flexibility, attached/stranded energy and readiness, acceleration/ability
    potential, bench and evolution development, visible Trainer/Supporter
    access, deck-out risk, and exposed weakness/resistance. Energy payment
    handles Colorless, Rainbow, and Team Rocket Psychic/Darkness compatibility.
  - Added 13 named golden comparisons for terminal bounds, prize monotonicity,
    attacking instead of passing, useful energy, stall recovery, promotion,
    retreat, live-HP targeting, KO-back avoidance, weakness, evolution readiness,
    and decking risk. Added status-aware readiness so an Asleep or Paralyzed
    Active is not falsely scored as able to attack or retreat.
  - Added `run_phase3_suite.py`, which validates synthetic tactical fixtures and
    real public states from Hydrapple plus the Fire, Grass, and Dark decks. The
    definitive run completed **40/40 games**, **4,598 decisions**, and **9,276
    seat evaluations** with **0** perspective failures, scalar/breakdown
    mismatches, non-finite values, bound failures, errors, or timeouts. All
    **13/13 tactical fixtures** and **44/44 Plan 1 unit tests** pass.
  - Scalar evaluation measured **0.044-0.056 ms median** and **0.066-0.119 ms
    p95** by deck, or **11-28%** of the corresponding Phase 1 native search-step
    median. The tracked evidence is
    `plan_1/artifacts/reports/phase3-suite.json`, SHA-256
    `ce4fb6ba0ccddb5549d3be41d2aae4779df6fa4e36ee6030b9bf7c076f91546d`.
  - **Known limitation:** attacks whose text changes damage are deliberately
    evaluated from printed damage and tagged
    `dynamic_attack_damage_approximated`; the evaluator does not claim complete
    semantic interpretation of arbitrary card text. Phase 4 can measure whether
    effect-aware parsing is worth its search cost.
  - **Reason:** earlier one-ply search regressed because its leaf evaluation was
    myopic and could not price the opponent's reply. MCTS must not amplify that
    defect, so Phase 3 establishes a transparent, testable, public-information
    value function before tree search is introduced.
  - The active `sample_submission` agent and `deck.csv` were not modified.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Scouted Dipam Chakraborty (LB 1090.2) — his deck is OUR Hydrapple deck, 90%
  identical. The ~625-point ladder gap is the AGENT, not the deck**:
  - Pulled his list from public episode `92687782` via
    `kaggle.com/competitions/episodes/<id>/replay.json` (same route used for the
    LiamK and Majkel scouting). Leaderboard position checked directly: **1090.2,
    ~30th of ~6,500 teams** — strong, but not top-10 (leader `flg` is at 1220.9).
  - His 60: 20 Pokémon / 12 Item / 10 Supporter / 4 Stadium / 14 Energy. Lines are
    4 Teal Mask Ogerpon ex, 2/2/2 Applin-Dipplin-Hydrapple ex, 2/2/2
    Chikorita-Bayleef-Meganium, 2 Meowth ex, 1 Fezandipiti ex, 1 Tapu Bulu.
  - **Overlap with `Decs/Hydrapple.csv` (our active submission deck): 54/60 = 90%
    by card name.** His entire edge over our list is six slots:
    `+2 Ultra Ball, +1 Forest of Vitality, +1 Dawn, +1 Meowth ex, +1 Basic {G} Energy`
    against `-1 Boss's Orders, -1 Night Stretcher, -1 Celebi, -1 Briar,
    -1 Ciphermaniac's Codebreaking, -1 Regigigas`. He cut our scattered 1-ofs and
    spent the slots on consistency.
  - Head-to-head under our current agent, seat-balanced, 80 games each:

    | matchup | result |
    |---|---|
    | Dipam_Grass vs **Hydrapple** | 53.8% [42.9-64.3] — **TIE** |
    | Dipam_Grass vs No_Name_Grass | 82.5% [72.7-89.3] — Dipam better |
    | Dipam_Grass vs Claude_Grass_Venusaur | 80.0% [70.0-87.3] — Dipam better |
    | Hydrapple vs No_Name_Grass | 70.0% [59.2-78.9] — Hydrapple better |

  - **The headline:** his deck and our deck are statistically indistinguishable in
    play, yet he scores **1090.2** and our active submission scores **464.6**. Same
    deck, ~625 points apart. Deck is NOT our bottleneck. This is the cleanest
    evidence we have that agent quality dominates deck choice at our current level,
    and it supersedes the earlier working assumption that we needed a better deck.
  - **Both in-progress Grass decks are REGRESSIONS against the deck we already
    submit.** `No_Name_Grass` and `Claude_Grass_Venusaur` both lose heavily to
    Dipam's list, and Hydrapple beats `No_Name_Grass` 70/30. Structural reasons,
    measured:

    | metric | Dipam | No_Name_Grass | Claude_Grass_Venusaur |
    |---|---|---|---|
    | Pokémon / Supporters / Energy | 20 / 10 / 14 | 26 / **6** / **11** | 24 / 11 / 13 |
    | 4-of cards (consistency core) | **5** | 3 | **2** |
    | unique cards | 22 | 23 | **25** |
    | Prizes conceded across all Pokémon | **29** | **42** | 35 |
    | avg Prizes per Pokémon | **1.45** | **1.62** | 1.46 |

    `No_Name_Grass` runs three separate Mega ex lines (Kangaskhan / Meganium /
    Venusaur, 3 Prizes each) on only 6 Supporters and 11 Energy — worst prize
    liability in the field plus the thinnest draw engine. `Claude_Grass_Venusaur`
    has the most unique cards and the fewest 4-ofs, i.e. maximum dilution.
  - **Dipam runs ZERO Mega ex.** His most expensive body concedes 2 Prizes. This
    independently corroborates the 2026-08-09 Zygarde finding (10 of 14 Rule Box
    bodies lost despite dealing 4.4x more damage) and the refuted `_prize_value`
    patch: low Prize liability plus a fat 4-of consistency core beats raw damage.
  - Timing note: our only active submission is from **2026-08-08** and is now six
    days stale, with the Final Submission Deadline at 2026-08-16 23:59 UTC
    (2026-08-17 05:29 IST). Nothing has been promoted from the sub-agents platform.
  - His list is saved locally as `Decs/Dipam_Grass.csv` for testing and is
    **gitignored** (`Decs/Dipam_*`), same handling as `Decs/LiamK_*` — another
    team's list reconstructed from Competition Data should not be redistributed
  from this repo. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Plan 1 Phase 2 completed - leakage-safe observation records and bounded legal-action generation verified natively**:
  - Added immutable, typed records for public observations, state, players,
    Pokemon, cards, logs, selections, and every option field exposed by the
    competition API. Active/bench slot identity, live HP, attached Energy/cards,
    tools, evolution history, statuses, public zones, turn flags, and selection
    metadata are preserved. Opponent hidden hands remain `None` with only their
    count visible, and the converter deliberately never reads or serializes the
    opaque native `search_begin_input`; the final fixture leakage scan found zero
    matches.
  - Added a stable 1,270-token card vocabulary: PAD, UNKNOWN, INVALID, and all
    1,267 dataset card IDs. Added a versioned metadata catalog for all 1,267 cards
    and 1,556 attacks, including card type, HP, Energy type, evolution/Rule Box
    flags, weakness/resistance, skills, attack text, damage, and costs. Catalog
    construction rejects duplicate IDs and missing attack references, and its
    content hash is recorded in the Phase 2 report.
  - Implemented complete-action generation over the engine's variable
    `minCount`/`maxCount` contract. Small spaces are exhaustive; unordered
    selections use canonical combinations; `SKILL_ORDER` preserves permutations;
    large spaces use a deterministic preferred/prefix/sampled candidate set capped
    at 128. Every candidate has a selection-qualified fingerprint and exact option
    mask. Invalid bounds fail closed, duplicate/range/count violations are
    rejected, and appended future enum values are emitted safely but logged as
    unknown patterns instead of silently treated as known.
  - Added a complete-game fixture/legality suite across Hydrapple, No_Name Fire,
    No_Name Grass, and No_Name Dark. The final fresh-seed run completed **40/40
    games**, covered **3,928 live decisions** and **21 observed SelectType/context
    pairs**, generated **26,220 candidates**, and received **26,220/26,220 native
    `search_step` acceptances**. Setup decisions are now fork-validated too, so
    there are zero unvalidated candidates, timeouts, unknown patterns, or engine
    errors. Forty-six combinatorial decisions were bounded; the largest complete
    action space contained 1,035 actions.
  - Removed repeated per-candidate selection hashing after an initial latency
    review. Final generation p95 was 0.65-1.23 ms by deck and the worst observed
    call was 13.72 ms, below the declared 25 ms p95 and 100 ms maximum gates.
    Unit coverage increased from 20 to **35 passing tests**, source compilation and
    diff checking pass, and `Plan_1.md` now marks Phases 0-2 complete. The fixture,
    vocabulary, and card catalog contain competition-derived data, so they remain
    locally gitignored; their SHA-256 identities and aggregate evidence are stored
    in `plan_1/artifacts/reports/phase2-suite.json`. No active submission, deck, or
    Plan 2 specialist was changed.
    **Reason for the implementation:** give MCTS a stable, immutable,
    information-safe state/action boundary and prove that its bounded candidate
    generator produces only native-accepted complete actions before evaluator or
    tree-search logic is allowed to depend on it. -
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 Phase 1 completed - native search replay, release topology, chance, memory, and multi-deck gates passed**:
  - Extended the engine conformance layer with canonical public/search-state
    fingerprints, deterministic full-game searched paths, independent path replay,
    and explicit stochastic-boundary detection for shuffle, hidden draw, coin, and
    randomized deck-selection transitions. A real Hydrapple diagnostic found that
    independent search sessions can expose a differently ordered deck-selection
    list after randomness even when the action path is identical. The correct
    invariant is now enforced: exact state equality before the first stochastic
    boundary, followed by legal terminal completion for both independent paths.
  - Added release-topology coverage proving that a parent can create multiple
    children, a sibling survives unrelated leaf release, a child survives parent
    release, a grandchild survives ancestor release, released states are rejected,
    and double release is idempotent at the Plan 1 ownership layer. The pass
    criteria are centralized so single-process, multi-deck, and spawned-worker
    probes cannot apply contradictory gates.
  - Added an uncontrolled chance probe using an Applin deck. All 200 trials reached
    a coin event with `manual_coin=False`: 91 heads and 109 tails (45.5% heads), no
    missing outcomes, and no engine errors. This is a corruption/forced-outcome
    guard rather than a claim of precise statistical calibration.
  - Ran the full Phase 1 suite across Hydrapple, No_Name Fire, No_Name Grass, and
    No_Name Dark: **2,000 native begin/step/end sessions per deck, 8,000 total**.
    All four decks passed branch, release, cross-turn, stochastic-aware replay,
    terminal completion, error, latency, and post-warmup memory gates. Complete
    searched paths ranged from 106 to 230 decisions. Median begin times were
    0.284-0.577 ms and median step times were 0.173-0.432 ms; the largest measured
    post-midpoint working-set growth was 225,280 bytes, below the declared 8 MiB
    gate.
  - Re-ran process isolation under the same full criteria: two Windows spawned
    workers completed 500 sessions each, both independent replay paths terminated,
    exit codes were clean, and tail working-set growth was 94,208 and 81,920 bytes.
    Unit coverage increased from 12 to 20 passing tests, source compilation and
    diff checking remain clean, and `Plan_1.md` now marks Phases 0 and 1 complete.
    Phase 2 canonical observation/action implementation is next; no active
    submission, active deck, or Plan 2 specialist was changed.
    **Reason for the implementation:** close the simulator-contract risk before
    building MCTS by proving that complete searched games, branch ownership,
    release order, independent RNG streams, process isolation, and sustained
    native memory behavior are understood and enforced across multiple decks. -
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 implementation started - Phase 0 complete and Phase 1 native-search foundation verified**:
  - Added the isolated `plan_1/` package without touching the active submission or
    Plan 2 specialists. The foundation includes a standard-library-only Python
    package, strict baseline MCTS configuration and JSON schema, explicit empty
    dependency lock, `.venv-plan1` bootstrap, artifact boundaries, lazy bundled-
    engine loading, and commands for environment, baseline, conformance, and test
    verification.
  - Implemented hash-based reproducibility manifests with Git commit/dirty status,
    canonical configuration hash, runtime identity, deterministic derived seeds,
    atomic JSON writes, and SHA-256 identities for the current `main.py`, active
    `deck.csv`, engine API/game wrapper, and Hydrapple reference deck. The frozen
    Phase 0 evidence is stored in
    `plan_1/artifacts/manifests/phase0-baseline.json`.
  - Implemented an ownership-safe native `SearchSession` wrapper. It validates
    hidden-zone card IDs, rejects foreign/released search states, prevents session
    re-entry, makes close idempotent, attempts cleanup after failed `search_begin`,
    guarantees `search_end` after successful begin even on exceptions, and always
    calls the engine with `manual_coin=False` so favorable chance outcomes cannot
    be selected by the production search path.
  - Added real-engine conformance and spawned-process isolation probes. Hydrapple
    tests confirmed that one parent can create multiple children, children remain
    valid after parent release, released states are rejected, search crosses a turn
    boundary, and native root IDs are reused only across ended sessions. A 500-
    session sequential soak completed with no errors, median `search_begin` 0.171
    ms, median `search_step` 0.106 ms, and a 40,960-byte working-set delta. Two
    spawned workers then completed 200 sessions each with clean exit codes. Reports
    are in `plan_1/artifacts/reports/phase1-conformance.json` and
    `phase1-process-isolation.json`.
  - Verification passed in both the host Python and the isolated environment: 12
    unit tests, full source compilation, strict diff checking, engine import of
    1,267 cards and 1,556 attacks, and environment-report generation. `Plan_1.md`
    now marks Phase 0 active evidence complete while correctly leaving Phase 1 in
    progress; deeper path replay, broader release-order coverage, and longer memory
    soak remain before Phase 1 is declared complete.
    **Reason for the implementation:** establish a reproducible and failure-safe
    simulator foundation before implementing MCTS, because search strength is
    irrelevant if branch semantics, hidden-input contracts, cleanup, process
    isolation, or evidence identity are wrong. -
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan 1 fully specified for information-set MCTS plus policy-value reinforcement learning**:
  - Added `Plan_1.md` as the implementation specification for the combined MCTS/RL
    track. It defines success criteria, competition constraints, non-goals, system
    architecture, repository boundaries, reproducibility metadata, and the rule
    that the active submission remains untouched until a candidate passes every
    promotion gate.
  - Planned the simulator conformance layer before search implementation, including
    branch semantics, search-state lifecycle, process isolation, multi-select legal
    actions, chance handling, cross-turn search, leak tests, and unconditional
    cleanup. Hidden information is handled through public card accounting,
    root-sampled ISMCTS, information-set node keys, and explicit anti-leakage tests.
  - Specified the progression from a transparent handcrafted evaluator and UCT to
    opponent-response search, belief-aware ISMCTS, a variable-action policy-value
    model, PUCT, supervised bootstrap, and an AlphaZero-style self-play league.
    Trajectories, checkpoints, replay data, seeds, configurations, and model/deck
    identities are versioned and recoverable.
  - Defined frozen multi-deck evaluation, seat/first-player balancing, `n >= 500`
    confirmation, confidence intervals, appropriate statistical tests, causal
    ablations, tactical human review, held-out generalization, runtime/fault
    metrics, and strict champion/submission promotion gates.
  - Included CPU-first environment bootstrapping, Windows spawned-process workers,
    long-run recovery, storage/resource controls, Kaggle dependency and packaging
    probes, compact inference alternatives, deterministic heuristic fallback, a
    13-phase implementation sequence, immediate backlog, timeline, risk register,
    completion checklist, and Strategy-report/compliance requirements. This entry
    records planning only; no MCTS/RL code, active `main.py`, active deck, or Plan 2
    specialist state was changed.
    **Reason for the implementation:** turn the proposed RL/MCTS direction into a
    complete, ordered, testable engineering program that addresses imperfect
    information, variable actions, simulator safety, reproducibility,
    generalization, deployment constraints, and statistical promotion before
    expensive training begins. -
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-08-13

- **Four-deck specialist research launched concurrently with pinned models**:
  - Created new isolated specialists from the exact evaluated CSVs: `Fire` from
    `No_Name_Fire.csv`, `Grass` from `No_Name_Grass.csv`, and `Dark` from
    `No_Name_Dark.csv`. The older `Claude_Grass_Venusaur` specialist was not reused
    because its deck hash and list differ. Hydrapple remains the fourth specialist.
  - All three new 60-card lists passed static validation and runtime import against
    the competition engine. Unchanged baseline smoke readiness also completed with
    zero crashes: Fire 8-12, Grass 14-6, and Dark 11-9 over 20 games each. Those
    neutral experiments were explicitly rejected and archived as infrastructure
    checks rather than improvements.
  - After explicit human authorization to transmit each isolated `main.py`,
    `deck.csv`, and strategy context, queued and started four jobs simultaneously:
    Hydrapple `JOB-00003` and Fire `JOB-00004` use Codex **`gpt-5.5`**; Grass
    `JOB-00005` and Dark `JOB-00006` use Claude **`opus`**. Scheduler capacity
    confirms Codex 2/2, Claude 2/3, and global 4/5 active.
  - First-cycle mechanisms are deliberately separate and attributable: Hydrapple
    active-only attack-readiness attachment, Fire Charizard effect-driven damage
    evaluation, Grass Wild Growth Meganium engine priority, and Dark damaged-
    Sharpedo conditional attack value. Each job follows provider edit -> 20-game
    smoke -> 200-game screening -> rejection or human review. Automatic acceptance
    and submission promotion remain disabled.
  - Active experiments are Hydrapple `EXP-0008`, Fire `EXP-0002`, Grass `EXP-0002`,
    and Dark `EXP-0002`. All accepted specialist files and the active submission
    remain unchanged while candidates run in isolation.
    **Reason for the implementation:** begin parallel, deck-specific agent research
    on the four selected lists with explicit model accountability, isolated files,
    and measured gates instead of allowing untracked or cross-deck tuning. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Subagent execution paused and three user-built decks evaluated before selecting the next four specialists**:
  - Stopped the continuous scheduler at a safe review boundary. Hydrapple's live
    candidate had already been automatically rejected after its provider stage
    failed. The completed Venusaur screening experiment was explicitly rejected
    from adoption because specialist selection is being reset; all historical
    evidence remains archived. Scheduler status is stopped with both jobs closed,
    and no candidate was accepted or promoted.
  - Validated `No_Name_Dark.csv`, `No_Name_Fire.csv`, and `No_Name_Grass.csv` as
    legal 60-card decks with one ACE SPEC and no validation warnings. The Grass TXT
    says Bug Catching Set `[1094]`, but its executable CSV contains Buddy-Buddy
    Poffin `[1086]`; evaluation used the CSV.
  - Ran a four-deck, six-pairing matrix using the same current generic agent for
    every seat: **100 games per seat, 200 per pairing, 1,200 total games**, with
    zero draws, timeouts, crashes, or illegal actions. Aggregate ranking was:
    Hydrapple **480-120 (80.0%)**, Fire **257-343 (42.8%)**, Grass **248-352
    (41.3%)**, Dark **215-385 (35.8%)**. Hydrapple beat Dark 169-31, Fire 148-52,
    and Grass 163-37.
  - Candidate matchups formed a real cycle: Dark beat Fire **114-86** (`p=0.0477`),
    Grass beat Dark **130-70** (`p=0.000022`), and Fire beat Grass **119-81**
    (`p=0.00721`). Fire ranks first among candidates because it had the best field
    aggregate and strongest Hydrapple result, but it is not close to Hydrapple yet.
  - Tested whether the archived Venusaur attacker-concentration logic transfers to
    the exact user Grass list. It tied the generic agent **101-99 over 200 games
    (50.5%, p=0.888)**, so the previous 121-79 specialist gain was specific to its
    older deck and cannot be credited to `No_Name_Grass.csv`.
  - Added `No_Name_Decks/evaluation/REPORT.md` with full matchup evidence and
    card-level synergy review. Current recommendation: retain Hydrapple as the only
    confirmed specialist; place Fire first in the candidate queue; simplify and
    retest Grass; concentrate and retest Dark; leave remaining worker slots empty
    until decks earn them.
    **Reason for the implementation:** choose deck-agent research targets using
    legal lists, measured field performance, actual combo requirements, and agent
    transfer evidence before spending parallel coding-agent capacity. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Phase 8 scalable multi-provider worker pool implemented and first live jobs started**:
  - Expanded continuous research from two to **five concurrent deck specialists**.
    Enforced provider ceilings are **Codex 2**, **Claude 3**, and optional
    **Antigravity/Gemini 1**, all constrained by the five-process global limit.
    One active experiment per specialist remains mandatory.
  - Added provider-aware scheduling so a saturated provider no longer blocks jobs
    from another provider with free capacity. Scheduler status now reports global
    capacity, provider limits, and active counts by provider. New validated deck
    specialists can join the queue without scheduler code changes; empty capacity
    remains unused until a real deck and hypothesis are supplied.
  - Added verifier requirements for the five-worker pool and Codex/Claude quotas.
    Syntax and synthetic capacity tests passed, including two-Codex saturation,
    available Claude capacity, and the five-process global ceiling. Full audit
    `VERIFY-20260812-215132-253946` passed all Phases 1-7 with **0 errors across
    88 JSON files** before live launch; active submission hashes were unchanged.
  - The user explicitly authorized isolated source/context transmission to both
    configured providers. `JOB-00001` (Hydrapple active-only attack readiness)
    started under Codex, and `JOB-00002` (Venusaur attacker concentration) started
    under Claude. Scheduler status confirmed both in `running_screening`, occupying
    2/5 global slots. Their bounded provider, 20-game smoke, and 200-game screening
    results remain pending; no candidate has been accepted or promoted.
    **Reason for the implementation:** support parallel specialization across a
    growing deck library without allowing one provider or one deck to monopolize
    workers, while preserving independent evidence gates and human control. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Phase 7 decision-difference evidence implemented and verified**:
  - Added `decision_trace.py` and a bounded JSON trace schema. During real engine
    games, the candidate controls its seat while a separate frozen-baseline shadow
    evaluates each exact candidate-controlled observation. Only the candidate
    choice advances the game, so collection cannot turn a shadow choice into a
    misleading counterfactual outcome claim.
  - Each changed decision retains selection type/context, legal-option metadata,
    candidate and baseline selections, and a compact live-board summary. Policy
    limits the trace to 20 games, 200 changed decisions, and 40 options per record.
    The live opponent and shadow baseline use separate module instances so trace
    collection cannot corrupt opponent policy state.
  - Integrated error-free traces into both screening and confirmation human-review
    packs. Reviews now show the overall policy-difference rate, affected contexts,
    games containing differences, and representative choices beside benchmark and
    code-diff evidence. This identifies indirect behavior changes that a source diff
    alone can miss.
  - Verified the collector on rejected Hydrapple `EXP-0006`: **76 differences over
    1,296 candidate decisions (5.86%) in 18/20 games**, with 12 candidate wins, 8
    baseline-opponent wins, zero draws/timeouts, and zero trace errors. Human-readable
    records showed differences in `PLAY`, `ABILITY`, `ATTACH`, `RETREAT`, `EVOLVE`,
    and `ATTACK`; the wider MAIN effects are plausible because the narrow attachment
    change is also used inside the agent's search simulations.
  - Extended `verify_platform.py` with a Phase 7 audit for tool/schema/policy/review
    integration and schema validation of retained trace artifacts. The trace is
    behavioral attribution evidence only; it does not replace the 200/300/500-game
    statistical benchmark gates.
    **Reason for the implementation:** make human-in-the-loop review inspect what
    the candidate actually chooses differently on live board states, instead of
    relying only on aggregate wins and source-code intent. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **All implemented phases verified and Phase 6 controlled promotion completed as infrastructure**:
  - Added `verify_platform.py`, which performs one repeatable Phase 1-6 audit:
    parses every Plan_2 JSON artifact, validates experiment/job/matchup/tournament/
    promotion schemas, validates and runtime-imports every registered specialist,
    compares registry hashes, checks configured providers, enforces 20/200/300/500
    evidence policy, detects stale locks, maps tournament-history markers to result
    directories, verifies continuous-job authorization consistency, inspects
    promotion policy, and fingerprints the active submission. Verification
    `VERIFY-20260812-203435-964809` passed every phase with **0 errors** across
    **82 JSON files**; Codex, Claude, and Gemini CLIs were all available. Its only
    warning was correct: no statistically powered central tournament exists yet.
  - Added Phase 6 `promotion_config.json`, promotion schema, and
    `promote_candidate.py` with `request -> approve -> execute -> rollback` states.
    A request requires an accepted specialist backed by at least 500 confirmation
    games and two cross-deck opponents, exact specialist/registry/tournament hashes,
    a fault-free rank-one result, at least three entrants, and at least 300 games
    per seat. Approval requires named human acknowledgement and remains separate
    from execution.
  - Execution preserves the current submission pair in a uniquely identified
    snapshot, atomically replaces both `main.py` and `deck.csv`, validates the deck
    and Python interface, imports against the local `cg` engine, runs a complete-pair
    smoke and `benchmark.py` from the actual submission directory, and emits exact
    hashes/logs in a promotion manifest. Any validation, import, copy, or smoke
    failure automatically restores both old files. Explicit rollback restores and
    verifies both snapshot hashes. Every lifecycle event is append-only.
  - Isolated Phase 6 tests passed for successful atomic replacement, explicit
    rollback, and automatic rollback after a simulated missing-second-file partial-
    copy failure. The real request path was tested against Hydrapple and tournament
    `T-20260812-190829-346545`; it correctly refused **10 games per seat; requires
    300** before creating a request. No approval, execution, real submission write,
    or promotion occurred.
  - Active submission hashes remain
    `DBA17948B...AA3203` for `main.py` and `E1A9ABF1...AC41` for `deck.csv`, identical
    to accepted Hydrapple. The two continuous provider jobs remain blocked awaiting
    explicit source-egress authorization, so phase verification sent no new source
    to Codex or Claude.
    **Reason for the implementation:** make the final submission transition as
    evidence-gated, recoverable, auditable, and human-controlled as the specialist
    experimentation that precedes it, while providing a single command that can
    detect drift across every implemented phase. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Continuous sub-agent research pipeline implemented — 20/200/300/500 evidence gates, persistent queue, and two safe staged jobs**:
  - Added `continuous_scheduler.py`, `continuous_config.json`, and a continuous-job
    schema. The scheduler can remain resident, run up to two different specialists
    concurrently, enforce one experiment per specialist, cap new starts at six per
    day, retain fresh seeds and process logs, recover through persisted job states,
    stop gracefully, and append every transition to
    `sub-agents/continuous/REPORT.md`. Automatic acceptance and promotion remain
    disabled.
  - **Recommended Pipeline:** one narrow coding-agent hypothesis -> **20-game
    smoke** for import/legality/crash detection -> **200-game screening** for clear
    gains or regressions -> first human logic review -> **300-game main** evaluation
    -> fresh-seed **500-game confirmation** -> **200 cross-deck games per opponent**
    -> final human review -> private acceptance. Central tournament and controlled
    submission promotion remain separate operations.
  - **Evidence:** 20 games are infrastructure evidence only and have roughly a
    +/-22-point 95% margin near 50%; 200 games narrow that to roughly +/-7 points
    and are suitable for screening large effects; 500 games narrow it to roughly
    +/-4.4 points and are the minimum confirmation bar. Effects around 2-3 points
    require substantially more than 500 games. The central tournament remains 300
    games per seat (600 per pairing) for stronger pair comparison.
  - Added `advance_evidence.py` and strengthened acceptance. Screening survivors
    pause at review; approval runs main, confirmation, and available cross-deck
    matches, then creates a final review. `review_gate.py accept` now requires a
    confirmation result, two distinct completed cross-deck opponents, and explicit
    final human approval. With only two registered specialists, the system honestly
    records a 1/2-opponent limitation and cannot accept until a third specialist is
    available.
  - Staged two narrow jobs from measured evidence: Hydrapple's readiness bonus is
    restricted to the Active Pokemon, and Venusaur tests primary-attacker promotion
    after knockouts. Starting the daemon was blocked before launch because it would
    send isolated private `main.py`, `deck.csv`, and copied strategy/rules context
    to external Codex and Claude providers. Both jobs were changed to
    `awaiting_provider_authorization`; **no source was sent and no provider was
    called**. Explicit destination-aware source-egress approval is still required.
  - Python compilation, all JSON parsing, empty scheduler execution, CLI loading,
    mandatory authorization refusal, persisted queue state, and active-submission
    isolation passed.
    **Reason for the implementation:** allow long-running, statistically meaningful
    specialist improvement without converting continuous automation into unchecked
    self-modification, repeated false-positive tuning, or automatic submission
    changes. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Tournament reporting made progressive and Phase 6 boundary defined**:
  - Added `sub-agents/tournaments/REPORT.md` as the append-only cross-run ledger.
    Existing per-run `results/<tournament-id>/REPORT.md` files remain immutable
    detailed snapshots; future tournaments append one central entry identified by
    a unique HTML tournament marker and never overwrite earlier entries. A bounded
    exclusive report lock protects the duplicate-check and append operation when
    background tournaments finish concurrently.
  - Backfilled all three existing Phase 5 pilots chronologically. The ledger now
    maps Hydrapple's observed **70% -> 55% -> 65%** sequence and the inverse
    Venusaur sequence, while recording that both agent and deck hashes were
    unchanged. Those deltas therefore show sampling variation, not implementation
    improvement.
  - New tournament summaries calculate progress against the latest same-field run:
    prior/current version, agent/deck hash changes, rank delta, field-win-rate
    delta, and worst-matchup delta. Comparisons are labeled direct only when both
    the entrant field and games per seat match; the seed is now retained in new
    summaries as additional reproducibility context.
  - Historical backfill is idempotent: running it twice left the central report at
    the identical SHA-256
    `ADC425B1E439706B2D0C8E7AF75E7AAC4B60DCEB884C3A0AE3E035A944BF6ED9`,
    proving that already-recorded tournaments were neither duplicated nor rewritten.
  - Defined **Phase 6** as controlled submission promotion: human approval,
    recoverable submission snapshot, exact tournament-artifact verification,
    atomic pair copy, validation/smoke from the submission directory, promotion
    manifest, and tested rollback. It remains deliberately unstarted because the
    current 20-game pilot is infrastructure evidence rather than a credible winner.
    **Reason for the implementation:** preserve the full experimental timeline and
    distinguish genuine agent/deck progress from run-to-run variance before any
    tournament result can influence the final submission. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan_2 phase 5 complete — central tournament now ranks whole private deck-agent pairs; two-specialist pilot remained inconclusive**:
  - Added `matchup_pair.py`, which loads two independent private `main.py` modules,
    binds each to its own 60-card `deck.csv`, swaps the complete deck-agent pair
    between seats, and alternates first player game by game. Outcomes retain
    orientation counts, Wilson interval/null-test statistics, per-agent timing,
    timeouts, agent crashes, illegal actions, and engine failures instead of
    collapsing all non-wins into one bucket.
  - Added `run_tournament.py`, central configuration, matchup/tournament schemas,
    immutable entrant hashes, subprocess and log isolation per pairing, aggregate
    robustness ranking, matchup matrix, and a Markdown report under
    `sub-agents/tournaments/results/`. Tournament entry rejects active experiments
    and any specialist not in `READY_FOR_EXPERIMENT`.
  - Ranking is fault-free operation first, then field win rate, worst matchup, and
    mean decision time. The reported winner is only a **provisional champion**;
    configuration and every result fix `auto_promote=false`, and the tournament
    runner contains no submission-copy path.
  - Closed a lifecycle-state gap found during the pilot: a successful smoke stage
    now records static, runtime-import, and smoke validation in `status.json`.
    Created the isolated `Claude_Grass_Venusaur` specialist from the existing legal
    deck and shared baseline. Its unchanged `EXP-0001` smoke finished **13-7 over
    20**, with no failures, then was explicitly rejected because it contained no
    strategic change. No Claude coding-provider call occurred.
  - Final infrastructure pilot `T-20260812-190829-346545`: Hydrapple **13-7** over
    Claude Grass Venusaur, exactly 10 games in each seat orientation, zero draws,
    timeouts, illegal actions, agent crashes, or engine crashes. Hydrapple's 65%
    had **95% CI 43.3-81.9%, z=1.34, p=0.180**. This is not statistically persuasive;
    it validates pair swapping and reporting only and does not support promotion.
  - Python compilation, both generated JSON schemas, outcome/seat accounting,
    specialist readiness, and active-submission integrity passed. The active
    `main.py` and `deck.csv` hashes still match the accepted Hydrapple specialist.
    **Reason for the implementation:** replace incomparable specialist self-reports
    with one central, seat-balanced measurement of complete deck-agent pairs while
    preserving human authority over any final submission decision. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan_2 phase 4 live verification complete — authorized Codex candidate reached screening and was correctly auto-rejected at 40%**:
  - The user explicitly authorized transmitting the isolated Hydrapple candidate and
    copied Plan_2 context to Codex CLI. The first authorized run (`EXP-0004`) reached
    Codex but produced no edit because the nested Windows sandbox could not spawn even
    `pwd` (`CreateProcessAsUserW failed: 5`). The controller rejected it before any game,
    and accepted/submission files remained untouched.
  - Corrected the Codex adapter to use its managed `--approve-for-me` execution policy.
    This Codex version forbids combining that flag with an explicit `--sandbox`; the
    corrected invocation reports `approval: on-request` and `sandbox: workspace-write`.
    The disposable workspace, 15-minute outer timeout, complete workspace fingerprint,
    and `main.py`-only import gate remain in force. A fresh harmless comment probe
    (`EXP-0005`) proved Codex could read context and edit only `main.py`; it was then
    explicitly rejected without benchmarking.
  - Ran the real `attack_readiness_attachment` hypothesis as `EXP-0006`. Codex added
    Energy-type inference, an attack-cost transition check, and a 100,000-point bonus
    when one attachment changed a target from unable to able to attack. The provider
    exited cleanly, modified only `main.py`, passed syntax/deck/interface validation,
    and was atomically imported into the private candidate.
  - Engine evidence: smoke **9/20 (45%)**, then screening **40/100 (40.0%, 95% CI
    30.9-49.8%, z=-2.00, p=0.0455)**; average 127.86 steps and 4.90 ms candidate
    decision time; zero draws, timeouts, illegal actions, or crashes. The Phase 4 policy
    automatically rejected it below the 45% floor, before human review or any acceptance.
  - Code-quality postmortem: Energy metadata inference matched the real API, so this was
    not a silent metadata failure. The strategic interpretation was wrong: the enormous
    readiness bonus applied to **Benched** Pokemon even though they normally cannot attack
    that turn, overpowering the established Active preference. This recreates the already
    observed harmful bench-first Energy routing rather than narrowly preventing wasted
    Active attachments. No retry or constant tuning was performed after the measured loss.
  - Hydrapple remains `v000-baseline`; active submission `main.py` and `deck.csv` remain
    unchanged. This completes Phase 4's real verification: external provider invocation,
    isolated edit, validation, smoke, screening, statistical gate, and automatic rejection
    all operated end to end.
    **Reason for the implementation:** verify that Plan_2 can safely turn a real coding-
    agent hypothesis into measured evidence and reject a plausible but harmful strategy
    without relying on the provider's self-assessment or risking accepted files. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-08-12

- **Plan_2 phase 4 locally complete — bounded worker cycle and human review gate proven; live provider awaits explicit source-transmission approval**:
  - Added `orchestration_config.json`, `orchestrate.py`, and `review_gate.py`. A cycle is
    now a finite, persisted `start -> provider -> smoke -> screening -> REVIEW_REQUIRED`
    state machine protected by an atomic per-specialist lock. Interrupted experiments can
    be resumed from their recorded provider/stage results instead of restarting or
    silently duplicating work.
  - The orchestrator delegates to the Phase 2/3 CLIs, preserving their isolation,
    validation, game caps, and audit logs. Provider failure, outer timeout, engine-stage
    failure, any crash/illegal action/engine timeout, screening below 45%, or a significant
    screening loss triggers an explicit rejection through the normal experiment decision
    path. Configuration explicitly sets `auto_accept=false` and `auto_promote=false`.
  - Added generated human-review packs under `sub-agents/human-review/pending/`: exact
    hypothesis/mechanism, provider record, benchmark statistics, Wilson interval/null-test,
    failure and decision-time counts, bounded unified diff, and mechanism-aware review
    questions. `review_gate.py approve` authorizes only the later main benchmark; it does
    not accept the candidate. Rejection moves Markdown/JSON evidence to `rejected/` and
    closes the experiment through the existing archive path.
  - Verified the full local success path as Hydrapple `EXP-0003` using an explicitly
    labeled no-op fixture (one comment, no behavior change): smoke **9/20**, screening
    **54/100 [44.3-63.4%], z=0.80, p=0.424**, average 124.49 steps, zero draws/timeouts/
    illegal actions/crashes. The result correctly reached human review rather than being
    treated as a gain. The review wording initially exposed an Energy-specific assumption
    for a generic fixture; generation was corrected to generic checks plus optional
    mechanism-specific questions. Human rejection archived both review artifacts, and
    Hydrapple remained `v000-baseline` with the accepted hash unchanged.
  - A real Codex-provider pilot for the narrow `attack_readiness_attachment` hypothesis
    was attempted, but execution was blocked **before experiment creation** because it
    would transmit the isolated private `main.py` and copied project context to an
    external coding provider without explicit source-egress approval. No source was sent,
    no model was called, and no workaround was used. The code path remains ready once the
    user explicitly authorizes that transmission.
  - Python compilation, JSON parsing/schema compatibility, real 120-game stage ordering,
    review generation/archive, and active-submission integrity checks passed.
    **Reason for the implementation:** convert the separate provider and benchmark tools
    into one finite, recoverable human-in-the-loop workflow that can reject failures
    automatically but can never accept or promote an unreviewed strategy. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan_2 phase 3 implemented — Codex, Claude Code, and Antigravity/Gemini now share one isolated worker contract**:
  - Added `provider_config.json`, `provider_adapters.py`, and `run_worker.py`. Provider
    discovery confirmed Codex CLI `0.147.0-alpha.6.5`, Claude Code `2.1.218`, and Gemini
    CLI `0.47.0-nightly.20260604.g4196596f7` are callable. The configured `antigravity`
    slot resolves to Gemini CLI because the installed Antigravity desktop directory has
    no headless PATH executable; audit records name the actual `gemini-cli` backend so
    this is not represented as direct desktop automation.
  - Every invocation receives a disposable experiment workspace with copies of the
    candidate `main.py`/`deck.csv`, frozen baseline, experiment definition, specialist
    configuration/status/progress, shared contract, and Pokemon rules. The generated
    prompt permits only the smallest hypothesis-specific edit to root `main.py`; workers
    do not benchmark, accept, promote, or touch the staged candidate directly.
  - Provider commands are constrained according to available CLI controls: Codex uses
    an ephemeral workspace-write sandbox, Claude Code uses safe mode plus Read/Edit/Write
    tools only, and Gemini uses sandbox + auto-edit mode. The controller adds an outer
    timeout and separate actual-run/dry-run budgets, records prompt/command/backend/model,
    captures stdout/stderr, and fingerprints the complete disposable workspace.
  - Import is fail-closed: process failure, timeout, unchanged `main.py`, any changed
    protected/context/deck file, invalid deck, or invalid Python interface rejects the
    output. Only a valid root `main.py` is atomically copied into the already-isolated
    experiment candidate; accepted specialist and submission files remain outside this
    operation.
  - Exercised Hydrapple `EXP-0002` as a **dry-run-only** adapter test. Codex, Claude, and
    Antigravity/Gemini each resolved a concrete command and received equivalent private
    workspaces; all worker and candidate `main.py` hashes matched the accepted baseline.
    No model was invoked, no provider cost was incurred, and the experiment was explicitly
    rejected because it contained no gameplay change. Hydrapple remains `v000-baseline`.
  - Python compilation and JSON parsing passed. A real provider-generated edit remains
    intentionally unverified until a gameplay hypothesis is selected; it must then pass
    Phase 2 validation and benchmarks. Cross-deck evaluation, review-pack generation,
    central tournament ranking, and submission promotion remain future phases.
    **Reason for the implementation:** connect all available coding agents to the same
    bounded evidence pipeline without granting any one CLI direct authority over accepted
    specialists or submission files, while keeping the true backend and every attempted
    change auditable. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan_2 phase 2 complete — bounded private experiments now run through the local engine**:
  - Added `run_experiment.py` with an explicit `start -> run -> decide` lifecycle.
    Starting creates an immutable snapshot of the accepted private deck-agent pair and
    a separate candidate copy; only the candidate may be edited. A specialist can have
    only one active experiment, and the tested concurrency guard refused a second start
    with exit 2 while preserving the first experiment.
  - Added `benchmark_pair.py`, which loads candidate and baseline modules independently,
    binds the specialist deck to each seat, alternates the candidate's seat, and runs the
    ignored local `cg` engine in a child process. The controller enforces configured game
    caps, step caps, and wall-clock timeout, while preserving stdout/stderr logs and JSON
    results. It records wins/losses, draws, engine timeouts, candidate illegal actions,
    candidate crashes, steps, mean/max decision time, Wilson interval, and a two-sided
    head-to-head 50% null-test approximation.
  - Enforced ordered `smoke -> screening -> main -> confirmation` stages. Private
    acceptance requires a successful main-stage result and no recorded failed/timed-out
    run; promotion remains a separate future gate. Candidate-versus-baseline changed-file
    detection is recorded at run time.
  - Added explicit accept/reject handling. Rejection archives the complete evidence and
    leaves accepted files untouched. Acceptance creates a recoverable accepted snapshot,
    uses atomic per-file replacement, restores the prior baseline if replacement fails,
    and updates specialist status plus the central registry. No submission file is ever
    addressed by this workflow.
  - Exercised the full safe path as Hydrapple `EXP-0001` with an intentionally unchanged
    candidate: runtime import passed; a two-game seat-balanced smoke run finished **1-1**,
    average 115 steps, zero draws/timeouts/illegal actions/crashes, and 4.86 ms mean
    candidate decision time. The experiment was deliberately **rejected** because it
    contained no strategic change. The accepted Hydrapple and active submission hashes
    remained identical afterward. This tiny run validates infrastructure only and makes
    no gameplay-strength claim.
  - `py_compile`, all Plan_2 JSON parsing, generated experiment/result JSON Schema
    validation, overwrite/concurrency guards, runtime import, and submission-integrity
    checks passed. Updated `Plan_2.md` and `sub-agents/README.md` with the implemented
    lifecycle and the remaining boundary: provider adapters, autonomous workers,
    cross-deck review, tournament ranking, and promotion are not implemented yet.
    **Reason for the implementation:** give future Codex, Claude Code, and Antigravity
    workers one bounded and reproducible experiment controller before allowing them to
    edit deck-specific agents in the background; this converts hypotheses into isolated,
    reviewable evidence without risking accepted or submission files. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Plan_2 implementation started — isolated deck-specialist foundation and Hydrapple pilot created**:
  - Added `Plan_2.md` with the agreed full architecture: development-agent contract,
    specialist lifecycle, common measurement policy, human review gates, central
    tournament, controlled promotion, coding-agent roles, and staged implementation
    order. The first milestone is explicitly limited to safe specialist scaffolding;
    autonomous workers and submission promotion are not enabled yet.
  - Added `sub-agents/` with an enforceable shared `AGENT_CONTRACT.md`, provider-neutral
    specialist/reviewer prompts, benchmark policy, experiment/result JSON schemas,
    central registry, disabled-by-default tournament configuration, review directories,
    and an immutable private copy of the current `main.py` baseline. Specialists are
    forbidden from writing to the active submission or another specialist.
  - Added `create_specialist.py` and `validate_agent.py`. Creation validates exactly 60
    integer Card IDs, dataset membership, at least one Basic Pokemon, the four-copy
    limit aggregated by card name, and the one-ACE-SPEC limit; it then creates the
    private deck/agent pair, configuration, status, experiment directories, progress
    log, hashes, and registry entry. Existing specialist names are refused rather than
    overwritten. Agent validation parses Python syntax and verifies the required
    top-level `agent()` and `read_deck_csv()` interfaces; optional runtime import is a
    separate check so missing engine dependencies cannot be mistaken for a code error.
  - Created the first pilot at `sub-agents/specialists/Hydrapple/` through the same CLI
    intended for future decks. Static validation passed: 60 cards, 26 unique Card IDs,
    13 Basic Pokemon, one ACE SPEC, valid Python syntax, and both required interfaces.
    Repeating creation returned exit 2 and left `registry.json` byte-for-byte unchanged,
    confirming the overwrite guard. JSON parsing and `py_compile` checks also passed.
  - Runtime import/gameplay smoke testing remains pending because the Python available
    in this shell does not expose the competition `cg` package (`ModuleNotFoundError`).
    No active submission file was changed and no benchmark claim is made in this entry.
    **Reason for the implementation:** establish a reproducible isolation and validation
    boundary before Codex, Claude Code, or Antigravity are allowed to perform background
    deck-specific experiments; this prevents parallel edits, inconsistent evidence, and
    accidental submission replacement at the foundation of Plan_2. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Codex_MegaCharizard_FireTurbo evaluated — weakest deck measured so far; cause is
  attacker discipline, and my ability-cap hypothesis was falsified**:
  - Legality verified by Card ID before running: 60 lines, all IDs exist, >=1 Basic,
    ACE SPEC exactly 1 (Precious Trolley), and the per-**name** cap holds -- Charmander
    appears as two printings (788 x2 + 926 x2 = 4 total, exactly at the cap), Charmeleon
    as two (789 + 927 = 2). Legal.
  - **Results (n=200 each, 0 timeouts):** `vs random` **77.5% [71.2-82.7]**,
    `vs Hydrapple` seat-balanced **20.5% [15.5-26.6]**, `vs Claude_Grass_Venusaur`
    seat-balanced **33.5% [27.3-40.3]**. All three are decisive losses; the deck ranks
    **below both Hydrapple and the Venusaur build**, which itself already failed the
    submission bar.
  - **The vs-random number is the real diagnostic.** 77.5% against an opponent playing at
    random, where Hydrapple scores 96-97% and Venusaur 99.0% on the identical harness.
    A deck that cannot cleanly beat random play is failing structurally, not merely
    being outclassed.
  - **Instrumented 40-game mirror shows why: attacker discipline collapses.** Attacks by
    Active: Mega Audino ex 25.1%, Oricorio ex 24.1%, **Charmander 16.6%**, Fezandipiti ex
    8.6%, Charmeleon 4.3% -- i.e. **~78% of all attacks come from support/basic Pokemon
    and only 22.5% from the actual Mega Charizard X/Y ex**, the entire point of the deck.
    Total volume is also low at **4.7 attacks/game**, with 21.4% of MAIN decisions being
    END. Compounding it, **Mega Evolution ends your turn** (POKEMON_RULES.md line 241),
    so landing a Charizard costs a full tempo cycle the greedy ladder does not model.
  - **Hypothesis raised and then falsified, recorded as such.** I flagged before running
    that `ABILITY_CAP_PER_TURN = 4` (added 2026-08-11) might be throttling Oricorio ex's
    `Excited Turbo`, an "as often as you like" ability, and said the cap was the prime
    suspect if the deck underperformed. Tested it directly with a cap sweep (n=150/arm):

    | cap | vs random | vs Hydrapple |
    |---|---|---|
    | **4 (shipped)** | 74.0% [66.4-80.4] | **27.3% [20.8-35.0]** |
    | 12 | 76.0% [68.6-82.1] | 22.0% [16.1-29.3] |
    | 40 | 70.0% [62.2-76.8] | 17.3% [12.1-24.2] |

    Raising the cap makes the deck **monotonically worse**, not better: cap=4 vs cap=40
    against Hydrapple is z=-2.08, **p=0.038** -- significant, and in the *opposite*
    direction from my prediction. The shipped cap=4 is the best of the three. The
    hypothesis was wrong with the sign reversed, which is worth stating plainly rather
    than quietly dropping. Plausible reading: extra Ability activations spend MAIN
    decisions shuffling Energy instead of attacking, on a deck already starved at 4.7
    attacks/game.
  - **Conclusion: not a submission candidate**, and the gap is not fixable by deck
    tweaks alone. This is the clearest instance yet of the "needs piloting" category
    from the 2026-08-10 card review -- the deck requires Charmander -> Rare Candy ->
    Mega sequencing plus Oricorio bench-fueling for `Inferno X`, and the current greedy
    + 1-ply agent executes none of it. `deck potential x agent execution` with execution
    near zero. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Deck Library now supports safe single- and multi-deck deletion**:
  - `deck_builder/index.html`, `app.js`, and `styles.css` — added an explicit deck-selection
    mode to the saved Deck Library with Select decks, Select all, Cancel, and Delete
    selected actions. Selected folders receive a clear checkbox-style marker and count,
    and the controls remain usable in the phone layout.
  - Bulk deletion requires confirmation, removes only the selected saved-library records
    from local storage, and deliberately leaves the deck currently loaded in the builder
    unchanged. Existing deletion from inside a single saved deck continues to work.
    **Reason for the implementation:** imported deck experiments can accumulate quickly,
    so the library needs a deliberate way to remove one or several obsolete lists without
    clearing the active build or deleting folders one at a time. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Claude_Grass_Venusaur clean evaluation (post ability-cap fix) — real result: loses
  decisively to Hydrapple, not a submission candidate as built**:
  - Every earlier number for this deck was contaminated by the ability-loop hang (logged
    on 2026-08-11); this is the first clean measurement now that `main.py` no longer
    stalls. `vs random n=200`: **99.0% [96.4-99.7]**, 0 timeouts, avg 117.7 steps --
    comparable to Hydrapple's own 96-97% vs random, confirming the deck itself is
    legitimate, not broken. `vs Hydrapple, seat-balanced n=200`: **35.5% [29.2-42.3]**,
    0 timeouts, avg 127.3 steps -- CI upper bound sits clearly below 50%, a real,
    significant loss, not noise.
  - Per the standing working principle ("don't replace Hydrapple unless new deck + adapted
    main.py clearly beats Hydrapple + current main.py"), this deck fails that bar outright
    and is **not a submission candidate as constructed**. Kept in `Claude_Decks/` as a
    recorded result, not reworked in this entry.
  - Suspected cause, not yet isolated: 23 Trainers vs Hydrapple's 26, and three competing
    Stage-2 Grass lines (Meganium / Hydrapple ex / Mega Venusaur ex) sharing the same 13
    Energy and drawing against each other for consistency, rather than the two-line
    Hydrapple core stacking cleanly. Not measured in isolation -- a real diagnosis would
    need an ablation (drop the Venusaur line, re-test at the original 26-Trainer count)
    before asserting which factor actually costs the win rate. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Discussion with Codex: RL/MCTS direction, 3-day feasibility, and Strategy focus**:
  - Clarified that a full, leaderboard-reliable RL system is unlikely to be built
    and trusted in a single 24-hour push. A 24-hour run can realistically produce a
    prototype: simulator wrapper, state/action encoding, rollout loop, basic
    training logs, and maybe an exportable policy. It should be treated as an
    experiment, not as a guaranteed stronger submission.
  - Reframed the user's follow-up plan: working 24 hours nonstop for 3 days could
    create meaningful progress on an RL pipeline, especially if the goal is to learn
    whether RL has promise in this simulator. The likely deliverable is a working
    RL-assisted or MCTS-assisted prototype, not a robust pure-RL agent that can be
    trusted without strong benchmark proof.
  - Recommended priority split: keep the current heuristic/search `main.py` and deck
    work as the dependable Simulation submission path, while using the 3-day push as
    a side experiment. If the RL/MCTS prototype clearly beats the current
    `main.py + deck.csv` in controlled tests, it can be considered for Simulation;
    otherwise it should remain research for the Strategy Hackathon.
  - For the Strategy Hackathon, the longer 2-3 week window makes the idea more
    reasonable. The strongest path is not pure RL from scratch, but a hybrid:
    retain the existing legal-action and heuristic structure, then add learned
    scoring, bounded MCTS, rollout evaluation, or deck-specific policy improvements
    around the decisions that matter most.
  - Practical 3-day outline recorded for future execution: Day 1 should build the
    environment wrapper, state representation, legal-action mapping, random/self-play
    rollout loop, and reward logging. Day 2 should train the first policy/value or
    imitation model using current-agent games plus reward shaping for prizes, KOs,
    board setup, attacking, Energy attachment, and avoiding dead turns. Day 3 should
    benchmark against the current agent, run enough games to avoid noise, and export
    only if the result is clearly stronger.
  - Decision rule carried forward: do not replace the current submission with an
    RL/MCTS variant merely because it exists. Replace only if it wins by a meaningful
    margin against the current agent under the same harness, same deck constraints,
    and enough games to make the result credible. **Reason for the entry:** the user
    is deciding whether to aim beyond the current heuristic agent for the Strategy
    track, so the project log needs the practical RL/MCTS tradeoff, timeline, and
    go/no-go rule captured before work branches in that direction. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Mobile card-catalog scrolling restored after the responsive sidebar pass**:
  - `deck_builder/styles.css` — removed the desktop grid-height and overflow clipping
    from the catalog panel at phone widths, allowing the card grid to grow with its
    contents and use normal page scrolling. **Reason for the implementation:** the
    preceding mobile redesign made the card grid itself scroll-compatible but left
    its parent constrained to the desktop catalog layout, so cards beyond the first
    viewport were clipped on phones. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Deck builder rebuilt around a catalog-first phone workflow with cascading sidebars**:
  - `deck_builder/index.html`, `app.js`, and `styles.css` — converted the existing
    stacked phone layout into two touch-friendly off-canvas panels: filters cascade
    in from the left and the live deck cascades in from the right, while the card
    catalog remains the primary phone view. A fixed bottom navigation bar exposes
    Cards, Filters, and the current deck count at all times.
  - Added synchronized mobile filter/deck counters, explicit drawer close controls,
    backdrop and Escape dismissal, responsive deck-name handling, and automatic
    drawer cleanup when returning to desktop width. Existing filtering, validation,
    add/remove, saved-deck, flag, import, and export behavior continues to use the
    original panels rather than duplicated mobile-only state.
  - Reworked phone spacing and sizing across the header, horizontal catalog tabs,
    two-column card grid, card steppers, saved-deck folders, deck rows, focused-card
    controls, and import dialogs. **Reason for the implementation:** the previous
    mobile breakpoint placed every major panel in one long page, making it difficult
    to browse cards while checking the current deck; the cascading layout keeps those
    tasks one tap apart without obscuring the catalog permanently. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-08-11

- **Ability-cap fix confirmed clean on the shipped Hydrapple baseline (follow-up to
  the entry below)**:
  - `self_play_benchmark.py 500` (main.py with the fix, vs frozen `previous_agent`,
    Hydrapple mirror): **48.6% [95% CI 44.2-53.0%]** (243/257/0), avg 126.4 steps. CI
    spans 50% -- a tie, and average steps sits in the same ~121-131 band logged since
    the 08-08 freeze. Exactly the expected result: Hydrapple's own Abilities (Teal
    Dance, Ripening Charge) are already "once during your turn" -- bounded -- so the
    cap never engages on them and should be a no-op, which this confirms.
  - The fix is now validated on both ends: `check_ability_cap.py` shows it eliminates
    the hang on the deck that exposed the bug, and this run shows it does not change
    behavior on the deck that must not regress. Committed and pushed as `569ca1d`
    together with the fix itself. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **First `Claude_Decks/` build exposed a genuine infinite-loop bug in `main.py`'s
  MAIN ladder; root-caused and fixed at the actual decision point**:
  - `Claude_Decks/Claude_Grass_Venusaur.txt` / `.csv` — first deck built from the
    user's flagged-card research: extends the proven Hydrapple core (Teal Mask
    Ogerpon ex / Meganium / Hydrapple ex) with a second Stage-2 Grass attacker line,
    Bulbasaur -> Ivysaur -> **Mega Venusaur ex** (380 HP, `Solar Transfer` ability
    moves a Basic {G} Energy between own Pokemon "as often as you like"). 24 Pokemon /
    23 Trainers / 13 Energy, legal by direct Card-ID check against the dataset (all 60
    IDs exist, no name over 4 copies outside Energy, >=1 Basic present) and confirmed
    playable end-to-end through the real engine.
  - **First measurement was alarming: 80% vs random (Hydrapple's own baseline is
    96-97%) and 23.5% [18.2-29.8] head-to-head vs Hydrapple, n=200 seat-balanced.**
    Investigated rather than accepted at face value, per house discipline. A 20-game
    instrumented mirror run showed **avg 831-963 steps** (Hydrapple's proven average is
    ~121-131) with **7 of 20 games (35%) hitting the 3000-step harness cap and never
    finishing**, scored as non-wins. Not a weak deck -- a hang.
  - **Root cause, confirmed by direct trace of the actual option sequence:** the agent
    cycles `ENERGY -> CARD -> ABILITY -> ENERGY -> CARD -> ABILITY ...` on one turn for
    1500+ consecutive steps. Mega Venusaur ex's `Solar Transfer` is legal forever (moves
    Energy between your own in-play Pokemon at zero net cost, so nothing runs out), and
    `_eval_state`'s Active-quality term (`energies * 5`, shipped 2026-08-04) rewards
    hoarding Energy with **no penalty for never attacking**. Once an unlimited
    energy-move source exists, `_search_choose_main` finds "use Ability again" scores
    higher than "attack" on literally every turn and re-picks it forever. This pathway
    was invisible until now because Hydrapple's own abilities (Teal Dance, Ripening
    Charge) are all "once during your turn" -- bounded.
  - **First fix attempt was wrong and is recorded as such.** Capped Ability re-selection
    inside `_choose_main`'s greedy ladder (`_take_ability`, a per-(turn,seat) counter).
    Re-ran the same trace: **identical infinite loop, unchanged.** Cause: when
    `SEARCH_MAIN` is on, the top-level MAIN decision is chosen by `_search_choose_main`,
    which evaluates every `sel.option` candidate directly and **never calls
    `_choose_main`'s ladder for the live pick** -- that function is only used for the
    ROLLOUT TAIL inside each candidate's preview. The cap gated a code path the bug
    didn't go through.
  - **Working fix gates the actual decision point.** Replaced the ladder-only cap with
    `_ability_cap_reached()` (read-only, checked by both `_choose_main`'s ladder AND
    `_search_choose_main`'s candidate loop, which now skips ABILITY-type options once
    the cap is hit) and `_record_ability_use()` / `_record_if_ability()` (the only
    writer, called once in `_agent_impl` on the action actually returned to the engine
    -- never from inside a rollout, so hypothetical search deliberation can't burn the
    real turn's budget before the live game acts). `ABILITY_CAP_PER_TURN = 4`: high
    enough that legitimate multi-use turns (consolidating Energy from several sources
    before attacking) aren't restricted, low enough to guarantee the MAIN phase always
    terminates.
  - `sample_submission/sample_submission/check_ability_cap.py` — new persistent
    regression check (ponytail: one runnable check for non-trivial logic). Plays N
    games with the Grass/Venusaur deck and asserts none hit the step cap.
    **Before the working fix: 6/30 games at ~2998-2999 steps (right at the cap).
    After: 0/30, all finishing in a normal 30-239 step range.**
  - **Verification status, stated plainly rather than assumed:** the no-regression
    check on the shipped Hydrapple baseline (`self_play_benchmark.py 500` vs frozen
    `previous_agent`) and a clean re-measure of the new deck vs random were both
    **launched but not yet returned** when this entry was written (the shell session
    restarted mid-run and orphaned the first attempt). Do not read this fix as fully
    validated on the shipped deck until a follow-up entry confirms the ~71.6% Hydrapple
    baseline is unchanged. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Deck builder full-TXT import and persistent saved-deck folders added**:
  - `deck_builder/index.html`, `app.js`, and `styles.css` — expanded deck import
    from pasted card IDs into a multi-file TXT workflow that accepts the grouped
    `count card name - card ID` format used by `Codex_MegaCharizard_FireTurbo.txt`,
    `Codex_FireCamerupt.txt`, and `Hydrapple.txt`. **Reason for the
    implementation:** imported deck lists needed to remain available for visual
    comparison instead of only replacing the single editable deck and then being
    forgotten.
  - Added a persistent **Saved Decks** catalog section. Each imported file becomes
    a separate folder named from its filename; opening a folder shows its unique
    cards with local card artwork and imported copy counts in the same visual form
    as the Card Catalog. Saved folders can be loaded explicitly into the editable
    builder or deleted, and re-importing the same deck name updates that folder.
  - Multiple TXT files can be selected in one import. Pasted deck lists remain
    supported with an explicit deck name, unknown IDs are reported and skipped,
    and saved folders persist in browser storage alongside the working deck and
    flags.
  - Verification passed against all three requested examples: Mega Charizard Fire
    Turbo imported as 60 cards / 21 unique / 0 unknown IDs, Fire Camerupt as 60 /
    18 / 0, and Hydrapple as 60 / 26 / 0. JavaScript syntax and diff checks also
    passed. No submission `main.py` or active `deck.csv` was changed. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Codex Mega Charizard Fire Turbo candidate built from updated flagged pool**:
  - `Codex_Decks/Codex_MegaCharizard_FireTurbo.txt` and `.csv` — added a separate
    60-card candidate deck, leaving active submission files unchanged. **Reason for
    the implementation:** the updated `My_Deck_flags.txt` added enough Fire Mega
    pieces to form a coherent Pokemon shell and support shell around Mega
    Charizard X ex, Mega Charizard Y ex, Oricorio ex, and Firebreather without
    mixing unrelated flagged engines.
  - The deck uses a compact 17-Pokemon shell: 4 Charmander split across two legal
    printings, 2 Charmeleon, 3 Mega Charizard X ex as the primary scalable finisher,
    2 Mega Charizard Y ex as a high-impact secondary snipe attacker, 3 Oricorio ex
    for Fire Energy acceleration once a Fire Mega is in play, plus Fezandipiti ex,
    Latias ex, and Mega Audino ex as utility/support basics.
  - Trainer shell follows the World Champion deck lesson of high consistency:
    4 Firebreather, 4 Hilda, 4 Ultra Ball, 4 Rare Candy, 3 Mega Signal, 3 Pokegear
    3.0, 2 Boss's Orders, 2 Air Balloon, 2 Night Stretcher, and 1 Precious Trolley
    ACE SPEC. Energy shell is 14 Basic {R} Energy so Firebreather and Oricorio ex
    have enough targets and Charizard X has fuel across the board.
  - Validation passed locally: 60 total cards, exactly 1 ACE SPEC, and no
    non-Basic card name above four copies. This deck is exploratory only and was
    not copied into `sample_submission/sample_submission/deck.csv`. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-08-10

- **World Champion deck import reviewed — use as structure reference, not direct copy**:
  - Reviewed the newly added `World_Champion_Decks_2025/` folder and sampled lists
    across Junior, Senior, and Master divisions. **Reason for the implementation:**
    the original entry only recorded that the files were added; the more useful
    project takeaway is what their deck structure teaches for our own deck-building
    process.
  - The strongest repeated pattern is Trainer density and consistency, not large
    Pokemon piles. Across the sampled champion lists, Pokemon counts generally sit
    around 13-23, Trainer counts around 28-39, and Energy around 6-12. Repeated
    staples include search/draw/recovery/gust cards such as Ultra Ball, Boss's
    Orders, Iono, Fezandipiti ex, Nest Ball, Buddy-Buddy Poffin, Night Stretcher,
    Counter Catcher, Arven, Rare Candy, and Super Rod.
  - Current user workflow clarified: the immediate focus is intentionally only on
    building a **Pokemon shell** from the flagged card pool. Trainer and Energy
    shells should be added later after the Pokemon core is chosen, because the
    correct support package depends on the chosen attackers, evolution depth,
    Energy types, acceleration needs, and whether the deck asks the agent to pilot
    complex sequencing.
  - Practical rule carried forward: use the champion lists as deck-construction
    templates for ratios and consistency philosophy, but do not copy them directly.
    The hackathon card pool is different, and our submitted `main.py` must be able
    to pilot the resulting deck reliably. No deck files, `main.py`, or active
    `deck.csv` were changed. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Added ``World_Champion_Decks_2025`` for understanding deck creation and learning strategies:**
  - ``/Junior`` contains all the decks from Junior Division.
  - ``/Senior`` contains all the decks from Senior Division.
  - ``/Master`` contains all the decks from Master Division. - <span style="background-color:rgba(50, 205, 50, 0.31); color:#12db12">no_name</span>

- **Card-pool research pass on the user's 53 flagged cards; multi-type Energy solved;
  `Claude_Decks/` created**:
  - `Claude_Decks/` — new directory. All decks I build from now on go here only, kept
    separate from `Decs/` (user-authored + replay-derived), `Codex_Decks/`, and the
    active submission `deck.csv`.
  - **Leafeon ex `{G}{R}{W}` rainbow-cost problem — solved.** The user asked which
    cards can supply Energy of different types. Findings from the full 2,022-row pool:
    - **Terapagos [234]** is the single best answer: `Prism Charge ●` searches the deck
      for **up to 3 Basic Energy of different types and attaches them to your Tera
      Pokémon**. Leafeon ex is Tera(Stellar), so one attack costing one Colorless pays
      the entire `{G}{R}{W}` cost straight from deck. It also pairs with Leafeon ex's
      `[Tera]` (no damage while Benched), so the attacker loads in total safety.
    - **Sparkling Crystal [1165]** (Tool) makes any **Tera** Pokémon's attacks cost
      **1 Energy less, of any type** — it does not fix the rainbow so much as delete a
      third of it, and it applies to six already-flagged Tera cards.
    - Trap recorded: **Prism Energy [16]** is rainbow **only on Basic** Pokémon and
      **Neo Upper Energy [10]** only on **Stage 2**. Leafeon ex is Stage 1, so both
      provide plain `{C}` on it and are dead there. **Legacy Energy [12]** is genuinely
      wild but is **ACE SPEC** (1 copy) and competes with Energy Search Pro for the slot.
  - **Direct-attach sweep (non-Pokémon cards).** Confirmed **no Stadium in the pool
    attaches Energy** — all 26 checked; Levincia [1254] is the only Energy-related
    Stadium at all and it only moves Basic {L} from discard to *hand*. Direct attach
    lives on 11 Items/Supporters/Tools. Generic, any-type, any-target: **Waitress
    [1235]** (deck -> any 1 Pokémon, Active or Bench), **Crispin [1198]**, **Powerglass
    [1163]** (discard -> Active, repeats every turn, no Supporter slot), **Energy Coin
    [1135]** (coin-flip), **Rosa's Encouragement [1240]** (Stage 2, prize-gated).
    Archetype-locked: **Janine's Secret Art [1195]** is the strongest single card of the
    group (2 Basic {D} from deck onto 2 different {D} Pokémon) but is dark-only.
    **Heavy Baton [1160]** moves up to 3 Basic Energy to the Bench when a **retreat-4**
    Active is KO'd — four flagged cards qualify (Iron Thorns ex, Cetitan ex, Mega
    Venusaur ex, Orthworm ex).
  - **Review of `My_Deck_flags.txt` (53 cards).** Structural finding: the list is
    **53 Pokémon, 0 Trainers, 0 Energy**. Deck strength in this pool has repeatedly
    tracked Trainer consistency (LiamK sits at #1 on a 36-Trainer build), so ~30 slots
    of every deck built from this list are still unscouted.
  - Cards judged strongest, grouped by what they actually do:
    - *Passive/always-on:* Meganium [710] (each Basic {G} provides {G}{G} — a doubler,
      not accel), Aurorus [1033] (-50 to all {W}-attached), Ludicolo [262] (+40 HP to
      every Pokémon in play), Cornerstone Mask Ogerpon ex [117] (immune to any Pokémon
      **with an Ability**), Serperior ex [481] (+20 to all your attacks).
    - *Anti-meta hosers — the most interesting group:* **Iron Thorns ex [37]** turns off
      **every Rule Box Pokémon's Ability in play, both sides** while Active (this would
      blank Mega Lopunny/Mega Froslass, and also our own Teal Dance); **Tyranitar [290]**
      Item-locks the opponent while Active; **Genesect [142]** blocks ACE SPEC;
      **Farigiraf ex [83]** is immune to Basic Pokémon ex. Worth noting because copying
      LiamK's *deck* measured as a tie (49.2%) — attacking their *engine* is a different
      axis that has not been tried.
    - *Cost-break attackers:* Incineroar ex [79] (-{C} per opponent Bench Pokémon),
      Decidueye ex [1022] (ignores all {C} when opponent holds exactly 4 cards),
      Yanmega ex [340] (self-loads 3 Basic {G} on Bench->Active), Azumarill [315]
      (230 for `{P}` with any Tera in play).
  - **Corrections to my own review, after the user pushed back — all three of their
    challenges were right and are recorded as such:**
    - **Seviper [829]** — I called it a dead card without a {D} Mega ex. **Wrong.**
      `Pitch-Black Fangs` is **120 base**, 240 with the Ability live. It is also already
      enabled by **Mega Gengar ex [772]** ({D} Mega ex) on the same list.
    - **Oricorio ex [795] + Charizard** — the user's played combo checks out and is
      stronger than I credited. **Mega Charizard X ex [790]**'s `Inferno X {R}{R}` is
      **90x per {R} Energy discarded from among your Pokémon** — not just itself — so
      Oricorio's unlimited attach to the **Bench** builds a fuel tank Charizard spends.
      The hand-dependency the user then solved themselves with **Firebreather [1232]**
      (Supporter: search up to **7** Basic {R} Energy to hand), verified in the pool.
    - **Magneton [211] self-KO** — I logged the conceded Prize as a drawback. The user's
      read is better: it *powers your own cards*. Eight cards scale on "Prize cards your
      opponent has taken" — best fit is **Zekrom ex [515]** (`Voltage Burst` 130 **+50
      per prize**, same {L} type), so Magneton loads it from the discard, dies, and pays
      for the concession on the same turn. Also **Kingambit [901]** (+30/prize, passive).
      Noted for accuracy: **Luxray [1037]** scales on prizes ***you*** took — opposite
      direction, does **not** pair with Magneton.
  - One correction in the other direction: **Huntail [416]** recovers the **Basic {W}
    Energy cards to hand**, *not* the Knocked Out Pokémon. It limits tempo loss on a KO;
    it cannot replay the attacker. Kept on the list pending a {W} shell.
  - **Data-quality find:** [480] Servine and [481] Serperior ex are the **only 2 cards
    in the entire dataset with untranslated Japanese effect text**. Serperior ex's
    Regal Cheer is "+20 damage to the opponent's Active from your Pokémon's attacks" and
    Command the Grass is "150, then search your deck for up to 3 cards". Flagged because
    `main.py` reads effect text for heuristics, so a build around it needs the simulator
    behaviour verified first.
  - **Selection criterion carried forward from our own measurements:** deck power under
    *our* pilot is not paper power (one agent change moved Mega_Lopunny +6.6 and
    Mega_Latias -8.4 in the round-robin). The useful split of this list is **agent-proof**
    (passive effects that need no sequencing) vs **needs piloting**. The largest single
    cluster the user flagged — unlimited energy-move loops (Azumarill ex, Dewgong, Mega
    Venusaur ex, Mega Gengar ex, Iron Thorns ex) — is precisely what a greedy ladder plus
    1-ply MAIN search handles worst. No decks built yet; this entry is the research
    substrate for them. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Codex deck workspace created — future Codex-built decks isolated**:
  - `Codex_Decks/` — added a dedicated directory for deck lists created by Codex
    from this point onward. **Reason for the implementation:** keep exploratory
    Codex-built decks separate from existing `Decs/`, active submission files, and
    user/Claude deck work so future deck experiments are easier to compare without
    muddying the current project structure.
  - No deck files, `main.py`, or active `deck.csv` were changed. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Flagged-section import/export added — portable CSV and readable TXT**:
  - Added separate Import / TXT / CSV controls beside the flagged catalog section
    tabs in `deck_builder/index.html`, with transfer logic in `app.js` and compact
    responsive styling in `styles.css`. **Reason for the implementation:** make the
    Ability, Attack, and Both research collections portable between browser
    sessions/machines and shareable independently of the active 60-card deck.
  - CSV export writes a deterministic `card_id,flag` file containing all flagged
    cards. TXT export writes a readable grouped list under `[Ability]`, `[Attack]`,
    and `[Both]` headings with competition Card ID and card name. Files use the
    current deck name plus `_flags` so they remain distinguishable from deck CSV/
    TXT exports.
  - Added a dedicated flag-import dialog that accepts `.csv` and `.txt` files or
    pasted content. Import validates IDs against the 1,267-card local dataset,
    ignores unrecognized lines, reports skipped unknown IDs, and offers an explicit
    option to merge with current flags or replace all existing flags first. The
    imported state is persisted through the existing local-storage mechanism and
    immediately refreshes section totals and card results.
  - Deck import/export remains separate and unchanged. `main.py` and active
    `deck.csv` were not changed. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Flag interaction revised — direct buttons in expanded view only**:
  - Removed the flag dropdown from every catalog tile and replaced the expanded
    card's dropdown with three direct `Ability`, `Attack`, and `Both` buttons.
    **Reason for the implementation:** flagging is an intentional evaluation made
    while inspecting a card closely, so exposing a dropdown on every library tile
    added unnecessary visual density and did not match the requested workflow.
  - The current flag is shown as the active button. Clicking another button moves
    the card to that flag section; clicking the already-active button clears the
    flag. Catalog cards retain only a small read-only criterion badge and colored
    edge so previously flagged cards remain recognizable without presenting an
    editing control outside expanded view.
  - Persistent storage and the Card Library / Ability / Attack / Both sections are
    unchanged. Validation passed with `node --check deck_builder\app.js`, and a
    source scan confirmed the old tile and expanded-view dropdown controls were
    removed. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Persistent card flagging added — Ability, Attack, and Both catalog sections**:
  - Added independent card flags to `deck_builder/app.js` with four possible
    states: unflagged, `Ability`, `Attack`, or `Both`. Flags are stored alongside
    the existing deck state in browser local storage and restored when the deck
    builder is reopened. **Reason for the implementation:** support research and
    deck exploration before committing cards to a 60-card list, allowing useful
    cards to be collected according to whether their Ability, Attack, or complete
    card design is the reason they are being considered.
  - Added Card Library / Ability / Attack / Both section tabs above the catalog.
    Each section displays live card totals and reuses the complete existing card
    experience: artwork grid, search, card-kind/type/expansion/stage filters,
    sorting, keyboard navigation, focused-card inspection, and deck add/remove
    controls. The three flag sections are exclusive, so a card appears in the one
    section matching its current criterion.
  - Added a flag selector to every catalog card and to the expanded-card header.
    Flagged cards receive a subtle criterion-colored edge in the library. Changing
    or removing a flag immediately updates the section counts and visible results;
    if the expanded card no longer belongs to the active flagged section, the
    inspector closes back to that section cleanly.
  - Flag state remains separate from deck membership: flagging does not alter the
    60-card count, and cards can still be added or removed normally from every
    flagged section. Existing deck autosave, validation, import, and CSV/TXT export
    behavior is preserved. Validation passed with `node --check
    deck_builder\app.js`, and the updated markup contains no duplicate element IDs.
    `main.py` and active `deck.csv` were not changed. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-08-09

- **Focused-card opening stabilized — original catalog remains as the backdrop**:
  - Removed the separately rendered focus-mode background grid from
    `deck_builder/index.html`, `app.js`, and `styles.css`. The focused inspector
    now overlays the existing Card Catalog directly and applies a brief
    semi-transparent dimming fade plus a small card-entry transition.
    **Reason for the implementation:** replacing the visible catalog with a newly
    generated dark card grid caused an abrupt background change when opening an
    individual card, breaking the user's spatial context. Preserving the exact
    catalog underneath makes the transition feel continuous while keeping the
    inspected card and controls prominent.
  - Removed the unused backdrop-rendering JavaScript and added a reduced-motion
    fallback. Navigation, live deck visibility, and keyboard/visible `+` / `-`
    controls are unchanged. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Focused card inspector confined to Card Catalog — live deck remains visible**:
  - Reworked the focused-card interaction in `deck_builder/app.js` and
    `styles.css` so the inspector is mounted inside `.catalogPanel` and covers
    only the center card catalog rather than the entire browser viewport.
    **Reason for the implementation:** the full-screen inspector hid the selected
    deck, making it difficult to know which cards and quantities had already been
    added while browsing. Keeping the filter panel and right-hand deck editor
    visible preserves context and makes each add/remove decision immediately
    observable.
  - The inspector retains its centered card, dimmed neighboring cards, previous/
    next navigation, visible red `-` / `+` controls, keyboard arrow navigation,
    keyboard `+` / `-`, and Escape-to-close. Add/remove still uses the shared deck
    update path, so counts, legality feedback, composition, and selected rows in
    the right panel refresh immediately.
  - Removed the focus-mode body scroll lock and disabled the redundant internal
    deck drawer. The existing right deck panel is now the single visible source of
    truth for selected cards while the inspector is open. Responsive focus-header,
    card, arrow, and control dimensions were tightened for the smaller catalog
    container.
  - Validation: `node --check deck_builder\app.js` passed. `design-qa.md` documents
    the new scoped state and remains blocked because the integrated browser runtime
    again failed during initialization, preventing rendered screenshot comparison
    and console/interaction verification. `main.py` and active `deck.csv` were not
    changed. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Keyboard-focused card browser added — arrow navigation and direct +/- deck editing**:
  - Reworked the visual browsing interaction in `deck_builder/index.html`,
    `styles.css`, and `app.js` around the supplied game-style deck-builder
    references. Selecting card artwork now opens a full-viewport focused browser
    with a large centered card, dimmed surrounding card gallery, previous/next
    controls, a persistent deck count, large red remove/add controls, and an
    optional right-side visual deck drawer. **Reason for the implementation:**
    make rapid card comparison and deck editing practical from the keyboard and
    visually closer to the interaction model the user requested, instead of
    requiring repeated pointer travel between small catalog cards and the deck
    list.
  - Added roving keyboard navigation in the normal card grid: Left/Right move one
    card, Up/Down move approximately one grid row, Enter opens the focused card,
    and `+` / `-` add or remove the focused grid card. Every catalog tile now also
    exposes visible `-`, selected-count, and `+` controls.
  - Focus mode navigates through the complete current filtered result set with
    Left/Right or Up/Down (wrapping at the ends), supports keyboard and visible
    `+` / `-` deck editing, closes with Escape, and can toggle the deck drawer with
    `D`. Closing restores focus to the originating catalog card where available.
  - The focus-mode deck drawer shows live legality status, Pokemon/Trainer/Energy
    tabs and counts, card artwork, and selected quantities. Selecting a drawer
    card moves the centered inspector to that card without closing the drawer.
    Existing filtering, autosave, validation, import, and CSV/TXT export behavior
    remains intact; `main.py` and the active `deck.csv` were not changed.
  - Validation: `node --check deck_builder\app.js` passed and a static UI-ID check
    found no missing referenced elements. `design-qa.md` records the visual QA as
    blocked because the integrated browser runtime failed to initialize, so a
    browser-rendered screenshot comparison and interaction/console pass could not
    be completed in this environment. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Deck builder rebuilt — self-contained visual card library and interactive 60-card workspace**:
  - Replaced the first `deck_builder/index.html`, `styles.css`, and `app.js`
    implementation with an image-first deck-building workspace inspired by the
    structure of Limitless: compact filters on the left, a scrollable visual card
    catalog in the center, and a persistent grouped deck editor on the right.
    **Reason for the implementation:** the first version reported mapped images
    but referenced them through absolute `file:///C:/...` URLs outside the
    project, leaving the visible catalog blank in the browser and making the
    builder fragile whenever the external folder path or browser file policy
    changed.
  - Updated `deck_builder/generate_card_data.py` to create optimized WebP card
    previews inside `deck_builder/assets/cards/` and write relative image paths
    into `card-data.js`. All 1,267 supplied JPG card images are now packaged as
    1,267 local previews (about 38.1 MB instead of copying the 219.1 MB originals),
    so `index.html` no longer depends on external absolute image URLs.
  - The catalog now displays actual card artwork, selection-count badges, card
    names/set numbers/competition IDs, incremental result loading, search across
    names/attacks/effects, Pokemon/Trainer/Energy segmented filtering, Energy
    type, expansion, stage/trainer type, Mega, Ability, and sort controls. Clicking
    artwork opens a full preview with HP, evolution, attacks, effects, Weakness,
    Resistance, Retreat, and add/remove controls.
  - The deck workspace now has a live circular 60-card counter, Pokemon/Trainer/
    Energy composition, grouped rows with thumbnails and steppers, same-name
    four-copy enforcement across different printings, Basic Energy exceptions,
    ACE SPEC and Basic Pokemon checks, local browser autosave, deck naming, clear
    confirmation, and responsive desktop/mobile layouts.
  - Import now accepts both one-ID-per-line CSV content and grouped readable TXT
    lines. Export writes the chosen deck name to `.csv` in the one-ID-per-line
    competition format and `.txt` in the same grouped structure as
    `Decs/Hydrapple.txt`. The active submission `main.py` and `deck.csv` were not
    changed.
  - Validation: `node --check deck_builder\app.js` and
    `python -m py_compile deck_builder\generate_card_data.py` passed; regeneration
    reported 1,267 cards and 1,267 previews; an independent manifest/filesystem
    check found zero missing image paths; and a representative generated WebP was
    visually inspected and readable. The integrated browser preview could not be
    started because its connection failed during initialization, so final
    in-browser interaction remains a manual check by opening `index.html`. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Local deck builder added — interactive dataset-only deck construction/export**:
  - `deck_builder/index.html`, `styles.css`, and `app.js` — added a standalone
    browser deck builder for the cards available in this project dataset. It
    presents filters on the left, a searchable card catalog in the center, and the
    selected deck on the right. Filters include card kind, Energy/type, expansion,
    stage/trainer type, Mega-only, ability-text, and image availability.
    **Reason for the implementation:** make deck exploration faster and less error
    prone than editing ID lists by hand, while keeping the active submission
    `main.py` and `deck.csv` untouched.
  - `deck_builder/generate_card_data.py` — added a generator that groups
    `dataset/EN_Card_Data.csv` by competition `Card ID`, preserves attack/effect
    text, classifies cards as Pokemon/Trainer/Energy, and maps every card to the
    image folder at `C:\Users\novan\Desktop\Pokemon_Dataset` using expansion +
    collection number. Generated `deck_builder/card-data.js` contains 1,267 cards
    and 1,267 mapped image URLs.
  - Export support writes `deck.csv` as one card ID per line, matching
    `Decs/Hydrapple.csv`, and `deck.txt` in the grouped readable format used by
    `Decs/Hydrapple.txt`. The UI also supports pasting/importing an existing card
    ID list, live 60-card validation, non-Basic 4-copy enforcement, Basic Energy
    exceptions, ACE SPEC warnings, and Pokemon/Trainer/Energy count breakdowns.
  - Verified live: `python deck_builder\generate_card_data.py` regenerated the
    static card data; `python -m py_compile deck_builder\generate_card_data.py`
    passed; `node --check deck_builder\app.js` passed; a metadata sanity check
    confirmed 1,267 card records and 1,267 image mappings. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Mega Gardevoir ex challenger built — stable Psychic engine explored, not adopted**:
  - `Decs/Codex_MegaGardevoir.txt` / `.csv` — added a separate 60-card deck built
    around Mega Gardevoir ex, leaving the active submission `deck.csv` unchanged.
    **Reason for the implementation:** test whether Gardevoir's one-Energy
    `Overflowing Wishes` setup attack and board-wide `Mega Symphonia` scaling can
    form a stable alternative submission archetype rather than continuing to tune
    only Hydrapple and its direct counters.
  - Final composition is 16 Pokemon / 31 Trainers / 13 Energy. The 4 Ralts / 2
    Kirlia / 3 Mega Gardevoir ex core has both natural-evolution and Rare Candy
    routes. Xerneas, Smoochum, Telepathic Psychic Energy, and the Precious Trolley
    ACE SPEC provide four overlapping ways to fill or energize the Bench; Hilda,
    Mega Signal, Ultra Ball, and Buddy-Buddy Poffin provide redundant search.
    Latias ex removes Basic retreat costs, Fezandipiti ex supplies post-KO draw,
    Lillie's Clefairy ex adds Dragon coverage, Air Balloon is the Mega's retreat
    tool, and Mystery Garden converts spare Energy into draw.
  - Legal/count validation passed: exactly 60 IDs, no non-Basic card above four
    copies, and exactly one ACE SPEC. The list contains 10 Basic Psychic Energy and
    3 Telepathic Psychic Energy, leaving enough Basic Energy targets for
    `Overflowing Wishes` while making early Bench development more reliable.
  - Final stability screen: 38/40 = **95.0% versus random**, with zero draws or
    timeouts. The harder Hydrapple screen was only **7/40 = 17.5% [95% CI
    8.7-32.0%]**, so consistency against a blind opponent does not translate into
    competitive tempo against the current strong deck.
  - Several alternatives were tested and rejected: a three-Latias tempo package
    scored 4/40 versus Hydrapple; a Mega Diancie package scored 6/40; a
    single-multi-prize focused shell scored 4/40; and a denser Scream Tail hybrid
    scored 5/40. An independently created `Claude_Mega_Gardevoir` list was tied in
    direct play (Codex 18/40, 45.0%, CI spans 50%) and itself scored only 8/40 into
    Hydrapple. These small screens are not precise rankings, but every tested
    Gardevoir branch showed the same Stage-2 tempo ceiling.
  - Decision: **keep as an exploratory challenger; do not adopt**. The deck is legal,
    coherent, and functional, but current evidence says Hydrapple and the Fire
    anti-Hydrapple candidate are materially stronger under the present `main.py`.
    Improving Gardevoir further likely requires deck-specific planning in the agent
    (setup-attack timing and promotion discipline), not more blind list swaps. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **How much of a bad deck result is the DECK vs the AGENT? Measured on
  Claude_Mega_Gardevoir — a deck-aware agent nearly DOUBLES it, and still loses**:
  - Question raised: every deck above was piloted by an agent tuned on Hydrapple.
    So how much of Gardevoir's 20% was the deck being bad vs the agent being wrong
    for it? Built a Gardevoir-aware agent as a wrapper over `main.py` (no files
    modified) and ran 4 arms x 100 seat-balanced games vs Hydrapple, with Hydrapple
    always piloted by the STOCK agent:

    | arm | change | result vs Hydrapple |
    |---|---|---|
    | stock | unmodified `main.agent` | 21.0% [14.2-30.0] |
    | dmg | Mega Symphonia damage estimated **dynamically** each call as 50 x (all {P} Energy in play) | 34.0% [25.5-43.7] |
    | bench | dmg + attach Energy to the **Bench** instead of the Active | **40.0% [30.9-49.8]** |
    | full | bench + crude "force Gardevoir into the Active slot" | 38.0% [29.1-47.8] |

  - **+19 points, ~2x the win rate, from agent changes alone with the deck untouched.**
    So a meaningful share of a deck's measured score here is agent fit, not deck
    quality — deck head-to-heads under one fixed agent systematically understate any
    deck the agent cannot read.
  - Of the two changes that mattered, they are NOT the same kind of thing:
    - The variable-damage estimate is a **general** agent fix. 381 of 1556 engine
      attacks report `damage = 0`; any deck built on a scaling attacker is currently
      mis-valued. This belongs in `main.py` regardless of which deck we submit.
    - Bench-first Energy attachment is **deck-specific** and probably WRONG for
      Hydrapple (which wants its Active powered). This is genuine agent/deck
      co-tuning, and the competition submits exactly one `main.py` + one `deck.csv`,
      so co-tuning is the correct strategy rather than a compromise.
  - Forcing Gardevoir into the Active slot did NOT help (38% vs 40%, overlapping CIs).
    The gain came from the agent *evaluating* the card correctly, not from steering it.
  - Not chased further: the agent still never uses **Overflowing Wishes** (0 printed
    damage), which is the deck's actual ramp engine (+1 {P} Energy per Benched Pokémon).
    A fuller deck-aware agent would ramp with it on a wide bench, then swing. Untested.
  - Conclusion: even with a dedicated agent, Gardevoir sits at 40% vs Hydrapple while
    `Codex_FireCamerupt` reaches 66% under the *stock* agent. Gardevoir is not worth
    further investment; the variable-damage fix is, independently of deck choice.
    — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Two Claude challenger decks built and MEASURED — both LOSE; the useful output is
  a agent blind spot, not the decks (neither adopted)**:
  - `Decs/Claude_Zygarde_Ramp.txt` / `.csv` — 60-card Fighting deck, all attackers
    **Basic** (4 Mega Zygarde ex / 4 Cornerstone Mask Ogerpon ex / 4 Cornerstone Mask
    Ogerpon / 2 Regirock ex, 31 Trainers, 15 Basic {F} Energy). Thesis came from the
    2026-08-08 ladder analysis (wins avg 6.0 turns, losses avg 17.8, one loss with
    ZERO attacks in 13 turns): if we lose by never coming online, remove every
    evolution step. Two rules facts drove the picks — **Basic Megas exist**
    (`prev-stage = n/a`), so they skip the "evolving into a Mega ends your turn" cost
    (POKEMON_RULES.md sec.12); and `_best_attack_index` ranks by printed damage only,
    so drawback text is invisible. Rejected on that basis: Mega Mawile ex (260 dmg
    but base drops to **30** once the target has damage counters — the bot would spam
    30s), Gouging Fire ex, Koraidon/Latias/Yveltal/Zacian ex (next-turn lockouts),
    Pikachu ex / Black Kyurem ex (self-damage), Iron Boulder (does nothing unless hand
    sizes match).
  - Measured: `deck_head2head.py Claude_Zygarde_Ramp Hydrapple 50` → **37/100 = 37.0%
    [95% CI 28.2-46.8%]**, avg 135 steps. Hydrapple better; CI upper bound below 50%.
  - **Two hypotheses tested and BOTH refuted**, which is the point of the entry:
    1. *"`_prize_value` returns 3 for megaEx but POKEMON_RULES.md sec.12 says Mega = 2,
       so the agent over-penalizes its own Mega."* Monkeypatched to 2, re-ran:
       **23/100 = 23.0%** — WORSE. Making the agent more willing to lead with Zygarde
       made it lose harder, i.e. Zygarde in the Active slot was feeding Prizes.
    2. *"Basic attackers fix the ladder losses."* Tempo probe (12 mirror games/deck):
       Claude_Zygarde_Ramp first attack turn **3.7**, 6.9 attacks/game, **627** printed
       dmg/game; Hydrapple turn 4.0, 4.8 attacks/game, **142** dmg/game. The deck
       attacks earlier, more often, for 4.4x more damage — **and still loses**. So
       "comes online slowly" was NOT the binding constraint, and the ladder diagnosis
       does not translate into "more damage sooner => more wins". Treat the earlier
       energy-acceleration recommendation as unproven.
    - Best remaining explanation: **prize economy**. 10 of 14 Pokémon were Rule Box
      (2 Prizes per KO), so the opponent needed only ~3 KOs; Hydrapple has 13
      single-Prize bodies to absorb trades. Self-inflicted secondary bug: Cornerstone
      Mask Ogerpon's Rock Kagura is a **0-damage** attack included as a ramp trick, but
      the agent picks max damage among *legal* attacks, so on 1 Energy it attacked for
      literally 0 (avg damage/attack 91, vs Gaia Wave's 200).
  - `Decs/Claude_Mega_Gardevoir.txt` / `.csv` — 60-card Psychic deck built on request
    around **Mega Gardevoir ex** (4 Mega Gardevoir ex / 4 Ralts / 2 Kirlia / 4 Scream
    Tail ex / 2 Smoochum, 27 Trainers, 16 Basic {P} Energy). The combo is real:
    Mega Symphonia costs **1 Energy** and does **50x every {P} Energy attached to ALL
    your Pokémon**, so damage scales off the bench rather than the attacker; Smoochum's
    Delightful Kiss costs **zero** Energy and pulls 2 {P} Energy from deck onto the
    Bench; Rare Candy skips Kirlia; Buddy-Buddy Poffin fetches Ralts/Smoochum (both
    <=70 HP); Gardevoir is 360 HP.
  - Measured: v1 (support-heavy) **19/100 = 19.0% [12.5-27.8%]**; v2 (swapped the
    fragile support bodies for 4 Scream Tail ex) **20/100 = 20.0% [13.3-28.9%]**.
    Composition fix did not move it.
  - **ROOT CAUSE — the agent is blind to variable-damage attacks.** The engine reports
    `Attack.damage = 0` for "50x"-style attacks, and the agent ranks every attacker by
    that field (`_best_attack_index`, `_best_usable_damage`). So it believes Mega
    Gardevoir ex is a zero-damage Pokémon. Probe over 10 games: Gardevoir held the
    Active slot only **55 steps** while Scream Tail ex (printed 120) held **334** — the
    agent kept promoting the weaker card. Proof by experiment: patching ONLY the
    agent's view of Mega Symphonia (0 -> 200), changing no cards, moved the same
    matchup **20.0% -> 37.0%** (+17 points, one line).
  - Scope of the blind spot: **109 cards** in the pool have variable damage in the
    card data; **381 of 1556** engine attacks report `damage = 0`. That whole class of
    cards is currently un-pickable by our heuristics. Fixing it means teaching
    `_best_usable_damage` to estimate scaling attacks (for Mega Symphonia:
    50 x count of {P} Energy in play) — an **agent** change, not a deck change.
  - This is the concrete answer to "would a new deck work on the current main.py?":
    for Mega Gardevoir, **no** — it cannot function until the agent can see variable
    damage. Decision: **do not adopt either deck.** Codex's `Codex_FireCamerupt`
    (66% vs Hydrapple, logged below) is a far stronger challenger than either of
    these; both Claude decks are kept as recorded negative results with their
    measurements written into their `.txt` files. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Codex challenger deck built — Fire/Mega Camerupt anti-Hydrapple candidate
  (not adopted)**:
  - `Decs/Codex_FireCamerupt.txt` / `.csv` — added a separate 60-card challenger
    deck, leaving the active submission `deck.csv` unchanged. The concept is a Fire
    tempo deck aimed at Hydrapple's Grass weakness while staying simple enough for
    our current lookahead agent to pilot: 4 Numel / 3 Mega Camerupt ex as the main
    Mega line, Volcanion ex and Hearthflame Mask Ogerpon ex as Basic Fire attackers,
    Oricorio ex for Fire Energy acceleration once a Fire Mega is in play, and
    Flareon ex as a deck-to-board Energy accelerator. The Trainer package borrows
    the proven high-consistency shell pattern: Lillie's Determination, Ultra Ball,
    Hilda, Mega Signal, Pokégear, Firebreather, Boss's Orders, Air Balloon, and
    Surfer.
  - Legal/count validation passed locally: 60 IDs, no non-basic card above 4 copies,
    exactly 1 ACE SPEC (`Enriching Energy`). The readable `.txt` list classifies it
    as 19 Pokémon / 26 Trainers / 15 Energy.
  - Initial measurement under our current agent: `python deck_head2head.py
    Codex_FireCamerupt Hydrapple 50` finished **66/100 = 66.0%
    [95% CI 56.3-74.5%]**, avg 125 steps, 0 draws/timeouts. This is a promising
    anti-Hydrapple signal, but it is only 100 total games and should not trigger a
    deck swap by itself.
  - Sanity check into the known leaderboard-style archetype was weaker and noisy:
    `python deck_head2head.py Codex_FireCamerupt LiamK_MegaLopunny 20` finished
    **14/40 = 35.0% [95% CI 22.1-50.5%]**, avg 138 steps, 0 draws/timeouts. The CI
    still touches 50%, but the point estimate warns that this may be a targeted
    Hydrapple counter rather than a broadly stronger deck. Larger runs timed out at
    the current command budget, so this remains exploratory.
  - Decision: **do not adopt**. Keep Hydrapple as the active submission deck until a
    challenger pair proves itself across Hydrapple, LiamK-style Mega Lopunny, and the
    existing round-robin field. This deck is useful as a challenger/anti-meta probe,
    not yet as the default submission. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-08-08

- **First Kaggle submissions — two failed, root cause found and fixed (`__file__` under
  `exec()`)**:
  - Submitted to the **Simulation** competition for the first time (entry gate was
    already cleared; `user_has_entered: true`). Submissions `#55335664` and `#55351154`
    both came back `status: ERROR` / "Validation Episode failed."
  - **Root cause** (from the Agent 0 Logs attachment on the Submissions page, which is
    the ONLY place the traceback is exposed — the MCP `get_episode_agent_logs` tool
    returns a content-free stub and no public URL pattern serves it the way
    `episodes/<id>/replay.json` does):
    ```
    File "/kaggle_simulations/agent/main.py", line 55, in read_deck_csv
        local_path = Path(__file__).with_name("deck.csv")
    NameError: name '__file__' is not defined
    ```
    `kaggle_environments/agent.py` runs the submitted `main.py` by `exec()`-ing its
    source into a fresh namespace, so **`__file__` is never defined**. Every local
    execution path (normal import, `python main.py`, `run_local.py`, Docker) defines
    `__file__`, so no amount of local testing could reproduce it. The failure hit the
    very first `agent()` call (the deck-selection request, `select: null`) — visible in
    the replay as `remainingOverageTime` dropping only ~0.08s before `ERROR`.
  - Aggravating factor: the `agent()` safety net added earlier that day swallowed the
    `NameError` and returned `[]`, converting a loud crash into a silent **empty deck**
    — still invalid, but harder to diagnose. Broad `except Exception` around an entry
    point hides exactly the errors worth seeing.
  - `sample_submission/sample_submission/main.py` — `read_deck_csv()` now resolves
    `deck.csv` from `globals().get("__file__")` when present, then
    `/kaggle_simulations/agent/deck.csv`, then CWD. No bare `__file__` reference.
  - `sample_submission/sample_submission/cg/sim.py` — native engine load deferred from
    module import to first attribute access (`_LazyLib`). This was speculative — it was
    NOT the cause (the `.so` loads fine on Linux, verified in a container) — but it does
    mean a native-lib failure can no longer kill `import main` before `agent()` exists.
  - Verified live: replicated Kaggle's execution model in a Linux container
    (`exec(compile(src, "main.py", "exec"), {"__name__": "__main__"})`, no `__file__`)
    and fed it the real server-generated observation JSON pulled from a public ladder
    replay. Fixed code returns all 60 card IDs; the previously-submitted code returns
    `0` under the identical harness (negative control). Full game still completes
    (129 steps) on Linux. Resubmitted as `#55351602`.
  - Note for the Strategy writeup: the deck/agent were never the problem for those two
    submissions — this was purely a submission-harness bug, and cost ~14h of ladder time.
  - Also pulled and analysed the rank-1 opponent's deck (`Majkel1337`, 1277.8) from a
    public replay: 4× Mega Lucario ex + 4× Fighting Gong (energy accel) + 4× Premium
    Power Pro (damage boost) + 4× Judge — a 4-copy consistency build around one attacker,
    vs our 5-line toolbox with no energy-acceleration item. Their observed win rate is
    **79.2% (38-10 over 48 ladder games)**, not 100% — they trade fairly evenly with
    LiamK and flg. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Deck builder committed source-only; its card data held out as Competition Data**:
  - `.gitignore` — added `deck_builder/card-data.js` and `deck_builder/assets/`.
    Caught while staging: `card-data.js` (887 KB) is `dataset/EN_Card_Data.csv`
    repackaged as JSON — all 1,267 cards with HP, attack costs, damage and effect text
    — and `assets/cards/` is the 1,267 card images (~42 MB). Both are **Competition
    Data** under EVALUATION.md §5, and this repo's own ignore rule already says never to
    commit such files "even to a private remote you might later make public". The remote
    is currently private, so nothing leaked, but committing would have written them into
    git history permanently, where flipping the repo public or adding a collaborator
    republishes them and removal needs a history rewrite.
  - `deck_builder/generate_card_data.py` **is** committed, so `card-data.js` rebuilds
    from `dataset/` on any machine — holding the data out costs nothing.
  - Committed as `e0d5526` on `main` and pushed: deck-builder source (`index.html`,
    `app.js`, `styles.css`, the generator), `design-qa.md`, 7 new `Decs/` lists, and the
    PROGRESS entries below. Verified before committing that nothing matching
    `card-data|assets/cards|dataset/|liamk|.webp|.pyc` was staged.
  - Note on the earlier `.gitignore` edit (not mine): the ignore rule was loosened from
    `Decs/` to `Decs/LiamK_*`, so our own authored deck lists are now tracked while the
    replay-reconstructed LiamK lists stay ignored. That split is correct and is kept. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Cleanup shipped, baseline re-frozen — and the attacker-concentration hypothesis is
  FALSIFIED**:
  - `sample_submission/sample_submission/main.py` — deleted
    `_should_retreat_to_better_attacker` (~40 lines, magic thresholds 30/60/90/120 and
    a prize-exposure branch) after the ablation measured its contribution at exactly
    zero. Retreat reverted to the simple pre-2026-08-08 rule at step 7 (below "attack
    anyway", `hp <= 30% maxHp` and a healthier Bench option). Left a `ponytail:` comment
    naming the ablation result in-code so the gate is not rebuilt blind later.
    **`_live_attacker_score` was deliberately KEPT** — it is now load-bearing for
    `_choose_card`, which is where the measured gain actually lives.
  - `sample_submission/sample_submission/attacker_share.py` — new. The attacker-share
    metric had been quoted in three separate entries with no committed tool behind it
    (the 08-07 numbers came from an ad-hoc replay decode). This harness wraps the agent,
    records the Active card on every selected ATTACK option, and prints the full
    per-card ranking plus top-2 concentration. It does **not** hardcode a "real vs weak
    attacker" card list — the split is left visible in the ranking so the reader
    classifies, not the tool.
  - `sample_submission/sample_submission/retreat_ablation.py` — guarded its monkeypatch
    with `getattr`, so the harness degrades to no-op arms instead of crashing now that
    the gate it ablated no longer exists.
  - **Re-test of the cleaned agent** (vs the old frozen 07-18 baseline, so directly
    comparable to everything above):

    | test | result | reads against |
    |---|---|---|
    | `self_play_benchmark.py 500` | **71.6% [67.5-75.4]** (358/142/0), 121.6 steps | fix #2 control 72.8%, Codex's 71.2% — a **tie**, so removing the retreat gate cost nothing, exactly as the ablation predicted |
    | `benchmark.py 200` vs random | 97.0% (194/200) | 96.0% previously — healthy, no legality/crash regression |
    | `attacker_share.py 40` | **top-2 = 60.9%** | 66.3% on 2026-08-07 |

  - **The headline is the attacker-share null.** Win rate rose ~10pts while attacker
    concentration **fell** (66.3% -> 60.9%), and the weak/support share is unchanged at
    **35.6%** (Celebi 10.3%, Tapu Bulu 9.2%, Regigigas 6.3%, Applin 2.9%, Chikorita
    2.9%, Bayleef 2.9%, Dipplin 1.1%) — the same ~34-40% band logged since 08-04.
    So **attacker concentration does not drive our win rate**, and the "close the ~22pt
    concentration gap vs LiamK" target set on 2026-08-07 was aimed at a metric that does
    not convert. It should stop driving work.
  - What *did* move is the composition **within** the attackers: Teal Mask Ogerpon ex
    54.7% -> 39.7%, **Hydrapple ex 11.6% -> 21.3%**. The promotion fix routes swings to
    the deck's heavier hitter rather than concentrating them into fewer cards. The gain
    is attacker **quality per swing**, not concentration.
  - Instrument caveat, stated so the numbers are not over-read: this harness decodes
    MAIN-phase ATTACK selections on **one seat**, while the 08-07 figures came from a
    both-seats replay decode. Attacks/game are therefore **not comparable** (4.3 here vs
    14.4 there). Shares are comparable in kind; the honest claim is "concentration did
    not improve", not a precise -5.4pt delta.
  - `sample_submission/sample_submission/previous_agent.py` — **re-frozen** to the
    cleaned agent (was the 2026-07-18 pre-lookahead greedy, preserved in git at
    `7f732ba`). Reason: the old baseline had stopped discriminating — every change since
    lookahead scored 60-72% against it, so a mediocre change and a good one looked
    similar. All future deltas measure against the *current shipped* policy, which is
    also much closer to what the ladder actually pits us against. Verified the freeze:
    module imports independently of `main`, `SEARCH_MAIN=True`, retreat gate absent, and
    `self_play_benchmark.py 60` of the agent against its own frozen copy returns 45.0%
    [33.1-57.5] — a CI spanning 50%, as identical policies must.
  - Consequence for reading this log: **every win-rate number logged before this entry
    is "vs the 07-18 greedy" and every number after it is "vs the 08-08 cleaned agent".
    They are not on the same scale.** — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Fix #2 ablated — the entire gain is the CARD/promotion change; the retreat gate
  contributes nothing**:
  - `sample_submission/sample_submission/retreat_ablation.py` — new harness. Fix #2
    shipped **two** mechanisms in one measurement, so its +6.6pts could not be credited
    to either: (a) the tactical retreat gate ordered above "attack anyway", and (b)
    own-board `CARD` selection ranked by `_live_attacker_score` instead of static
    `_option_card_power`. Arm (b) fires on **every forced promotion after a KO** — far
    more often than RETREAT, which was only 3.9% of MAIN decisions (2026-08-07 table).
    The harness monkeypatches each arm off independently (same pattern as
    `eval_ablation.py`) and runs all four combinations against the same frozen
    `previous_agent`.
  - **Also added a two-proportion z-test** (`two_prop_z`) and switched attribution
    calls to it. Method note: comparing two Wilson CIs by eye is **over-conservative** —
    non-overlap implies significance, but *overlap does not imply a non-significant
    difference*. Fix #2's own headline is the example: 71.2% [67.1-75.0] vs the 64.6%
    [60.3-68.7] reference overlaps by 1.6pts, yet the correct test gives z=2.24,
    **p=0.025** — genuinely significant. The standing "refuse to act on overlapping
    CIs" rule should be read as "refuse to act without a test", not "overlap = tie".
  - **Results (500 games/arm, 2,000 games, vs frozen `previous_agent`):**

    | arm | wins | win rate | delta vs control | z | p |
    |---|---|---|---|---|---|
    | both (control) | 364/500 | **72.8%** [68.7-76.5] | — | — | — |
    | retreat_off | 352/500 | 70.4% [66.3-74.2] | -2.4 | -0.84 | 0.400 **tie** |
    | card_off | 312/500 | 62.4% [58.1-66.5] | -10.4 | -3.51 | 0.0004 **sig** |
    | neither | 314/500 | 62.8% [58.5-66.9] | -10.0 | -3.38 | 0.0007 **sig** |

  - The control also **replicates** fix #2's headline independently (72.8% here vs
    71.2% as logged), so the effect is real and not a single-run fluke.
  - **Attribution is unambiguous: `card_off` (62.4%) and `neither` (62.8%) are the
    same number.** Turning the retreat gate off costs nothing whether the CARD change
    is present or absent, i.e. the retreat mechanism is **inert**. All ~10pts belong to
    the live-attacker promotion ranking.
  - **Interpretation — the attacker-discipline hypothesis survives, but the lever was
    wrong.** Attacker choice is not decided by voluntarily retreating; it is decided at
    **forced promotion after a KO**, which happens every time something dies and was
    previously resolved by static printed card power (biggest HP + printed damage), not
    by who can actually attack right now. That is the mechanism behind the "attacks with
    whatever is already Active" flaw: the agent kept *promoting* the wrong Pokemon.
    Retreat was always the rarer and more expensive way to fix the same problem.
  - Consequence for `main.py`: `_should_retreat_to_better_attacker` (~40 lines, magic
    thresholds 30/60/90/120 and a prize-exposure branch) is now **measured dead weight**
    — unproven complexity of exactly the kind the 08-04 KO-risk term was flagged for.
    Recommend reverting the retreat portion to the pre-fix #1 rule and keeping only the
    CARD change; not done in this entry, pending decision. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Attacker-discipline retreat fix #2 — conservative tactical retreat gate (kept
  pending future challenger tests)**:
  - `sample_submission/sample_submission/main.py` — replaced the broad attempt #1
    rule ("retreat if any Benched Pokemon has higher usable damage") with a
    conservative tactical gate. Retreat still sits above "attack anyway", but now
    only fires when it turns a non-lethal line into an immediate KO or when the
    Benched attacker offers a meaningful immediate damage gain. The gate also avoids
    exposing a higher-prize attacker to an immediate KO for only a modest damage
    upgrade.
  - Added `_live_attacker_score()` and `_should_retreat_to_better_attacker()` so the
    rule is explicit and easier to tune. Also updated own-board `CARD` selections to
    prefer live in-play attackers by usable damage/HP/energy rather than static
    printed card power, so after choosing RETREAT the follow-up promoted Pokemon is
    more likely to be the actual attacker instead of merely the strongest printed
    card.
  - Reasoning: attempt #1 found the real structural issue (retreat was unreachable in
    greedy rollout whenever any attack was legal), but its fix was too blunt and
    measured as a tie with a lower point estimate. This pass keeps the valid ordering
    insight while requiring a concrete tactical payoff before giving up the current
    attack.
  - Verified live: `python -m py_compile` passed for `main.py`, `self_play_benchmark.py`,
    and `benchmark.py`; `python benchmark.py 40` finished 40/40 wins vs random;
    `python self_play_benchmark.py 200` finished current 138 / previous 62 / draw 0
    = **69.0% [95% CI 62.3-75.0%]**; `python self_play_benchmark.py 500` finished
    current 356 / previous 143 / draw 1 = **71.2% [95% CI 67.1-75.0%]**, avg 123.0
    steps. Compared with the shipped lookahead reference 64.6% [60.3-68.7%], this is
    a materially higher point estimate with only slight CI overlap, so it is kept as
    the current working version rather than rejected like attempt #1. Next useful
    check: measure attacker-share directly to confirm the win-rate gain actually
    came from fewer weak/support attacks. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Attacker-discipline attempt #1 — retreat promoted above "attack anyway" (measured
  a TIE, not shipped on evidence)**:
  - `sample_submission/sample_submission/main.py` — reordered the greedy MAIN ladder:
    the retreat rule moved from step 7 to step 6, i.e. **above** "attack anyway with
    the strongest available attack", and its gate changed from
    `active.hp <= 30% maxHp and any bench.hp > active.hp` (HP-based) to
    `any(_best_usable_damage(b) > _best_usable_damage(active))` (damage-based).
    Lethal attack remains step 1, so lethal still preempts retreat.
  - **Reasoning / mechanism found.** First hypothesis logged in discussion — "search
    never gets to consider retreat" — was **wrong**, and is corrected here:
    `_search_choose_main` enumerates *every* option index (`for i in
    range(len(sel.option))`), so RETREAT was always a legal top-level search candidate.
    The real blocker was ladder **ordering**: old step 6 returned an attack whenever
    any attack was legal, so old step 7 (retreat) was unreachable while the Active
    could swing at all. Because `_choose_main` is *also* the rollout policy inside
    lookahead (`_greedy_select` at the `search_step` tail), every rollout continuation
    also swung with whatever was Active. That explains why the 08-07 eval-term work
    (Active-quality / KO-risk) could not move the weak-attacker share (40% -> 39.2%):
    the terms were scoring lines the policy could never generate.
  - **Result: no measured gain.** `self_play_benchmark.py 500` vs the frozen
    `previous_agent` = **61.0% [95% CI 56.7-65.2%]** (305/195/0 draws), avg 123.2
    steps. The shipped lookahead config on the identical harness is **64.6%
    [60.3-68.7]**. The CIs overlap across most of their range, so this is a
    **statistical tie with a 3.6pt lower point estimate** — i.e. no evidence of
    improvement, and a hint of regression that is itself not significant.
  - Per the standing rule (do not ship on overlapping CIs; do not act on noise), this
    is **not** treated as an improvement. Left in the tree pending one follow-up
    measurement of the attacker-share metric, because a *moved share with flat win
    rate* would be a genuine finding — it would mean attacker concentration does not
    convert to wins on Hydrapple, and that imitating LiamK's 88.7% figure is chasing
    a metric with no payoff. If the share is unmoved, the change is simply reverted
    as rejected fix #4. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Discussion with Codex and me — clarified what we are actually optimizing**:
  - We clarified that the final Kaggle submission should be treated as a paired
    product: **`main.py + deck.csv`**. The goal is not to build a universally perfect
    Pokemon TCG agent in isolation, and it is not to pick a strong-looking deck in
    isolation. The goal is to submit the strongest measured pairing: an agent that
    pilots the submitted deck as well as possible against other teams' own
    `main.py + deck.csv` combinations.
  - Current stable baseline remains **Hydrapple + lookahead `main.py`**. Hydrapple is
    not assumed to be the final answer forever, but it is the safest current
    submission candidate because it has already been validated under our own agent.
    Copying LiamK's Mega Lopunny / Mega Froslass deck did not create a measurable
    gain under our pilot: LiamK deck vs Hydrapple was a statistical tie. Therefore
    LiamK's leaderboard strength should be read as a **deck + agent execution**
    result, not as proof that the deck alone is superior for us.
  - The useful lesson from LiamK is behavioral, not just deck-list based. Their agent
    appears to spend much more compute, takes more useful actions per turn, attaches
    or accelerates Energy more often, and concentrates attacks through real attackers.
    Our known gap is still that Hydrapple sometimes attacks with weak or support
    Pokemon instead of converting through Teal Mask Ogerpon ex / Hydrapple ex /
    Meganium-style attackers. The next `main.py` work should focus on attacker
    discipline, tempo, attachment/acceleration sequencing, retreat/promotion choices,
    and using more of the available search budget.
  - We also agreed that exploring another strong or anti-meta deck in parallel is
    reasonable. Hydrapple progress should not be halted or discarded, but a challenger
    deck can be developed separately. The rule is: **do not replace Hydrapple unless
    `new deck + adapted main.py` clearly beats `Hydrapple + current/improved main.py`
    under enough games**. Paper strength, type coverage, or leaderboard imitation is
    not enough; the candidate must be strong under our actual agent logic.
  - Working principle going forward:

    ```text
    final strength = deck potential * agent execution
    ```

    A strong deck with mismatched agent logic can underperform, and a good agent with
    a low-ceiling deck is limited. The winning target is the strongest measured pair.
    Immediate priorities are: keep improving Hydrapple execution as the stable path,
    add/track attacker-discipline and tempo metrics, widen/deepen search where useful,
    and test any challenger deck against Hydrapple and LiamK-style baselines before
    considering a switch. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-08-07

- **Behavioral comparison vs the #1 agent — two concrete gaps found**:
  - Replays carry the **full observation**, including `select.option` for every
    decision and `remainingOverageTime`. So the #1 agent's actual *choices* can be
    decoded (map each chosen action index back to its `OptionType`), and its compute
    consumption read directly. Extracted 40 of LiamK's episodes and measured our own
    agent on the identical metrics (40 Hydrapple mirror games).

    | metric | LiamK (#1, 1202) | ours (lookahead) |
    |---|---|---|
    | avg steps / turns per game | 158 / **13.3** | 139 / **16.1** |
    | MAIN decisions per game | **48.5** | 40.8 |
    | PLAY | 36.9% | 42.1% |
    | **ATTACH** | **25.4%** | **13.1%** |
    | ATTACK | 12.6% | 11.6% |
    | ABILITY | 10.9% | 13.4% |
    | END | 8.0% | 9.3% |
    | EVOLVE | 3.8% | 6.6% |
    | RETREAT | 2.4% | 3.9% |
    | **think time per game** | **15.51s** | **~0.5s** |

  - **GAP 1 — compute. They spend ~30x more time per decision than we do.** LiamK
    burns 15.51s of the 600s per-game overage bank; our lookahead uses roughly 0.5s.
    Both are far under the cap (they use 2.6% of it, we use ~0.08%), so **the budget
    is nowhere near binding for either of us** — consistent with the earlier timing
    probe (1.8ms per one-turn rollout, ~2,200 rollouts/decision affordable). Our
    1-ply/one-candidate-per-option search is simply far shallower than theirs. This
    is the clearest headroom we have: deeper or wider search is affordable *today*.
  - **GAP 2 — attacker discipline.** LiamK's attacks are overwhelmingly by their two
    real attackers: **Mega Lopunny ex 55.9% + Mega Froslass ex 32.8% = 88.7%**, with
    only ~11% by utility Pokémon (Fan Rotom, Buneary, Dunsparce). Ours: Teal Mask
    Ogerpon ex 54.7% + Hydrapple ex 11.6% = **66.3%**, leaving **~34% of attacks made
    by weak/support Pokémon** (Celebi, Chikorita, Applin, Bayleef, Regigigas, Dipplin,
    Tapu Bulu). This independently confirms the "attacks with whatever is already
    Active" flaw logged earlier — and quantifies the target: close a ~22pt gap in
    attacker concentration.
  - **Tempo signature:** they take *more* actions per turn (48.5 MAIN decisions over
    13.3 turns) yet finish in **~17% fewer turns** than us (16.1). Their much higher
    ATTACH rate (25.4% vs 13.1%) is the mechanism — they build a board faster and
    convert sooner, rather than spending turns cycling cards. Note only one *manual*
    energy attach is legal per turn, so their surplus ATTACHes come from card/ability
    effects: their Trainer-heavy (36) build is doing real work.
  - Caveats recorded so these are not over-read: LiamK's 60% win rate is **vs the
    live ladder field**, while our 55% is a **mirror self-match** (same agent and deck
    both seats) — those two numbers are *not* comparable and no conclusion is drawn
    from them. Their think time is engine-measured overage; ours is local wall clock —
    different instruments, but the ~30x order-of-magnitude gap is well outside
    measurement error.
  - `.gitignore` — added `liamk_behavior.json` (another team's replay-derived data;
    Competition Data, not redistributable). — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Leaderboard #1 (LiamK) deck extracted and tested — no deck change**:
  - Method (all public, and explicitly sanctioned by the competition Data page, which
    says replays from other teams are downloadable from the Leaderboard): the
    leaderboard replay viewer calls **`GET /competitions/episodes/{id}/replay.json`**,
    which needs no auth, and `POST /api/i/competitions.EpisodeService/ListEpisodes`
    with `{submissionId}` lists a submission's episodes. In a replay, an agent's
    **deck is simply its `steps[1]` action** (the 60 card IDs returned during the
    deck-selection phase), and `info.TeamNames` identifies which seat is whose. Found
    the endpoint by clicking the replay button and reading the network log after
    guessing endpoint names failed.
  - Sampled **60 of LiamK's 241 episodes** (submission 55248965, rating 1202.1).
    **Every game used one identical 60-card list** — no deck variation at all.
    Sample record 42W-18L (70%). Saved as `Decs/LiamK_MegaLopunny.txt` / `.csv`.
  - **The deck is a Mega Lopunny ex / Mega Froslass ex dual-Mega build**: 16 Pokémon
    (4 Dunsparce, 3 Dudunsparce, 2 Buneary, 2 Mega Lopunny ex, 2 Snorunt, 2 Mega
    Froslass ex, 1 Fan Rotom), 36 Trainers (4 each Buddy-Buddy Poffin / Lillie's
    Determination / Poké Pad / Ultra Ball / Wally's Compassion, 3 each Air Balloon /
    Battle Cage / Hand Trimmer / Hilda, 2 each Boss's Orders / Pokégear 3.0), 8 Energy
    (4 Mist, 3 Basic {W}, 1 Enriching). Notably thin on Pokémon and Energy, very
    Trainer-heavy — a consistency-first build.
  - **Independent corroboration of our own measurement:** this is the same archetype as
    our `Decs/Mega_Lopunny_ex`, which our lookahead round-robin had already ranked
    statistically tied for #1 (70.9% vs Hydrapple 71.0%). Two independent methods —
    our simulation and the actual leaderboard — converged on the same archetype.
    Theirs is a refinement of ours: adds the Snorunt/Mega Froslass ex line (+3 Basic
    Water Energy to power it) and 3 Hand Trimmer; cuts Psyduck, Abra, Dudunsparce ex,
    Spiky Energy; trims Boss's Orders 4->2 and Pokégear 4->2.
  - `sample_submission/sample_submission/deck_head2head.py` — new seat-balanced
    two-deck comparison harness (Wilson CI, avg game length, explicit timeout count so
    long games are reported rather than silently dropped).
  - **Decisive test: LiamK's deck vs Hydrapple, piloted by OUR agent = 49.2%
    [43.1-55.4%] over 250 games, 0 timeouts — a TIE. No deck change.** The important
    read is that **their #1 rating is driven by their agent, not by a copyable deck**:
    under our pilot their list is worth nothing extra over what we already run. This
    is more evidence for the deck<->agent coupling already logged — their build almost
    certainly needs sequencing our generic agent does not execute (Mega evolution
    timing, Froslass ability use, Hand Trimmer loops).
  - `.gitignore` — added `liamk_decks.json` and `.playwright-mcp/`. Another team's
    downloaded replay data is Competition Data and must not be redistributed. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Round-robin re-run WITH lookahead; submission deck re-validated (kept)**:
  - `sample_submission/sample_submission/round_robin.py` — **fixed a result-invalidating
    bug found before launching.** The harness passed each deck to the *engine*, but the
    lookahead builds its hidden-info predictions from `_MY_DECK`, which defaults to the
    submission `deck.csv`. So every seat would have predicted **Hydrapple's** cards while
    piloting a different list — systematically biasing the comparison toward the exact
    deck under test. Added `seat_agent(deck_ids)` to bind the right deck per seat. Also
    hit a Python shadowing trap: the module-level `def main():` rebound the name over
    `import main`, so `main._MY_DECK = ...` would have set an attribute on the *function*
    and then crashed on `main.agent`; renamed to `import main as agent_mod`. Added an
    optional output-filename argument.
  - **Deck ranking with lookahead** (50 games/ordered pair, 3,200 games, seat-averaged),
    vs the earlier greedy-pilot ranking:

    | Deck | greedy | lookahead | delta |
    |---|---|---|---|
    | Hydrapple | 74.7% | 71.0% | -3.7 |
    | Mega_Lopunny_ex | 64.3% | **70.9%** | **+6.6** |
    | Marnie's_Grimmsnarl_ex | 57.0% | 61.0% | +4.0 |
    | Team_Rockets_Honchkrow | 48.7% | 51.6% | +2.9 |
    | Mega_Kangaskhan_ex | 42.9% | 46.4% | +3.5 |
    | Mega_Absol_ex | 40.0% | 42.4% | +2.4 |
    | Mega_Latias | 49.4% | **41.0%** | **-8.4** |
    | Hide_n_Sneak | 23.0% | 15.7% | -7.3 |

  - Finding: **the pilot changes the deck landscape.** Mega_Lopunny_ex gained most from
    lookahead (+6.6) and Mega_Latias lost most (-8.4), collapsing the previously clear
    Hydrapple lead into a dead heat (71.0 vs 70.9 — noise at n=50/cell).
  - **Decisive head-to-head to settle the submission deck:** Hydrapple vs
    Mega_Lopunny_ex, 500 seat-balanced games = **47.4% [95% CI 43.1-51.8%]** — CI spans
    50%, i.e. a statistical **tie** (Hydrapple 50.0% as P0, 44.8% as P1).
  - **Decision: keep Hydrapple as the submission deck.** There is no significant
    advantage either way, so switching would be chasing noise — the same mistake the
    earlier 100-game 60/40 result caused. Documented rather than churned. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Lookahead SHIPPED ON: +15.6pts, with a corrected attribution**:
  - `sample_submission/sample_submission/main.py` — extended `_eval_state` (v2) with
    `_can_pay` (typed/Colorless attack-cost check, RAINBOW as wild),
    `_best_usable_damage` (highest damage a Pokémon can actually afford right now),
    and `_prize_value`; the eval now adds an **Active-attacker quality** term
    (`best_usable_damage*2 + energies*5`) and an **opponent-KO-back risk** penalty
    (`-300 * prize_value` if their Active can KO mine next turn). Set
    `SEARCH_MAIN = True`.
  - `sample_submission/sample_submission/eval_ablation.py` — new harness that
    monkeypatches `_eval_state` variants (full / no_ko / no_quality / base-v1) and
    runs each against the frozen `previous_agent`, so gains are attributed to a
    specific term instead of a bundle (a repeat criticism of earlier passes).
  - **Headline result — lookahead is a large, real win.** Same Hydrapple deck on
    both seats, vs frozen greedy: **control greedy-without-lookahead 49.0%
    [43.4-54.6] (n=300)** vs **lookahead 64.6% [60.3-68.7] (n=500)** — **+15.6pts**,
    CIs cleanly separated. Average game length also fell 131.9 -> 121.6 steps
    (faster, more decisive wins). `benchmark.py 200` = 192/200 (96.0%) vs random.
  - **Correction to the 2026-07-20 diagnosis.** That entry concluded 1-ply lookahead
    failed (45%) because "the eval is myopic". That was **wrong**. The ablation shows
    the *unchanged v1 naive eval* now scores **61.5% [54.6-68.0]** — the only thing
    that changed in between is the submission deck (auto-built Water -> Hydrapple).
    Lookahead's value is **deck-dependent**: it exploits Hydrapple's ability-driven
    energy engine and had little to work with in the clunky Water list.
  - **My v2 eval terms are within noise.** Ablation (n=200 each): full 63.5%
    [56.6-69.9], no_ko 64.0% [57.1-70.3], no_quality 56.0% [49.1-62.7], base-v1
    61.5% [54.6-68.0] — all CIs overlap, and dropping the KO-back term changes
    nothing (64.0 vs 63.5). The shipped config is the full eval because it carries
    the largest sample (n=500), but the KO-risk term is **unproven complexity on
    probation**, not a demonstrated improvement.
  - The Active-quality term also failed at its stated purpose: the weak-attacker
    share (Applin/Chikorita/Bayleef/Dipplin/Celebi/Regigigas/Tapu Bulu) is
    **39.2%** of attacks, essentially unchanged from the ~40% baseline. Attack
    composition did concentrate on the main attacker though (Teal Mask Ogerpon ex
    28.8% -> 43.6% of attacks) and total attacks per 40 games fell 785 -> 574, i.e.
    fewer, more decisive swings. Net: the win comes from lookahead selecting better
    *lines*, not from the specific eval terms designed for attacker choice. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Hydrapple deck-execution audit (verification of the deck swap)**:
  - Independently verified Codex's deck swap: `deck.csv` is byte-identical to
    `Decs/Hydrapple.csv` (60 lines) and `benchmark.py 60` reproduced 57/60 = 95.0%
    vs random. Swap confirmed correct and kept.
  - Ran `watch_game.py` on the new deck to check whether the agent actually executes
    Hydrapple's game plan (the Deck-Score question: are key cards *utilized*, not
    just present). **First single game was misleading** — it showed zero Hydrapple ex
    deployment and 13/13 attacks by Teal Mask Ogerpon ex, suggesting the deck's
    namesake line was dead weight. A 40-game instrumented re-run **corrected that**:
    Hydrapple ex evolves 89 times (~2.2/game) and attacks 85 times, so the engine
    does work. Noting the correction explicitly because the n=1 conclusion was wrong
    and nearly drove a deck rebuild.
  - **Real finding from the 40-game attacker distribution** (total attacks by card):
    Teal Mask Ogerpon ex 226, Meganium 85, Hydrapple ex 85, Celebi 84, **Applin 80**,
    Fezandipiti ex 53, Regigigas 48, **Chikorita 42, Bayleef 33, Dipplin 26**, Tapu
    Bulu 13, Meowth ex 10. Roughly **40% of attacks come from weak basics/unevolved
    intermediates** (Applin 40HP, Chikorita, Bayleef, Dipplin) rather than the deck's
    real attackers. The agent attacks with whatever is already Active instead of
    promoting the right attacker — the known tempo/misallocation flaw in a new form,
    consistent with the deliberately conservative retreat rule (only retreat at
    <=30% HP). Confirms the Ogerpon energy engine IS used (Teal Dance ability fires
    for energy accel + draw), so the deck/agent pairing is sound; the gap is
    attacker selection, not deck construction. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

## 2026-08-04

- **Submission deck swapped to Hydrapple**:
  - `sample_submission/sample_submission/deck.csv` — replaced the auto-built Water
    Stage-2 deck with the measured Hydrapple deck from `Decs/Hydrapple.csv`.
    Reasoning: the full 8-deck round robin already showed Hydrapple as the strongest
    deck under the current generic heuristic pilot (74.7% mean seat-neutral win rate
    vs the field), so leaving the weaker Water deck as the actual submission deck was
    unused measured value. This is the lowest-risk, highest-ROI deck-score/model-score
    improvement before further agent work.
  - `PLAN.html` — updated the completion board to mark Hydrapple as the active
    submission deck, reject the auto-built Water list for final submission, and mark
    deck-vs-deck measurement as done via the round-robin harness. Reasoning: the plan
    should reflect the current decision frontier: deck selection is now measured and
    cashed in; the remaining high-ceiling work is agent eval/lookahead.
  - Verified live: `Decs/Hydrapple.csv` and the copied submission `deck.csv` are both
    60 lines; `python -m py_compile` passed for runtime Python files; `python
    benchmark.py 200` with Hydrapple finished 190/200 wins (95.0%) against random;
    `python run_local.py` completed one local match and wrote `result.txt`. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Hackathon completion board**:
  - `PLAN.html` — added a static browser-openable planning board with tracks for
    submission correctness, measurement, agent strategy, deck strategy, report
    evidence, and final polish. Reasoning: the project now needs a controlled
    finish path rather than reactive heuristic tuning; an HTML board is easier to
    scan during the remaining hackathon days than a long markdown checklist.
  - The plan records current measured state (self-play neutrality over 500 games,
    random-smoke strength, and remaining tempo/stall debt), explicitly keeps the
    rejected one-rule tempo fixes rejected, and separates agent-quality work from
    deck-quality measurement so future changes are not mixed together. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-07-20

- **MAIN-phase 1-ply lookahead (built, measured, shipped OFF)**:
  - `sample_submission/sample_submission/main.py` — added a 1-ply lookahead for MAIN
    decisions behind a `SEARCH_MAIN` flag. Refactored the greedy dispatch into
    `_greedy_select(obs)` (reused as both the default policy and the rollout policy).
    New pieces: `_eval_state` (prizes×1000 + board-HP diff + Active energy, from a
    fixed my-index perspective, terminal win/loss = ±1e9), `_predictions` (mirror
    hidden-info fill for `search_begin`), `_rollout_score` (fork via `search_begin`,
    apply a candidate first action, greedily play out the rest of my turn via
    `search_step`, eval the end-of-turn board), and `_search_choose_main` (score
    every MAIN option's greedy continuation, pick the best; return None → greedy
    fallback on any failure).
  - **Measured WORSE than greedy and shipped OFF.** Verified search actually engages
    (33/33 P0 MAIN decisions, 0 errors — not a silent fallback). `self_play_benchmark
    200` (current lookahead vs frozen 07-18 greedy) = **45.0% [95% CI 38.3-51.9%]**,
    vs ~49% for greedy-without-lookahead — i.e. ~4pts worse, at the edge of
    significance. Set `SEARCH_MAIN = False` so the stronger greedy policy ships; all
    lookahead code kept behind the flag for iteration.
  - Diagnosis of why 1-ply didn't pay off: (1) the greedy rollout tail masks the
    first action — most candidates converge to similar end boards, so search
    differentiates on HP/energy noise and loses to greedy's clean lethal-first
    priority; (2) the eval is myopic (end-of-MY-turn only, ignores the opponent's
    KO-back on their turn — greedy's tuned retreat/priority implicitly handles some
    of that); (3) mirror-fill pollutes rollouts — draw/search cards in the sandbox
    pull from the predicted deck, not real draw order. Next-iteration levers:
    richer eval (opponent lethal-next-turn / Active survivability / prize race),
    or restrict search to specific decisions (attack timing) instead of all MAIN
    options. Paused for design discussion before iterating. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Search-API timing probe (lookahead feasibility)**:
  - `sample_submission/sample_submission/time_probe.py` — at 25 real MAIN decision
    points in a live game, times the cabt search API (`search_begin` /
    `search_step` / `search_end`) to size a future lookahead. Builds the hidden-info
    args `search_begin` requires (my deck/prize, opponent deck/prize/hand at exact
    counts; identities are valid-but-arbitrary for a pure speed test), rolls forward
    one turn, and reports rollouts-per-budget. Also read the env budget from
    `cabt.json`: `actTimeout=0`, `runTimeout=2000`, `remainingOverageTime=600` (a
    ~600s per-game bank).
  - **Results (Hydrapple mirror, 25 points, 0 failures):** `search_begin` median
    0.26ms, `search_step` median 0.17ms, one full one-turn rollout (begin + ~8
    steps) median **1.8ms** (max 3.9ms). A ~150-decision game averages ~4000ms per
    decision, i.e. **~2,200 rollouts/decision** available; even a conservative 200ms
    gives ~110.
  - **Conclusion: time does not constrain the lookahead design.** 1-ply search over
    a handful of candidate lines is trivially affordable; multi-ply / hundreds of
    rollouts also fit. The real constraints are (1) state-eval quality — with speed
    free, lookahead quality rides entirely on the board-scoring function — and (2)
    hidden-info prediction: the probe fed *true* decks, but a real agent must guess
    the opponent's deck/hand, which affects rollout realism (decision quality), not
    speed. Next: discuss eval design + opponent modeling before building 1-ply. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Full 8-deck round-robin (seat-bias-cancelled deck ranking)**:
  - `sample_submission/sample_submission/round_robin.py` — plays every ordered deck
    pair (A as P0 vs B as P1) for 50 games, heuristic agent both seats (3,200 games
    total), then seat-averages each pairing —
    `winrate(A vs B) = mean(P0win(A,B), 1 - P0win(B,A))` — to cancel the engine's
    first/second-seat bias. Writes `round_robin_results.md` (ranking + seat-averaged
    matrix + raw matrix + mirror seat-bias check).
  - **Deck strength ranking (mean seat-neutral win% vs field):**
    1. Hydrapple — 74.7%  2. Mega_Lopunny_ex — 64.3%  3. Marnie's_Grimmsnarl_ex —
    57.0%  4. Mega_Latias — 49.4%  5. Team_Rockets_Honchkrow — 48.7%
    6. Mega_Kangaskhan_ex — 42.9%  7. Mega_Absol_ex — 40.0%  8. Hide_n_Sneak — 23.0%.
  - Findings: **Hydrapple is dominant** (beats every deck 52-96%, only near-even vs
    Mega_Lopunny), **Hide_n_Sneak is clear last** (loses to all, 4% vs Hydrapple).
    The mirror seat-bias check varied by deck (raw P0% 42-60%), so seat advantage is
    noisier/less uniform than the single ~58/42 inferred from the earlier
    Hide_n_Sneak-only run; the seat-averaging cancels it either way. Caveat: this is
    deck power **under the generic heuristic pilot** — decks whose plan survives naive
    play (Hydrapple's Ogerpon energy accel) are favored over combo-reliant decks
    (Hide_n_Sneak). Actionable: with the current agent, **Hydrapple is the strongest
    deck to submit**, clearly better than the auto-built Water `deck.csv`. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Competitive deck ingestion pipeline + first cross-deck matchup results**:
  - `scripts/check_decks.py` — cross-references every `Decs/*.txt` deck list against
    the dataset by normalized name (apostrophe-safe, basic-energy aliasing), reports
    per-card Card ID matches and buildability. Fixed a real dataset typo it surfaced:
    card id 19 was `Telepath Psychic Energy` -> corrected to `Telepathic Psychic
    Energy` in `dataset/EN_Card_Data.csv`, which unblocked Hide_n_Sneak. `Special Red
    Card` (not in pool) was swapped to `Judge` (id 1213) in the two decks that needed
    it. End state: **all 8 decks build legally (60/60)**.
  - `scripts/annotate_decks.py` — rewrites each `Decs/*.txt` card line to
    `<count> <Card Name> - <Card ID>` using the same matcher; 0 unmatched across all
    decks. Section headers were also flipped to `<N> - <Section>` form per request.
  - Converted every annotated `Decs/*.txt` into a 60-line Card-ID `Decs/*.csv`
    (count-expanded, one ID per line) — drop-in decks for the engine/visualizer.
  - `sample_submission/sample_submission/decks_matchup.py` — runs P0 fixed =
    Hide_n_Sneak vs each of the 8 decks as P1, heuristic agent on both seats, 100
    games each, recording win/loss/draw + avg steps.
  - **Results (P0 = Hide_n_Sneak, heuristic mirror, 100 games each):**

    | P1 opponent | P0 win% | avg steps |
    |---|---|---|
    | Hide_n_Sneak (mirror) | 42.0% | 129.5 |
    | Team_Rockets_Honchkrow | 29.0% | 127.2 |
    | Mega_Absol_ex | 26.0% | 131.3 |
    | Marnie's_Grimmsnarl_ex | 23.0% | 141.3 |
    | Mega_Latias | 22.0% | 125.8 |
    | Mega_Lopunny_ex | 17.0% | 120.6 |
    | Mega_Kangaskhan_ex | 12.0% | 125.2 |
    | Hydrapple | 5.0% | 108.0 |

    Observations: (1) the mirror is **42% for P0**, i.e. a ~58/42 **seat bias
    favoring P1** (second seat) with identical decks — all P0 win rates here are
    depressed ~8pts by that, so read them relatively, not absolutely. (2) Even
    adjusting for seat, **Hide_n_Sneak underperforms every opponent** — worst vs
    Hydrapple (5%) and Mega_Kangaskhan_ex (12%). (3) These are *deck* strength
    signals under a *fixed* agent — the first real measurement of deck quality
    (previously impossible: self-play mirrored the same deck on both sides). The
    agent plays all decks with the same generic heuristic, so weak results partly
    reflect the heuristic not piloting these archetypes' combos, not only raw deck
    power. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Deck availability check + official visual replay renderer**:
  - `scripts/check_decks.py` — parses the user-authored deck lists in `Decs/`
    (standard PTCG export format: `count Name SET Collector`) and cross-references
    every card against `dataset/EN_Card_Data.csv` by normalized name, reporting per
    card whether it exists in the competition pool (with the matched Card ID / set)
    and whether a legal 60-ID cabt deck is buildable. Handles two matching
    footguns found live: (1) basic energies are named `Basic {W} Energy` in the
    dataset but `Water Energy` in the deck lists — added an element alias map; (2)
    the accent-strip step was deleting curly apostrophes (`’`) before they could be
    unified with straight ones, desyncing names like `Boss's Orders` — fixed by
    unifying/removing apostrophes before the ASCII strip.
  - Result: **5 of 8 decks are fully buildable** in the competition pool —
    Marnie's_Grimmsnarl_ex, Mega_Absol_ex, Mega_Kangaskhan_ex, Mega_Lopunny_ex,
    Team_Rockets_Honchkrow. **3 are not** — Chien-Pao_ex (17 cards absent, incl.
    Chien-Pao ex itself), Great_Tusk (14 absent), Hide_n_Sneak (only 3 absent:
    Gwynn, Prism Tower, Telepathic Psychic Energy). Finding: the competition pool
    is a **curated subset** missing many standard-format staples (Nest Ball, Super
    Rod, Counter Catcher, standalone Iono, Artazon, Radiant Greninja, Professor
    Sada's Vitality); it skews toward the newest sets (MEG/DRI/ASC/POR), which is
    why the buildable decks all lean on those.
  - `sample_submission/sample_submission/render_replay.py` — renders a watchable
    interactive HTML replay of one battle using the **official Kaggle visualizer**
    (`env.render(mode="html")`). Unblocked the `kaggle-environments` install that
    failed earlier (it pulls `litellm` → needs Rust) by installing with
    `pip install --no-deps kaggle-environments`; the `cabt` environment (v1.32.2)
    ships its own engine binaries + a Vite-built visualizer, and the core deps
    (numpy/jsonschema/requests) were already present. Script runs any two agents
    (`--p0/--p1 heuristic|random`) with optional custom decks (`--deck0/--deck1`)
    and writes `replay.html` (a self-contained interactive player — step/scrub
    through the match visually), `--open` launches the browser.
  - Note for runners: `render_replay.py` needs the WindowsApps Python 3.11 (the
    same interpreter that already runs the `cg` scripts), invoked as `python3`
    here — `kaggle-environments` is installed there, not in every Python on PATH.
  - Verified live: `python scripts/check_decks.py` produced the 5/8-buildable
    report above; `python3 render_replay.py --p1 random` ran a full game
    (heuristic P0 beat random P1 in 97 steps) and wrote a 2.8 MB `replay.html`
    confirmed to contain the interactive renderer/player. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

---

## 2026-07-19

- **Higher-confidence benchmarking + tempo diagnostics**:
  - `sample_submission/sample_submission/self_play_benchmark.py` — changed the
    default run size from 100 to 500 games and added a Wilson 95% confidence
    interval to the current-vs-previous win-rate report. Reasoning: the earlier
    60/40 over 100 games was too weak to treat as conclusive; self-play is the
    right yardstick, but it needs enough samples and uncertainty reporting to be
    useful.
  - `sample_submission/sample_submission/tempo_diagnostics.py` — added a local
    diagnostic harness that runs heuristic-vs-random games and counts MAIN states,
    attack availability, attack selections, no-attack states, PLAY availability,
    PLAY selections, END selections, and big-hand END selections. Reasoning: the
    watched-game evidence showed tempo/stall behavior, but future fixes need
    counters that quantify the symptom instead of relying only on hand-read replay
    transcripts.
  - Re-tested the prior live-targeting/evolve-unification policy with the stronger
    self-play harness. Result: `python self_play_benchmark.py 500` ended current
    246 / previous 254 / draw 0, current win rate 49.2% with 95% CI 44.8%-53.6%,
    average 131.9 steps. Reasoning: the old 100-game 60/40 result was noise; this
    policy should be treated as neutral against the frozen previous baseline, not as
    a proven improvement.
  - Tried two tempo fixes and rejected both after measurement: (1) playing useful
    Trainers only when no attack was available regressed to current 238 / previous
    262 over 500 games; (2) retreating to a Benched Pokémon that already had enough
    Energy to attack regressed to current 227 / previous 273 over 500 games. Neither
    policy change was kept. Reasoning: reducing visible stall counters is not enough
    if self-play gets worse; the benchmark is now doing its job by blocking fragile
    heuristic changes.
  - Final retained diagnostics: `python tempo_diagnostics.py 100` finished P0 97 /
    P1 3 / draw 0, with 4,085 MAIN states, 2,317 attack-available states, 1,768
    no-attack states, 836 MAIN END selections, and 363 big-hand END selections.
    Reasoning: tempo/stall remains real and measurable, but the safe next fix likely
    needs deeper Energy/Trainer sequencing or search-based lookahead rather than a
    one-rule patch.
  - Verified live: `python -m py_compile` passed for all changed Python files;
    `python benchmark.py 200` finished 195/200 wins (97.5%) against random;
    `python run_local.py` completed one match and wrote `result.txt`; `python
    scripts/build_deck.py` regenerated the same legal 60-card deck. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-07-19

- **Step-by-step battle watcher + first behavioral observations**:
  - `sample_submission/sample_submission/watch_game.py` — human-readable
    turn-by-turn replay of one match. Prints a per-turn board summary (both
    players' Active HP/energy, Bench, hand size, prizes left), each decision the
    acting agent makes decoded to English (`ATTACH`, `PLAY`, `EVOLVE`,
    `ATTACK 'Aqua Launcher' (210 dmg)`, `RETREAT`, `END`), and the resulting game
    events decoded from the observation `logs` (draws, plays, attaches,
    evolutions, attacks, HP changes, special conditions, coin flips, KO/win).
    Skips noise events (shuffles, face-down moves, turn-start/end markers). Runs
    `python watch_game.py` (heuristic mirror) or `python watch_game.py random`
    (heuristic P0 vs random P1); redirect to a file for a full transcript.
    Reasoning: `visualize_data()`/`result.txt` is a 1.6 MB per-step JSON dump, not
    something a human can read — the watcher is the tool for actually seeing *why*
    the agent wins or loses, which the benchmarks (win/loss tallies only) cannot
    show. Includes UTF-8 console reconfigure (Windows cp1252 was mojibaking card
    names) and slot-index fallback display for options whose `cardId` is None.
  - **Observations from the first watched games** (heuristic vs random) — logged
    as future Strategy-writeup evidence, not yet acted on:
    - The agent **hoards cards**: reached 15-16 cards in hand by ~turn 45 while
      repeatedly playing `END turn` with a full bench. The greedy ladder only
      attacks when the Active already has enough Energy, so a poorly-energized
      Active just passes the turn — lots of dead turns, games dragging to 45+
      turns. Against a real opponent that tempo loss likely costs games.
    - The **secondary line carried the win**, not the primary: Clawitzer's
      Aqua Launcher (210 dmg) one-shot a 180-HP Mamoswine for the last prize,
      while the "primary" Swinub->Piloswine->Mamoswine line mostly sat on the
      bench. Suggests the deck's line priority (4/3/2 primary vs 3/3 secondary)
      may be backwards for how the agent actually plays.
    - Net: two concrete heuristic weaknesses to target next — (1) press damage /
      attack more aggressively instead of stalling, (2) energy routing that
      actually powers an attacker toward a usable attack. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Delta-sensitive benchmark + live target selection pass**:
  - `sample_submission/sample_submission/previous_agent.py` — added a frozen copy
    of the 2026-07-18 heuristic policy. Reasoning: once the agent already beats
    random play almost every game, future tuning needs a stable previous-policy
    opponent so regressions are visible instead of hidden behind a saturated random
    benchmark.
  - `sample_submission/sample_submission/self_play_benchmark.py` — added current
    `main.agent` vs frozen `previous_agent.agent` self-play with mirrored decks,
    alternating first player, win/loss/draw tallies, and average step count.
    Reasoning: this is now the primary yardstick for heuristic deltas; the random
    benchmark remains useful as a crash/legality smoke test, not as the main quality
    metric.
  - `sample_submission/sample_submission/main.py` — added live-board target lookup
    for Active/Bench options and damage-target scoring that consults current
    `Pokemon.hp`/`maxHp`, damage taken, Active-vs-Bench location, and rule-box Prize
    value. Damage-counter contexts use the known remaining counter budget to prefer
    lethal targets; direct-damage contexts only override static threat for truly
    near-dead targets (<=10 HP). Reasoning: the previous CARD ranking used static
    `CardData` only, so it could not tell a full-HP Pokémon from a 10-HP Pokémon and
    missed obvious prize-finishing choices. A broader first pass regressed self-play,
    so the final rule is intentionally conservative.
  - `sample_submission/sample_submission/main.py` — unified standalone
    `SelectType.EVOLVE` ranking with MAIN-phase evolution by using `_best_card_option`
    instead of a separate HP-only implementation. Reasoning: evolution choices should
    not drift between selection contexts.
  - `scripts/build_deck.py` — changed the stale `NOTES.md` reference to
    `PROGRESS.md` and removed unused `cost_len`, `trainer_cards`, `by_name`, and
    `used_ids` code. Reasoning: these were cleanup items from review; removing them
    lowers maintenance noise without changing deck strategy.
  - Verified live: `python -m py_compile` passed for all changed Python files;
    `python self_play_benchmark.py 100` finished current 60 / previous 40 / draw 0
    with 128.7 average steps; `python benchmark.py 100` finished 98/100 wins
    (98.0%) against random; `python run_local.py` completed one match and wrote
    `result.txt`; `python scripts/build_deck.py` regenerated the 60-card deck; `rg`
    confirmed no remaining `NOTES.md`, `cost_len`, `trainer_cards`, `by_name`, or
    `used_ids` references in the cleaned files. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-07-18

- **Code-quality follow-up on the heuristic baseline**:
  - `sample_submission/sample_submission/main.py` — made `read_deck_csv()` resolve
    `deck.csv` relative to the submitted agent file first, with the Kaggle path as
    fallback and an explicit 60-card length check. Reasoning: local tools should not
    depend on whichever directory launched Python, while submission behavior stays
    compatible with Kaggle's `/kaggle_simulations/agent/` layout.
  - `sample_submission/sample_submission/main.py` — upgraded MAIN-phase ranking
    without changing the greedy baseline shape: lethal attack still comes first,
    evolution now chooses the strongest resulting card instead of option order,
    Energy attachment prefers the Active target and then stronger Bench targets,
    and Basic bench development chooses the strongest Basic available. Reasoning:
    the previous implementation was legal but over-dependent on simulator option
    ordering; the new ranking improves code quality while preserving the proven
    attack-first baseline. A first attempt also ranked all playable Trainers, but a
    20-game smoke benchmark dropped to 80%, so MAIN `PLAY` was intentionally narrowed
    back to Basic board development.
  - `sample_submission/sample_submission/main.py` — made CARD selection more
    context-aware: discard/return contexts prefer low-value cards, opponent damage
    target contexts prefer opponent options when available, and all card ranking now
    uses HP plus best printed attack damage instead of HP alone. Reasoning: one HP
    sort across every selection context was too blunt and could choose poor targets
    even though selections remained legal.
  - `scripts/build_deck.py` — replaced the unused placeholder trainer scorer with a
    deterministic score based on search/draw/evolution/Basic-Pokémon utility,
    explicit boosts for Rare Candy, Ultra Ball, and Buddy-Buddy Poffin, filters for
    dead Tera/Mega/Team-Rocket-specific search targets, and an 8-card Supporter cap.
    Reasoning: the earlier keyword filter produced a legal deck but could fill slots
    from CSV order rather than actual usefulness for this Water Stage-2 list.
  - `sample_submission/sample_submission/run_local.py` and
    `sample_submission/sample_submission/benchmark.py` — wrapped active battles in
    `try/finally` so `battle_finish()` runs even if an agent or simulator selection
    raises. Reasoning: the native simulator should be released reliably during local
    iteration and benchmarking.
  - Verified live: `python -m py_compile` for all changed Python files passed;
    `python scripts/build_deck.py` regenerated a 60-card deck; `python run_local.py`
    completed one local match and wrote `result.txt`; `python benchmark.py 100`
    finished at 99/100 wins (99.0%) against random, matching the prior baseline
    after the MAIN-phase Trainer-play regression was corrected. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-07-14

- **Heuristic-vs-random benchmark harness**:
  - `sample_submission/sample_submission/benchmark.py` — plays N games between
    `main.agent` (heuristic) and a local `random_agent`, alternating which one is
    player0 each game to cancel out first-move advantage, tallies win/loss/draw.
  - Verified live: 100 games, heuristic won 99/100 (99.0% win rate) against random
    play. This is the baseline number future changes (search/lookahead, ML) get
    measured against. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Synergistic 60-card deck built from card data**:
  - `scripts/build_deck.py` — parses `dataset/EN_Card_Data.csv` (2022 rows, 1267
    unique cards after grouping the multi-row-per-move schema), finds all
    Basic→Stage1→Stage2 evolution chains of a chosen type (Water), filters out
    rule-box (`ex`) Pokémon to avoid conceding extra Prize cards, scores chains by
    `top_attack_damage*2 + HP`, and assembles a full 60-card deck: primary line
    Swinub→Piloswine→Mamoswine (200 dmg finisher), secondary line
    Clauncher→Clawitzer (210 dmg, cheap), plus lone Basics Kyogre/Glastrier (20
    Pokémon total), 14 Basic Water Energy, 26 Trainers auto-selected by
    draw/search/heal keyword match in effect text (Rare Candy, Love Ball, Boxed
    Order, Buddy-Buddy Poffin, etc.), respecting the 1-copy ACE SPEC cap.
  - Bug caught and fixed same-session: the secondary-line search initially let
    `Palafin ex` (rule-box) through because the `rule == "n/a"` filter was only
    applied to the Stage-2 candidate, not Stage-1. Added the missing check so both
    stages of every chain are enforced non-`ex`.
  - Verified all seven chosen Pokémon's attack costs are pure `{W}`/Colorless —
    no off-type energy dependency introduced by the single-type Energy count.
  - Output written to `sample_submission/sample_submission/deck.csv` (60 lines,
    replaces the original sample deck). — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Heuristic (rule-based, no ML) battle agent**:
  - `sample_submission/sample_submission/main.py` — replaced the starter's
    `random.sample(...)` agent with a greedy priority-ladder decision function.
    Caches `all_card_data()`/`all_attack()` lookups once, then dispatches on
    `obs.select.type`/`context`:
    - **MAIN** phase: attack-for-lethal → evolve → attach Energy (once/turn) →
      play Basics to Bench → use Ability → attack anyway (best damage) → retreat
      only if Active is low-HP and a stronger Benched Pokémon exists → end turn.
    - **ATTACK**: highest-damage usable attack.
    - **EVOLVE** / **CARD**: highest-HP preference (lowest-HP first when the
      context is a discard/return-to-deck selection).
    - **YES_NO**: defaults to the beneficial-sounding option.
    - **COUNT**: picks the option with the largest offered number.
    - Unhandled select types (ENERGY, SKILL, SPECIAL_CONDITION, future additions)
      fall back to a minimal safe default instead of crashing.
  - `_clamp()` — enforces `minCount <= len(selection) <= maxCount`, de-dupes, and
    drops out-of-range indices on every return path, so a heuristic mistake can
    never produce an engine-rejected selection.
  - Added `assert sel is not None` / `assert state is not None` guards in each
    helper to fix a batch of Pyright null-safety false-positives (the functions
    are only ever called after the caller already confirmed non-None, but the
    type checker can't see that across the call boundary) and dropped an unused
    `EnergyType` import.
  - Verified live via `run_local.py`: 5 consecutive games, no crashes/exceptions,
    games completing in 14–61 steps (down from the random agent's 99). — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Local test harness (bypassing `kaggle-environments`)**:
  - `sample_submission/sample_submission/run_local.py` — drives
    `cg.game.battle_start` / `battle_select` / `battle_finish` directly to run one
    full match between two agent functions and dump `result.txt` via
    `visualize_data()`. Built after `pip install kaggle-environments` failed (pulls
    in `litellm`, which needs a Rust/Cargo toolchain not present locally) —
    reading `cg/game.py` showed the battle-loop primitives are sufficient on their
    own, so the official runner isn't actually required for local iteration.
  - Verified live: ran the (then still random) starter agent vs itself, game
    completed in 99 steps, `result.txt` produced. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Rulebook and competition-rules reference docs**:
  - `POKEMON_RULES.md` — full 41-page official TCG rulebook (`par_rulebook_en.pdf`)
    condensed to markdown: win conditions, turn structure, evolution rules, full
    damage-calculation order (base → attacker boosts → Weakness → Resistance →
    defender reductions → counters), all 5 Special Conditions with stacking
    behavior, deck-building limits, a rule-box Prize-penalty table (ex/GX/V/VMAX/
    TAG TEAM/etc.), retreat rules, glossary, and a merged section on the cabt
    simulator's documented deviations from official rules (sim behavior is ground
    truth for this competition per host discussion #708586).
  - `EVALUATION.md` — full competition rules/evaluation reference covering both
    linked Kaggle competitions (Simulation `pokemon-tcg-ai-battle` and Strategy/
    Hackathon `pokemon-tcg-ai-battle-challenge-strategy`, which requires
    Simulation entry first under the same team): skill-rating (Gaussian μ/σ)
    ladder mechanics, the Strategy judging rubric (Model 70% / Deck 20% / Report
    10%), team/submission limits (max team size 5, Strategy = 1 submission
    total), IP/data restrictions (competition data + models trained on it are
    scoped to the competition only, must be deleted afterward, can't be
    commercialized), eligibility thresholds, disqualification conditions, and a
    practical-implications checklist for the build (dev-log as you go, test for
    generalization not just win rate, etc.). — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

---

## Next up
- Log this session's design/testing notes as they compound (dev log doubles as
  future Strategy-writeup source material).
- Consider search-based lookahead (`search_begin`/`search_step`) for the
  MAIN-phase attack-timing decision, instead of pure greedy same-turn scoring.
- Re-run the 100-game benchmark after any heuristic change to track whether win
  rate actually improves.
