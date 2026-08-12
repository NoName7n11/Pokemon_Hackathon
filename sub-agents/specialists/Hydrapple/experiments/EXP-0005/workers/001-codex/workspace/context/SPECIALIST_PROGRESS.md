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

## 2026-08-12 — EXP-0002

- **REJECTED: Verify all configured provider adapters create isolated, bounded worker invocations without calling a model**
  - Mechanisms: provider_orchestration.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 0.
  - Decision reason: Provider-adapter infrastructure dry run only: Codex, Claude Code, and the configured Antigravity/Gemini backend resolved and received isolated equivalent workspaces; no model was invoked and no candidate strategy changed.

## 2026-08-12 — EXP-0003

- **REJECTED: Verify the Phase 4 successful orchestration and human-review path using a local no-op fixture without external source transmission**
  - Mechanisms: local_orchestration_fixture.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: human review rejection: Local no-op fixture changed only a comment; 54/100 at screening (p=0.424) is expected noise and provides no gameplay mechanism to advance.

## 2026-08-12 — EXP-0004

- **REJECTED: When choosing a normal Energy attachment, prefer an in-play Pokemon when that single attachment makes one of its attacks usable this turn; preserve Active preference and existing strength ordering as tie-breakers.**
  - Mechanisms: attack_readiness_attachment.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 0.
  - Decision reason: automatic rejection: provider stage failed with exit 1
