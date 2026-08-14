# Grass Specialist Progress

Append-only experiment log for this private Plan_2 specialist. This directory is
not the active submission.

---

## 2026-08-12

- **Specialist initialized**:
  - Worker provider: `claude`.
  - Source deck: `No_Name_Decks/No_Name_Grass.csv`.
  - Agent baseline: `sample_submission/sample_submission/main.py`.
  - Static deck and Python-interface validation passed.
  - Runtime import and gameplay benchmarks remain pending in an environment with
    the competition `cg` engine.
  - **Reason:** establish an isolated, reproducible deck-agent workspace before
    any automated strategic experiments begin.

## 2026-08-12 — EXP-0001

- **REJECTED: Unchanged baseline proves Grass specialist runtime readiness**
  - Mechanisms: infrastructure_baseline.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 1.
  - Decision reason: Infrastructure-only unchanged baseline

## 2026-08-13 — EXP-0002

- **REJECTED: When evolving the Chikorita line and no Wild Growth Meganium is already in play, prioritize establishing Meganium card 710 before competing Mega Meganium endpoints; preserve evolution ranking after the energy engine exists.**
  - Mechanisms: wild_growth_engine_priority.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: human review rejection: Superseded by human-revised strategy and source deck change from Buddy-Buddy Poffin 1086 to Bug Catching Set 1094; preserve EXP-0002 evidence but do not compare it as the new deck baseline.

## 2026-08-13 - deck rebase

- **Rebased `v000-baseline` to `v001-deck-rebase`.**
  - Deck hash: `7d8e05ad2d423e4562bd0ea48ae1006b27e75359ffbe9554deb46a626a398444` -> `f6cadd59a7e6741e96f18754c0866f87e97ed85f87b3a4486e510f4ea0ae2448`.
  - Source deck: `No_Name_Decks/No_Name_Grass.csv`.
  - Strategy: `No_Name_Decks/No_Name_Grass_Logic.txt`.
  - Reason: Human revised the Grass strategy into legal state-dependent sequencing and replaced two Buddy-Buddy Poffin (1086) with two Bug Catching Set (1094); prior experiments remain historical and cannot serve as the revised deck baseline.

## 2026-08-14 — EXP-0003

- **REJECTED: During opening setup, prefer Mega Kangaskhan ex as Active when Run Errand is usable while preserving Yanma on the Bench so an evolved Yanmega ex can later trigger Buzzing Boost when it moves Active; preserve existing choices outside opening Active/Bench placement.**
  - Mechanisms: kangaskhan_active_yanma_bench_opening.
  - Baseline: `v001-deck-rebase`; candidate: `v002-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: human review rejection: Rejected after human and Codex review: no measured improvement and no setup Active trace evidence proving the mechanism fired.
