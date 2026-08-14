# Dark Specialist Progress

Append-only experiment log for this private Plan_2 specialist. This directory is
not the active submission.

---

## 2026-08-12

- **Specialist initialized**:
  - Worker provider: `claude`.
  - Source deck: `No_Name_Decks/No_Name_Dark.csv`.
  - Agent baseline: `sample_submission/sample_submission/main.py`.
  - Static deck and Python-interface validation passed.
  - Runtime import and gameplay benchmarks remain pending in an environment with
    the competition `cg` engine.
  - **Reason:** establish an isolated, reproducible deck-agent workspace before
    any automated strategic experiments begin.

## 2026-08-12 — EXP-0001

- **REJECTED: Unchanged baseline proves Dark specialist runtime readiness**
  - Mechanisms: infrastructure_baseline.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 1.
  - Decision reason: Infrastructure-only unchanged baseline

## 2026-08-13 - specialist paused

- **EXP-0002 paused by human direction.**
  - Reason: Human is not confident in the current No_Name_Dark deck and requested that no further Dark specialist work run until the deck is reconsidered.
  - Existing experiment and human-review evidence were preserved.

## 2026-08-14 — EXP-0002

- **REJECTED: For attack choice and immediate attacker scoring, account for Mega Sharpedo ex Hungry Jaws receiving its conditional damage only when Sharpedo is damaged; preserve generic attack ranking for all other Pokemon.**
  - Mechanisms: sharpedo_conditional_attack_value.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: human review rejection: Rejected after Codex review: Hungry Jaws bonus was implemented as +100 but dataset specifies +150, and screening result was statistically neutral.
