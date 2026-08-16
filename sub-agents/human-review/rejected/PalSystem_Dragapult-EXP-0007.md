# Human Review: PalSystem_Dragapult EXP-0007

## Hypothesis

Replay-curated PalSystem games show Dreepy is the dominant successful opener and first setup body. For opening Active and initial setup Bench CARD selections only, prefer Dreepy first, then Munkidori/Budew as fallback support, while keeping Fezandipiti ex and Meowth ex off Active unless no better Basic is available; preserve all MAIN-phase play, Energy, Trainer, Ability, attack, evolution, and damage-target logic unchanged.

Expected effect: Increase stable Dragapult-line setup without bundling speculative Energy or Trainer changes; decision traces must prove the changed decisions are opening/setup CARD selections and not unrelated cascade differences.

Mechanisms: dreepy_first_opening_setup_only

## Review Assignment

- Implemented by: `codex` (`provider=codex`, `model=gpt-5.5`)
- Assigned reviewer: `opus` (`provider=claude`, `model=opus`)
- Reason: Codex-authored experiments require an independent Opus/Claude review.

## Evidence

- Stage: `screening`
- Candidate: `96/200` wins (48.0%)
- 95% interval: `41.2% - 54.9%`
- Head-to-head null test: `z=-0.5656854249492386`, `p=0.5716076449533313`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `6.01 ms / 196.67 ms`

## Cross-Deck Evidence

[]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `1897`
- Different choices: `127` (6.7%)
- Games containing a difference: `20`
- Retained records: `127`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 127 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 1 | 88 | MAIN/MAIN | EVOLVE | ATTACH |
| 1 | 89 | MAIN/MAIN | ABILITY | PLAY |
| 2 | 7 | MAIN/MAIN | ATTACH | PLAY |
| 2 | 11 | MAIN/MAIN | PLAY | PLAY |
| 2 | 72 | MAIN/MAIN | PLAY | PLAY |

## Required Human Checks

- Does the diff implement only the stated mechanism?
- Does the observed result justify more evaluation rather than acceptance?
- Could the change affect unrelated selection contexts or deck archetypes?
- Is representative decision-trace evidence required before the next benchmark?

## Agent Diff

```diff
--- baseline/main.py
+++ candidate/main.py
@@ -110,6 +110,44 @@
 
 def _best_card_option(options, indices, reverse=True):
     return sorted(indices, key=lambda i: _option_card_power(options[i]), reverse=reverse)[0]
+
+
+def _card_name(card) -> str:
+    for attr in ("name", "cardName", "displayName"):
+        value = getattr(card, attr, None)
+        if value:
+            return str(value)
+    return ""
+
+
+def _select_context_name(context) -> str:
+    return getattr(context, "name", str(context).split(".")[-1])
+
+
+def _setup_basic_priority(opt, active: bool) -> tuple[int, int]:
+    """Deck-specific opening setup only: establish Dreepy before support Basics."""
+    card = _card_data().get(opt.cardId)
+    if card is None or card.cardType != CardType.POKEMON or not card.basic:
+        return (-1, _option_card_power(opt))
+
+    name = _card_name(card).lower()
+    if name == "dreepy":
+        return (50000, _option_card_power(opt))
+    if name == "munkidori":
+        return (40000, _option_card_power(opt))
+    if name == "budew":
+        return (39000, _option_card_power(opt))
+    if active and name in ("fezandipiti ex", "meowth ex"):
+        return (0, _option_card_power(opt))
+    return (10000, _option_card_power(opt))
+
+
+def _choose_setup_card(obs: Observation, active: bool):
+    sel = obs.select
+    assert sel is not None
+    indices = list(range(len(sel.option)))
+    ranked = sorted(indices, key=lambda i: _setup_basic_priority(sel.option[i], active), reverse=True)
+    return ranked[: sel.maxCount] if sel.maxCount > 0 else []
 
 
 def _option_pokemon(opt, state):
@@ -326,6 +364,12 @@
     sel = obs.select
     assert sel is not None
     options = sel.option
+    context_name = _select_context_name(sel.context)
+    if context_name == "SETUP_ACTIVE_POKEMON":
+        return _choose_setup_card(obs, active=True)
+    if context_name == "SETUP_BENCH_POKEMON":
+        return _choose_setup_card(obs, active=False)
+
     weakest_first_contexts = (
         SelectContext.DISCARD,
         SelectContext.TO_DECK,
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.
