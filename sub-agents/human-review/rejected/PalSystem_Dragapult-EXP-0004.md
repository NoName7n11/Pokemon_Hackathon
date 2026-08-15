# Human Review: PalSystem_Dragapult EXP-0004

## Hypothesis

Only in Dragapult ex Phantom Dive damage-counter selections, rank opposing Bench targets using live remaining HP, prize value, immediate knockout completion, and useful two-turn knockout setup; preserve all other DAMAGE_COUNTER and CARD target contexts unchanged.

Expected effect: Convert Phantom Dive's spread counters into more prizes and credible follow-up knockouts instead of following printed card power.

Mechanisms: phantom_dive_live_spread_targeting

## Review Assignment

- Implemented by: `codex` (`provider=codex`, `model=gpt-5.5`)
- Assigned reviewer: `opus` (`provider=claude`, `model=opus`)
- Reason: Codex-authored experiments require an independent Opus/Claude review.

## Evidence

- Stage: `screening`
- Candidate: `100/200` wins (50.0%)
- 95% interval: `43.1% - 56.9%`
- Head-to-head null test: `z=0.0`, `p=1.0`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `8.04 ms / 250.65 ms`

## Cross-Deck Evidence

[]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `2051`
- Different choices: `168` (8.2%)
- Games containing a difference: `19`
- Retained records: `168`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 168 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 1 | 5 | MAIN/MAIN | PLAY | PLAY |
| 1 | 43 | MAIN/MAIN | PLAY | EVOLVE |
| 2 | 48 | MAIN/MAIN | ATTACH | ATTACH |
| 2 | 80 | MAIN/MAIN | PLAY | ABILITY |
| 2 | 84 | MAIN/MAIN | ABILITY | ATTACH |

## Required Human Checks

- Does the diff implement only the stated mechanism?
- Does the observed result justify more evaluation rather than acceptance?
- Could the change affect unrelated selection contexts or deck archetypes?
- Is representative decision-trace evidence required before the next benchmark?

## Agent Diff

```diff
--- baseline/main.py
+++ candidate/main.py
@@ -154,6 +154,61 @@
     else:
         live_pressure = damage_taken * 20 - pokemon.hp * 10
     return lethal_bonus + active_bonus + live_pressure + static_threat + prize_value * 1000
+
+
+def _is_phantom_dive_spread_context(obs) -> bool:
+    """Detect Dragapult ex Phantom Dive's six-counter opposing Bench selection."""
+    sel = obs.select
+    state = obs.current
+    if sel is None or state is None:
+        return False
+    if sel.context != SelectContext.DAMAGE_COUNTER:
+        return False
+    if sel.remainDamageCounter is None or not 1 <= sel.remainDamageCounter <= 6:
+        return False
+
+    target_options = [
+        opt for opt in sel.option
+        if opt.playerIndex is not None and opt.area is not None
+    ]
+    if not target_options:
+        return False
+    opp_index = 1 - state.yourIndex
+    return all(
+        opt.playerIndex == opp_index and opt.area == AreaType.BENCH
+        for opt in target_options
+    )
+
+
+def _phantom_dive_spread_score(opt, obs):
+    """Prize-aware live-HP score for Phantom Dive bench counter placement."""
+    state = obs.current
+    if state is None:
+        return _option_card_power(opt)
+
+    pokemon = _option_pokemon(opt, state)
+    if pokemon is None:
+        return _option_card_power(opt)
+
+    sel = obs.select
+    assert sel is not None
+    counters_left = max(1, sel.remainDamageCounter or 1)
+    prize_value = _prize_value(pokemon)
+    hp = max(0, pokemon.hp)
+    counters_to_ko = (hp + 9) // 10
+    damage_taken = max(0, pokemon.maxHp - hp)
+
+    immediate_ko = counters_to_ko <= counters_left
+    next_phantom_setup = counters_left < counters_to_ko <= counters_left + 6
+
+    score = prize_value * 2000 + damage_taken * 8 - hp * 4
+    if immediate_ko:
+        score += 100000 * prize_value + (counters_left - counters_to_ko) * 100
+    elif next_phantom_setup:
+        score += 15000 * prize_value - (counters_to_ko - counters_left) * 150
+    else:
+        score += max(0, 90 - hp) * prize_value * 20
+    return score
 
 
 def _best_attach_index(options, indices, me):
@@ -345,7 +400,9 @@
         if opponent_indices:
             indices = opponent_indices
 
-    if sel.context in opponent_target_contexts:
+    if _is_phantom_dive_spread_context(obs):
+        ranked = sorted(indices, key=lambda i: _phantom_dive_spread_score(options[i], obs), reverse=True)
+    elif sel.context in opponent_target_contexts:
         ranked = sorted(indices, key=lambda i: _target_score(options[i], obs), reverse=True)
     else:
         reverse = sel.context not in weakest_first_contexts
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.


## Opus Auto Review

Decision: MORE_EVIDENCE.

REJECT

## Reasoning

**The screening result is exactly null, not merely weak.** 100/200 wins (50.0%), 95% CI 43.1%–56.9%, head-to-head z=0.0, p=1.0. This is a coin flip. There is no positive signal to justify either acceptance or the cost of deep evaluation. A candidate that lands on 50.0% with p=1.0 has produced zero evidence of the claimed benefit ("convert spread counters into more prizes and credible follow-up knockouts").

**The trace does not confirm the claimed mechanism ever fires.** This is the decisive problem. The hypothesis is narrowly about `DAMAGE_COUNTER` selections during Dragapult ex Phantom Dive spread targeting. But the decision-difference trace shows all 168 differences classified as `MAIN`, and every representative difference is a PLAY / ATTACH / ABILITY / EVOLVE decision — not a single damage-counter target choice. So the evidence we're shown is entirely *downstream drift* (games diverging into different lines), with no captured instance of the actual Phantom Dive bench-ranking logic changing a target. The experiment therefore fails its own review question: "Confirm that the experiment evidence matches its claimed mechanism." It does not. We cannot see the mechanism act even once.

**Diff scoping looks clean, which makes this a measurement failure, not an implementation bug.** `_is_phantom_dive_spread_context` is well-guarded (requires DAMAGE_COUNTER context, 1–6 remaining counters, and all target options being opponent-bench), and the dispatch change (`main.py:400-404`) is correctly gated so other target contexts fall through unchanged. So the "affects unrelated contexts" risk is low *by construction* — but that also means the 168 MAIN divergences are pure cascade noise from a mechanism we can't observe producing any measurable prize gain.

**Why REJECT rather than MORE_EVIDENCE:** screening already ran the full 200-game sample and returned exact-null with p=1.0. The mechanism either almost never triggers in this matchup (making the whole line irrelevant) or triggers without moving win rate. Requesting another ablation on a mechanism that already shows p=1.0 at full screening sample would burn evaluation budget without a plausible path to a positive result. If the author wants to revive this, the burden is on them to (a) instrument and show DAMAGE_COUNTER decisions actually flipping, and (b) pick a matchup/deck where Phantom Dive spread targeting occurs often enough to matter — then re-screen.

To be explicit on the required checks: the diff implements only the stated mechanism (yes); the result does **not** justify more evaluation (p=1.0, 50.0%); unrelated contexts are protected by the guard; and representative *DAMAGE_COUNTER* trace evidence is missing and would be required — but should be produced before, not after, spending another benchmark on this.

(Assignment check: implemented by Codex/gpt-5.5, reviewed by Opus/Claude — the cross-family rule is satisfied.) I have not edited or promoted anything.

Audit artifact: `specialists/PalSystem_Dragapult/experiments/EXP-0004/reviews/screening-opus-auto-review.json`.
