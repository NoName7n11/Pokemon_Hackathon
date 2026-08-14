# Human Review: Grass EXP-0003

## Hypothesis

During opening setup, prefer Mega Kangaskhan ex as Active when Run Errand is usable while preserving Yanma on the Bench so an evolved Yanmega ex can later trigger Buzzing Boost when it moves Active; preserve existing choices outside opening Active/Bench placement.

Expected effect: Increase early draw consistency without disabling Yanmega's Bench-to-Active acceleration trigger.

Mechanisms: kangaskhan_active_yanma_bench_opening

## Review Assignment

- Implemented by: `claude` (`provider=claude`, `model=default`)
- Assigned reviewer: `codex` (`provider=codex`, `model=gpt-5.5`)
- Reason: Claude/Opus-authored experiments require an independent Codex review.

## Evidence

- Stage: `screening`
- Candidate: `96/200` wins (48.0%)
- 95% interval: `41.2% - 54.9%`
- Head-to-head null test: `z=-0.5656854249492386`, `p=0.5716076449533313`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `6.76 ms / 326.50 ms`

## Cross-Deck Evidence

[]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `1212`
- Different choices: `42` (3.5%)
- Games containing a difference: `14`
- Retained records: `42`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 42 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 1 | 5 | MAIN/MAIN | ATTACH | ATTACH |
| 1 | 6 | MAIN/MAIN | ATTACH | ATTACH |
| 1 | 10 | MAIN/MAIN | PLAY | PLAY |
| 3 | 5 | MAIN/MAIN | ATTACH | PLAY |
| 3 | 95 | MAIN/MAIN | PLAY | ATTACH |

## Required Human Checks

- Does the diff implement only the stated mechanism?
- Does the observed result justify more evaluation rather than acceptance?
- Could the change affect unrelated selection contexts or deck archetypes?
- Is representative decision-trace evidence required before the next benchmark?

## Agent Diff

```diff
--- baseline/main.py
+++ candidate/main.py
@@ -34,6 +34,11 @@
 ABILITY_CAP_PER_TURN = 4    # see _ability_cap_reached: guards against unbounded Abilities
 _live_ability_count: dict = {}
 _last_seen_turn = -1
+
+# Opening-setup Active preference (see STRATEGY.md "Opening and board construction"
+# and hypothesis kangaskhan_active_yanma_bench_opening).
+KANGASKHAN_EX_ID = 756  # Mega Kangaskhan ex: preferred opening Active / Run Errand draw engine
+YANMA_ID = 339          # keep Benched so an evolved Yanmega ex can later trigger Buzzing Boost
 
 
 def _card_data():
@@ -370,6 +375,36 @@
     return ranked[: sel.maxCount] if sel.maxCount > 0 else []
 
 
+def _setup_active_context():
+    """The SelectContext used when choosing the opening Active Pokemon, resolved
+    defensively so an engine that names it differently simply disables this
+    preference (rather than crashing / changing unrelated selections)."""
+    for name in ("SETUP_ACTIVE_POKEMON", "SETUP_ACTIVE"):
+        ctx = getattr(SelectContext, name, None)
+        if ctx is not None:
+            return ctx
+    return None
+
+
+def _choose_setup_active(sel) -> list[int]:
+    """Opening Active choice (hypothesis kangaskhan_active_yanma_bench_opening).
+
+    Prefer Mega Kangaskhan ex as the opening Active -- its Run Errand draw engine
+    drives early consistency -- while keeping Yanma on the Bench so an evolved
+    Yanmega ex can later trigger Buzzing Boost by moving Bench -> Active. When
+    Kangaskhan is not an available Active choice, fall back to the existing
+    static card-power ranking but still avoid promoting Yanma if any other Basic
+    is available, preserving it for the Bench-to-Active acceleration line."""
+    options = sel.option
+    indices = list(range(len(options)))
+    kanga = [i for i in indices if options[i].cardId == KANGASKHAN_EX_ID]
+    if kanga:
+        return [kanga[0]]
+    non_yanma = [i for i in indices if options[i].cardId != YANMA_ID]
+    pool = non_yanma if non_yanma else indices
+    return [sorted(pool, key=lambda i: _option_card_power(options[i]), reverse=True)[0]]
+
+
 def _choose_yes_no(obs: Observation) -> list[int]:
     """Default optimistic: take the beneficial-sounding option when offered."""
     sel = obs.select
@@ -412,6 +447,13 @@
     options = sel.option
     if not options:
         return []
+
+    # Opening-setup Active placement: prefer Mega Kangaskhan ex, keep Yanma
+    # benched. Only fires on the setup Active context; all other selections
+    # (including setup Bench placement) keep their existing behavior.
+    setup_active_ctx = _setup_active_context()
+    if setup_active_ctx is not None and sel.context == setup_active_ctx:
+        return _clamp(_choose_setup_active(sel), sel, len(options))
 
     if sel.type == SelectType.MAIN:
         idx_list = _choose_main(obs)
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.

## Human Review

Decision: REJECT for acceptance. APPROVE only if the agent wants to redesign/retest the experiment with proper setup traces.

Reason:
- The hypothesis is strategically reasonable: Mega Kangaskhan ex Active can improve early draw through Run Errand, while Yanma should usually stay Benched for the Yanmega ex Buzzing Boost line.
- The evidence does not support accepting the change. Candidate scored 96/200, 48.0%, with p=0.57, which is not an improvement.
- The decision-difference trace is not aligned with the stated mechanism. It reports MAIN/MAIN differences only, while the proposed code is supposed to affect opening Active setup. That means either the trace missed setup decisions or the change is not being measured correctly.
- Before any deeper benchmark, require representative setup traces showing actual opening hands where Kangaskhan and Yanma are both available, Kangaskhan is selected Active, and Yanma is preserved on Bench.
- Keep this deck-specific only. Hardcoded Kangaskhan/Yanma IDs should not be promoted into shared general logic.
- Do not accept into the deck agent yet. 

## Codex Independent Review

Decision: REJECT for acceptance and do not authorize deep evaluation.

Reason:
- I agree with the human review above. The idea is strategically plausible, but
  the measured candidate is not an improvement: 96/200 wins, 48.0%, p=0.5716.
- The evidence does not prove the mechanism fired. The trace reports only
  MAIN/MAIN differences, while the diff is supposed to affect opening Active
  setup. That means the trace instrumentation either missed the relevant setup
  selection or the candidate's actual measured differences are downstream noise.
- The smoke result was also weak at 8/20, and the max decision time spiked to
  1900 ms during smoke. It did not crash, but that tail is not a reason to spend
  deeper benchmark budget on a statistically neutral/negative candidate.
- The code is reasonably narrow because it gates on setup Active context, but
  the hardcoded Kangaskhan/Yanma IDs are deck-specific and should not move into
  shared logic.

Recommended next action:
- Reject this candidate.
- If the idea is retried, first add/setup a trace that captures opening Active
  decisions directly and requires examples where both Kangaskhan and Yanma are
  available in the opening selection.
