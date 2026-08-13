# Human Review: Dark EXP-0002

## Hypothesis

For attack choice and immediate attacker scoring, account for Mega Sharpedo ex Hungry Jaws receiving its conditional damage only when Sharpedo is damaged; preserve generic attack ranking for all other Pokemon.

Expected effect: Promote and attack with damaged Mega Sharpedo when Hungry Jaws is a real high-damage option without globally inflating its value.

Mechanisms: sharpedo_conditional_attack_value

## Evidence

- Stage: `screening`
- Candidate: `105/200` wins (52.5%)
- 95% interval: `45.6% - 59.3%`
- Head-to-head null test: `z=0.7071067811865481`, `p=0.4795001221869531`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `5.87 ms / 149.25 ms`

## Cross-Deck Evidence

[]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `1107`
- Different choices: `44` (4.0%)
- Games containing a difference: `12`
- Retained records: `44`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 44 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 1 | 20 | MAIN/MAIN | ATTACH | PLAY |
| 1 | 21 | MAIN/MAIN | PLAY | RETREAT |
| 1 | 25 | MAIN/MAIN | RETREAT | PLAY |
| 1 | 64 | MAIN/MAIN | PLAY | ATTACH |
| 1 | 79 | MAIN/MAIN | ATTACH | END |

## Required Human Checks

- Does the diff implement only the stated mechanism?
- Does the observed result justify more evaluation rather than acceptance?
- Could the change affect unrelated selection contexts or deck archetypes?
- Is representative decision-trace evidence required before the next benchmark?

## Agent Diff

```diff
--- baseline/main.py
+++ candidate/main.py
@@ -34,6 +34,16 @@
 ABILITY_CAP_PER_TURN = 4    # see _ability_cap_reached: guards against unbounded Abilities
 _live_ability_count: dict = {}
 _last_seen_turn = -1
+
+# Mega Sharpedo ex "Hungry Jaws" deals extra damage ONLY while Sharpedo itself
+# has damage counters on it. The static attack table stores the unconditional
+# base damage, so a damaged Sharpedo is worth more than the generic ranking
+# implies. This bonus is credited for that exact attack, and only when the
+# acting Pokemon is damaged -- see _sharpedo_conditional_bonus. REVIEWER: verify
+# the magnitude and that the engine's static attack .damage is the BASE (not the
+# already-boosted) value against the actual card DB before trusting the sign of
+# any measured effect.
+HUNGRY_JAWS_CONDITIONAL_BONUS = 100
 
 
 def _card_data():
@@ -81,13 +91,19 @@
     return by_type
 
 
-def _best_attack_index(options, indices):
-    """Index (into options) of the highest-damage attack among the given option indices."""
+def _best_attack_index(options, indices, mon=None):
+    """Index (into options) of the highest-damage attack among the given option
+    indices. When the acting Pokemon `mon` is supplied, damage estimates account
+    for its conditional attacks (Mega Sharpedo ex Hungry Jaws) via
+    _sharpedo_conditional_bonus; other Pokemon are unaffected."""
     attacks = _attack_data()
+    card = _card_data().get(mon.id) if mon is not None else None
     best_i, best_dmg = indices[0], -1
     for i in indices:
         atk = attacks.get(options[i].attackId)
         dmg = atk.damage if atk else 0
+        if atk is not None and card is not None:
+            dmg += _sharpedo_conditional_bonus(card, atk, mon)
         if dmg > best_dmg:
             best_i, best_dmg = i, dmg
     return best_i, best_dmg
@@ -254,11 +270,12 @@
     me = state.players[state.yourIndex]
     opp = state.players[1 - state.yourIndex]
     opp_active = opp.active[0] if opp.active else None
+    my_active = me.active[0] if me.active else None
     by_type = _group_by_type(options)
 
     # 1. Attack for lethal (engine only lists attacks we have Energy for).
     if OptionType.ATTACK in by_type and opp_active is not None:
-        idx, dmg = _best_attack_index(options, by_type[OptionType.ATTACK])
+        idx, dmg = _best_attack_index(options, by_type[OptionType.ATTACK], my_active)
         if dmg >= opp_active.hp:
             return [idx]
 
@@ -283,7 +300,7 @@
 
     # 6. Attack anyway with the strongest available attack.
     if OptionType.ATTACK in by_type:
-        idx, _ = _best_attack_index(options, by_type[OptionType.ATTACK])
+        idx, _ = _best_attack_index(options, by_type[OptionType.ATTACK], my_active)
         return [idx]
 
     # 7. Retreat only if the Active is dying and a stronger Benched Pokémon exists.
@@ -293,7 +310,6 @@
     # choice is decided at forced promotion after a KO, not by voluntary retreat.
     # Don't reintroduce a retreat heuristic without measuring it in isolation.
     if OptionType.RETREAT in by_type:
-        my_active = me.active[0] if me.active else None
         if my_active is not None and me.bench:
             low_hp = my_active.hp <= my_active.maxHp * 0.3
             if low_hp and any(b.hp > my_active.hp for b in me.bench):
@@ -309,7 +325,10 @@
 def _choose_attack(obs: Observation) -> list[int]:
     sel = obs.select
     assert sel is not None
-    idx, _ = _best_attack_index(sel.option, list(range(len(sel.option))))
+    state = obs.current
+    me = state.players[state.yourIndex] if state is not None else None
+    my_active = me.active[0] if me and me.active else None
+    idx, _ = _best_attack_index(sel.option, list(range(len(sel.option))), my_active)
     return [idx]
 
 
@@ -460,6 +479,34 @@
     return len(pool) >= colorless
 
 
+def _name_of(obj) -> str:
+    """Best-effort lowercase name for a card/attack. Returns '' when the engine
+    build exposes no name attribute, so every Sharpedo check below simply no-ops
+    (baseline behavior) rather than crashing on an unfamiliar object."""
+    return (getattr(obj, "name", "") or "").lower()
+
+
+def _sharpedo_conditional_bonus(card, attack, mon) -> int:
+    """Extra Hungry Jaws damage to credit for a DAMAGED Mega Sharpedo ex.
+
+    Mega Sharpedo ex's Hungry Jaws gains its conditional damage only while this
+    Pokemon has damage counters on it; the static attack table lists just the
+    base. Return the conditional bonus when (and only when) the acting Pokemon is
+    Mega Sharpedo ex, the attack is Hungry Jaws, and Sharpedo is currently
+    damaged. Every other Pokemon/attack returns 0, so generic ranking and an
+    UNDAMAGED Sharpedo are left exactly as the baseline scored them (no global
+    inflation of Sharpedo's value)."""
+    if card is None or attack is None or mon is None:
+        return 0
+    if not getattr(card, "megaEx", False) or "sharpedo" not in _name_of(card):
+        return 0
+    if "hungry jaws" not in _name_of(attack):
+        return 0
+    if mon.hp >= mon.maxHp:  # undamaged -> conditional damage does not apply
+        return 0
+    return HUNGRY_JAWS_CONDITIONAL_BONUS
+
+
 def _best_usable_damage(mon) -> int:
     """Highest damage this Pokémon can actually deal right now (cost affordable)."""
     if mon is None:
@@ -472,7 +519,7 @@
     for aid in card.attacks:
         a = attacks.get(aid)
         if a is not None and _can_pay(a.energies, mon.energies):
-            best = max(best, a.damage)
+            best = max(best, a.damage + _sharpedo_conditional_bonus(card, a, mon))
     return best
 
 
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.
