# Claude_Grass_Venusaur Specialist Progress

Append-only experiment log for this private Plan_2 specialist. This directory is
not the active submission.

---

## 2026-08-13

- **Private baseline validated and entered in the Phase 5 infrastructure pilot**:
  - Runtime import and static deck/agent validation passed.
  - `EXP-0001` compared the unchanged candidate with its frozen baseline for 20
    smoke games: 13-7, zero draws, timeouts, illegal actions, or crashes.
  - The experiment was rejected because it was an infrastructure validation and
    contained no code or strategic change. The specialist remains
    `v000-baseline` and is now `READY_FOR_EXPERIMENT`.
  - The final seat-balanced central pilot finished 7-13 against Hydrapple over 20
    games. This sample is too small for a strength conclusion and no Claude
    provider was invoked to tune the agent.
  - **Reason:** verify that a second legal private deck-agent pair can pass the
    standard lifecycle and central tournament without treating an unchanged
    baseline or a small pilot as an improvement.

## 2026-08-12

- **Specialist initialized**:
  - Worker provider: `claude`.
  - Source deck: `Claude_Decks/Claude_Grass_Venusaur.csv`.
  - Agent baseline: `sub-agents/shared/baseline/main.py`.
  - Static deck and Python-interface validation passed.
  - Runtime import and gameplay benchmarks remain pending in an environment with
    the competition `cg` engine.
  - **Reason:** establish an isolated, reproducible deck-agent workspace before
    any automated strategic experiments begin.

## 2026-08-12 — EXP-0001

- **REJECTED: Verify the unchanged private baseline before tournament entry**
  - Mechanisms: infrastructure_baseline.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 1.
  - Decision reason: Infrastructure-only unchanged baseline; smoke validates runtime and safety but is not a strategic candidate

## 2026-08-12 — EXP-0002

- **REJECTED: For forced promotion and own-board CARD choices after a knockout, prefer an attack-ready Mega Venusaur ex, Hydrapple ex, or Teal Mask Ogerpon ex over support Pokemon when it can immediately deal more usable damage; preserve generic live-attacker scoring outside that narrow choice.**
  - Mechanisms: venusaur_attacker_concentration.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: human review rejection: Deck-specialist selection reset: retain Hydrapple only until the next four decks are chosen through comparative evaluation.
