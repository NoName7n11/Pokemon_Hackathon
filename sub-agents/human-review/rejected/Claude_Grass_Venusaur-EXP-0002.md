# Human Review: Claude_Grass_Venusaur EXP-0002

## Hypothesis

For forced promotion and own-board CARD choices after a knockout, prefer an attack-ready Mega Venusaur ex, Hydrapple ex, or Teal Mask Ogerpon ex over support Pokemon when it can immediately deal more usable damage; preserve generic live-attacker scoring outside that narrow choice.

Expected effect: Increase attacks made by the deck's primary attackers and reduce turns lost after a knockout without changing global evaluation or ability handling.

Mechanisms: venusaur_attacker_concentration

## Evidence

- Stage: `screening`
- Candidate: `121/200` wins (60.5%)
- 95% interval: `53.6% - 67.0%`
- Head-to-head null test: `z=2.969848480983499`, `p=0.00297946665633299`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `8.76 ms / 423.85 ms`

## Cross-Deck Evidence

[]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `1147`
- Different choices: `75` (6.5%)
- Games containing a difference: `18`
- Retained records: `75`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 75 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 2 | 8 | MAIN/MAIN | ATTACH | PLAY |
| 2 | 9 | MAIN/MAIN | PLAY | PLAY |
| 2 | 12 | MAIN/MAIN | PLAY | PLAY |
| 2 | 13 | MAIN/MAIN | PLAY | PLAY |
| 3 | 20 | MAIN/MAIN | ATTACH | ATTACH |

## Required Human Checks

- Does the diff implement only the stated mechanism?
- Does the observed result justify more evaluation rather than acceptance?
- Could the change affect unrelated selection contexts or deck archetypes?
- Is representative decision-trace evidence required before the next benchmark?

## Agent Diff

```diff
--- baseline/main.py
+++ candidate/main.py
@@ -198,6 +198,31 @@
     lethal_bonus = 3000 if opp_active is not None and dmg >= opp_active.hp else 0
     prize_penalty = 120 * _prize_value(mon)
     return lethal_bonus + dmg * 20 + mon.hp + len(mon.energies) * 15 - prize_penalty
+
+
+def _attacker_concentration_bonus(mon) -> int:
+    """EXP-0002 (venusaur_attacker_concentration): when a forced-promotion /
+    own-board CARD choice after a knockout offers this deck's rule-box
+    attackers (Mega Venusaur ex reports card.megaEx; Hydrapple ex and Teal
+    Mask Ogerpon ex report card.ex), prefer one that can immediately attack
+    over a support Pokemon.
+
+    _live_attacker_score subtracts a prize-liability penalty (120 * prize
+    value) that pushes promotion toward a cheap support chump; here we cancel
+    that penalty for an already-attack-ready rule-box attacker and add a small
+    usable-damage-weighted preference so the attacker beats support that deals
+    less. Gated on usable_damage > 0: at setup nothing is powered yet, so this
+    is silent there and generic live-attacker scoring is preserved outside the
+    narrow post-knockout choice."""
+    if mon is None:
+        return 0
+    card = _card_data().get(mon.id)
+    if card is None or not (card.ex or card.megaEx):
+        return 0
+    dmg = _best_usable_damage(mon)
+    if dmg <= 0:
+        return 0
+    return 120 * _prize_value(mon) + dmg * 5
 
 
 def _ability_cap_reached(state) -> bool:
@@ -360,11 +385,11 @@
         if own_board_indices:
             opp = obs.current.players[1 - obs.current.yourIndex]
             opp_active = opp.active[0] if opp.active else None
-            ranked = sorted(
-                indices,
-                key=lambda i: _live_attacker_score(_option_pokemon(options[i], obs.current), opp_active),
-                reverse=True,
-            )
+            def _own_board_key(i):
+                mon = _option_pokemon(options[i], obs.current)
+                return _live_attacker_score(mon, opp_active) + _attacker_concentration_bonus(mon)
+
+            ranked = sorted(indices, key=_own_board_key, reverse=True)
         else:
             ranked = sorted(indices, key=lambda i: _option_card_power(options[i]), reverse=reverse)
     return ranked[: sel.maxCount] if sel.maxCount > 0 else []
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.
