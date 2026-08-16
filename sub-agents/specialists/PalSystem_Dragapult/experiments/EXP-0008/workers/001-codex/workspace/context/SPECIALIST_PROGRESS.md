# PalSystem_Dragapult Specialist Progress

Append-only experiment log for this private Plan_2 specialist. This directory is
not the active submission.

---

## 2026-08-14

- **Specialist initialized**:
  - Worker provider: `codex`.
  - Source deck: `Decs/PalSystem_Dragapult.csv`.
  - Agent baseline: `sample_submission/sample_submission/main.py`.
  - Static deck and Python-interface validation passed.
  - Runtime import and gameplay benchmarks remain pending in an environment with
    the competition `cg` engine.
  - **Reason:** establish an isolated, reproducible deck-agent workspace before
    any automated strategic experiments begin.

## 2026-08-14 — EXP-0001

- **REJECTED: Verify unchanged baseline policy can legally pilot the PalSystem Dragapult deck**
  - Mechanisms: infrastructure_readiness.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 1.
  - Decision reason: Infrastructure-only unchanged candidate; smoke established runtime readiness but contained no strategic implementation to accept.

## 2026-08-15

- **Dedicated specialist preparation and frozen-agent deck baseline**:
  - Corrected the human-readable deck headings to 17 Pokemon and 33 Trainers;
    the machine deck remains the same legal 60-card, 22-ID list with 10 Basic
    Pokemon and one ACE SPEC.
  - Added `STRATEGY.md` and connected it through `config.json`. The notes define
    the Dragapult evolution engine, Fire/Psychic attack preparation, Munkidori
    Darkness routing, live-HP spread targeting, timing-dependent support cards,
    and a six-step one-mechanism experiment backlog.
  - Runtime validation passed. The unchanged 20-game readiness smoke finished
    8-12 with zero draws, timeouts, illegal actions, or crashes. `EXP-0001` was
    rejected because it contained no strategic change.
  - Frozen-agent baseline versus Hydrapple: 191-309 over 500 games (38.2%, 95%
    CI 34.05-42.53%, `p=1.31e-7`), with zero draws or faults. Seat splits were
    101-149 when Dragapult moved first and 90-160 when Hydrapple moved first.
  - Frozen-agent baseline versus No_Name_Grass: 308-192 over 500 games (61.6%,
    95% CI 57.26-65.76%, `p=2.13e-7`), with zero draws or faults. Seat splits
    were 167-83 when Dragapult moved first and 141-109 when Grass moved first.
  - These are deck-plus-generic-policy baselines, not dedicated-agent results.
    They identify Hydrapple as the first difficult matchup and No_Name_Grass as
    the initial regression guard.
  - **Reason:** establish a reproducible specialist workspace, explicit deck
    logic, and statistically powered pre-specialization comparisons before any
    autonomous worker is allowed to tune `main.py`.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Progressive dedicated-agent campaign prepared**:
  - Added a five-hypothesis continuous campaign using `gpt-5.5` Codex workers,
    with independent Opus review supplied by the existing cross-provider gate.
  - Ordered the work by expected decision frequency and attribution clarity:
    Recon Directive before evolution, Crispin/Energy routing, Phantom Dive
    spread targeting, Munkidori damage transfer, then disruption timing.
  - Every item changes one named mechanism and must pass the existing 20-game
    smoke, 200-game screening, independent review, 300-game main test,
    500-game confirmation, cross-deck checks, and final review. Automatic
    acceptance and active-submission promotion remain disabled.
  - **Reason:** let the specialist improve continuously while keeping each gain
    attributable, statistically testable, independently reviewed, and isolated
    from the shared submission until the evidence supports promotion.

  — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-08-14 — EXP-0002

- **REJECTED: During MAIN-phase evolution ordering, when a Drakloak can use Recon Directive and can also evolve into Dragapult ex, use that Drakloak's draw Ability before evolving it; preserve the existing evolve and Ability ordering for every other Pokemon and when Recon Directive is unavailable or already used.**
  - Mechanisms: drakloak_recon_before_evolution.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: human review rejection: automatic opus review rejected candidate; see reviews/screening-opus-auto-review.json

## 2026-08-14 — EXP-0003

- **REJECTED: For Crispin and normal Energy attachment choices in this deck only, prioritize a legal Fire-plus-Psychic route that makes the Active or best prepared Dragapult ex able to use Phantom Dive, while reserving Darkness Energy for Munkidori only when Adrena-Brain has live damage-movement value; preserve generic attachment ranking when no deck-specific route improves attack readiness.**
  - Mechanisms: crispin_dragapult_energy_routing.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: automatic rejection: screening win rate 44.5% is below 45.0%

## 2026-08-14 — EXP-0004

- **REJECTED: Only in Dragapult ex Phantom Dive damage-counter selections, rank opposing Bench targets using live remaining HP, prize value, immediate knockout completion, and useful two-turn knockout setup; preserve all other DAMAGE_COUNTER and CARD target contexts unchanged.**
  - Mechanisms: phantom_dive_live_spread_targeting.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: human review rejection: Rejected after review: screening was exactly 100/200 with p=1.0, and the decision trace did not show representative DAMAGE_COUNTER/Phantom Dive target differences. No evidence of useful gain.

## 2026-08-14 — EXP-0005

- **REJECTED: For Munkidori Adrena-Brain selections only, move damage counters from the most strategically endangered friendly Pokemon to an opposing Pokemon where the moved damage secures a knockout or creates the strongest live-HP prize setup; do not alter generic Ability choice or unrelated damage-counter selection.**
  - Mechanisms: munkidori_adrena_brain_damage_transfer.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: human review rejection: automatic opus review rejected candidate; see reviews/screening-opus-auto-review.json

## 2026-08-15 — EXP-0006

- **REJECTED: For this deck's MAIN-phase Trainer choices only, delay Unfair Stamp, Judge, Boss's Orders, Crushing Hammer, and Jamming Tower unless their current board-state effect is materially useful, while preserving the shipped play ranking for all other Trainers and decks.**
  - Mechanisms: dragapult_disruption_timing.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: human review rejection: Rejected before replay-inspired setup campaign: disruption timing screen was weak (107/200, p=0.322) and AI review requested mechanism-level traces before more evidence. Closing it to unblock the next isolated PalSystem hypothesis.

## 2026-08-15 — EXP-0007

- **REJECTED: Replay-curated PalSystem games show Dreepy is the dominant successful opener and first setup body. For opening Active and initial setup Bench CARD selections only, prefer Dreepy first, then Munkidori/Budew as fallback support, while keeping Fezandipiti ex and Meowth ex off Active unless no better Basic is available; preserve all MAIN-phase play, Energy, Trainer, Ability, attack, evolution, and damage-target logic unchanged.**
  - Mechanisms: dreepy_first_opening_setup_only.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: human review rejection: Rejected after replay-inspired setup screen: candidate went 96/200 (48.0%, p=0.572) and decision trace showed 127 differences all in MAIN/MAIN, not opening/setup CARD contexts. The implementation did not isolate the stated Dreepy-first setup mechanism, so deeper evaluation would not answer the replay hypothesis.
