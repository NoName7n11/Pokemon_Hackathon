# Hydrapple Specialist Progress

Append-only experiment log for this private Plan_2 specialist. This directory is
not the active submission.

---

## 2026-08-12

- **Specialist initialized**:
  - Worker provider: `codex`.
  - Source deck: `Decs/Hydrapple.csv`.
  - Agent baseline: `sub-agents/shared/baseline/main.py`.
  - Static deck and Python-interface validation passed.
  - Runtime import and gameplay benchmarks remain pending in an environment with
    the competition `cg` engine.
  - **Reason:** establish an isolated, reproducible deck-agent workspace before
    any automated strategic experiments begin.

## 2026-08-12 — EXP-0001

- **REJECTED: Verify the bounded experiment lifecycle with an unchanged candidate**
  - Mechanisms: infrastructure_smoke.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 1.
  - Decision reason: Infrastructure-only unchanged candidate; the 2-game seat-balanced smoke run passed 1-1 with zero crashes, illegal actions, draws, or timeouts, but contains no strategic improvement to accept.
