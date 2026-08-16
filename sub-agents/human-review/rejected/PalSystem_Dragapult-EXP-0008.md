# Human Review: PalSystem_Dragapult EXP-0008

## Hypothesis

Use the corrected replay-pattern report from palsystem_games/analysis/replay_patterns.md. Implement only PalSystem opening setup CARD selection: when obs.select.type is CARD/select type 1 and context is numeric 1, choose Active by replay priority Dreepy first, then Munkidori, then Budew, then Meowth ex, then Fezandipiti ex. When context is numeric 2, choose setup Bench by replay priority Dreepy first, then Munkidori, then Meowth ex, then Fezandipiti ex, then Budew. Do not change MAIN-phase PLAY, ATTACH, Trainer, Ability, Attack, Evolve, or damage-target logic.

Expected effect: Correct the previous failed setup attempt by using the raw replay numeric CARD contexts 1 and 2; decision traces must show differences in CARD context 1 or 2, not MAIN cascade differences, before any deep evaluation.

Mechanisms: numeric_setup_context_replay_priority

## Review Assignment

- Implemented by: `codex` (`provider=codex`, `model=gpt-5.5`)
- Assigned reviewer: `opus` (`provider=claude`, `model=opus`)
- Reason: Codex-authored experiments require an independent Opus/Claude review.

## Evidence

- Stage: `screening`
- Candidate: `104/200` wins (52.0%)
- 95% interval: `45.1% - 58.8%`
- Head-to-head null test: `z=0.5656854249492386`, `p=0.5716076449533313`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `8.43 ms / 673.50 ms`

## Cross-Deck Evidence

[]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `1915`
- Different choices: `118` (6.2%)
- Games containing a difference: `20`
- Retained records: `118`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 118 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 1 | 45 | MAIN/MAIN | PLAY | EVOLVE |
| 1 | 128 | MAIN/MAIN | PLAY | PLAY |
| 2 | 10 | MAIN/MAIN | PLAY | PLAY |
| 2 | 11 | MAIN/MAIN | PLAY | PLAY |
| 2 | 28 | MAIN/MAIN | ATTACH | ATTACH |

## Required Human Checks

- Does the diff implement only the stated mechanism?
- Does the observed result justify more evaluation rather than acceptance?
- Could the change affect unrelated selection contexts or deck archetypes?
- Is representative decision-trace evidence required before the next benchmark?

## Agent Diff

```diff
--- baseline/main.py
+++ candidate/main.py
@@ -108,8 +108,55 @@
     return _card_power(opt.cardId) if opt.cardId is not None else 0
 
 
+def _raw_enum_value(value):
+    if hasattr(value, "value"):
+        value = value.value
+    try:
+        return int(value)
+    except (TypeError, ValueError):
+        return value
+
+
+def _card_name(card_id) -> str:
+    card = _card_data().get(card_id)
+    if card is None:
+        return ""
+    return str(
+        getattr(card, "name", "")
+        or getattr(card, "cardName", "")
+        or getattr(card, "displayName", "")
+    ).lower()
+
+
 def _best_card_option(options, indices, reverse=True):
     return sorted(indices, key=lambda i: _option_card_power(options[i]), reverse=reverse)[0]
+
+
+def _setup_replay_priority_choice(obs: Observation):
+    """Replay-derived opening setup only: raw CARD contexts 1 and 2."""
+    sel = obs.select
+    assert sel is not None
+    if _raw_enum_value(sel.type) != 1:
+        return None
+    context = _raw_enum_value(sel.context)
+    if context == 1:
+        priority = ("dreepy", "munkidori", "budew", "meowth ex", "fezandipiti ex")
+    elif context == 2:
+        priority = ("dreepy", "munkidori", "meowth ex", "fezandipiti ex", "budew")
+    else:
+        return None
+
+    priority_rank = {name: rank for rank, name in enumerate(priority)}
+
+    def rank(i):
+        name = _card_name(sel.option[i].cardId)
+        return (
+            priority_rank.get(name, len(priority)),
+            -_option_card_power(sel.option[i]),
+            i,
+        )
+
+    return sorted(range(len(sel.option)), key=rank)[: sel.maxCount] if sel.maxCount > 0 else []
 
 
 def _option_pokemon(opt, state):
@@ -326,6 +373,9 @@
     sel = obs.select
     assert sel is not None
     options = sel.option
+    setup_choice = _setup_replay_priority_choice(obs)
+    if setup_choice is not None:
+        return setup_choice
     weakest_first_contexts = (
         SelectContext.DISCARD,
         SelectContext.TO_DECK,
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.
