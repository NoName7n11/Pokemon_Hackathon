# Human Review: Fire EXP-0003

## Hypothesis

For Mega Charizard X ex and Mega Charizard Y ex only, estimate effect-driven attack damage and required Energy discard in lethal, attack, and immediate-attacker ranking instead of treating their printed zero damage as zero; preserve all other attack logic.

Expected effect: Choose powered Charizard attacks and promotions when their live effect damage is tactically superior, without changing unrelated Pokemon.

Mechanisms: charizard_effect_damage_evaluation_v2

## Review Assignment

- Implemented by: `codex` (`provider=codex`, `model=default`)
- Assigned reviewer: `opus` (`provider=claude`, `model=opus`)
- Reason: Codex-authored experiments require an independent Opus/Claude review.

## Evidence

- Stage: `screening`
- Candidate: `107/200` wins (53.5%)
- 95% interval: `46.6% - 60.3%`
- Head-to-head null test: `z=0.9899494936611675`, `p=0.3221988061625811`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `4.16 ms / 252.47 ms`

## Cross-Deck Evidence

[]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `1132`
- Different choices: `24` (2.1%)
- Games containing a difference: `9`
- Retained records: `24`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 24 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 1 | 17 | MAIN/MAIN | PLAY | PLAY |
| 1 | 114 | MAIN/MAIN | ATTACH | EVOLVE |
| 1 | 127 | MAIN/MAIN | PLAY | ATTACH |
| 1 | 128 | MAIN/MAIN | ATTACH | ATTACH |
| 1 | 129 | MAIN/MAIN | EVOLVE | ATTACH |

## Required Human Checks

- Does the diff implement only the stated mechanism?
- Does the observed result justify more evaluation rather than acceptance?
- Could the change affect unrelated selection contexts or deck archetypes?
- Is representative decision-trace evidence required before the next benchmark?

## Agent Diff

```diff
--- baseline/main.py
+++ candidate/main.py
@@ -1,3 +1,4 @@
+import re
 from pathlib import Path
 
 from cg.api import (
@@ -81,15 +82,16 @@
     return by_type
 
 
-def _best_attack_index(options, indices):
-    """Index (into options) of the highest-damage attack among the given option indices."""
+def _best_attack_index(options, indices, attacker=None):
+    """Index (into options) of the best attack among the given option indices."""
     attacks = _attack_data()
-    best_i, best_dmg = indices[0], -1
+    best_i, best_dmg, best_discard, best_score = indices[0], -1, 0, float("-inf")
     for i in indices:
         atk = attacks.get(options[i].attackId)
-        dmg = atk.damage if atk else 0
-        if dmg > best_dmg:
-            best_i, best_dmg = i, dmg
+        dmg, discard = _attack_damage_and_discard(atk, attacker)
+        score = dmg * 100 - discard * 25
+        if score > best_score:
+            best_i, best_dmg, best_discard, best_score = i, dmg, discard, score
     return best_i, best_dmg
 
 
@@ -173,6 +175,96 @@
     return best_i
 
 
+def _norm_name(obj) -> str:
+    return str(getattr(obj, "name", "") or "").lower().replace("-", " ")
+
+
+def _text_blob(*objs) -> str:
+    parts = []
+    for obj in objs:
+        if obj is None:
+            continue
+        for attr in ("name", "text", "effect", "effects", "description", "ruleText"):
+            value = getattr(obj, attr, None)
+            if value:
+                parts.append(str(value))
+    return " ".join(parts).lower().replace("-", " ")
+
+
+def _is_target_charizard(card) -> bool:
+    name = _norm_name(card)
+    return name in ("mega charizard x ex", "mega charizard y ex")
+
+
+def _fire_energy_count(mon) -> int:
+    if mon is None:
+        return 0
+    return sum(1 for e in mon.energies if e in (EnergyType.FIRE, EnergyType.RAINBOW))
+
+
+def _charizard_effect_damage_and_discard(card, attack, mon=None):
+    """Estimate zero-printed Mega Charizard X/Y ex attacks without touching
+    unrelated Pokemon. The simulator decides legality; this is only ranking.
+    """
+    if card is None or attack is None or not _is_target_charizard(card):
+        return None
+    printed = getattr(attack, "damage", 0) or 0
+    if printed > 0:
+        return printed, 0
+
+    text = _text_blob(card, attack)
+    fire_count = _fire_energy_count(mon)
+
+    discard = 0
+    fixed = None
+    per_energy = None
+
+    all_fire = re.search(r"discard all .*fire energ", text)
+    if all_fire:
+        discard = fire_count
+    else:
+        n_discard = re.search(r"discard (\d+) .*energ", text)
+        if n_discard:
+            discard = int(n_discard.group(1))
+        elif "discard" in text and "energ" in text:
+            discard = 1
+
+    per_match = re.search(r"(\d+) (?:more )?damage for each .*energ", text)
+    if per_match:
+        per_energy = int(per_match.group(1))
+
+    fixed_match = re.search(r"(?:does|do) (\d+) damage", text)
+    if fixed_match:
+        fixed = int(fixed_match.group(1))
+
+    attack_name = _norm_name(attack)
+    if fixed is None:
+        if "crimson" in attack_name or "wild blaze" in attack_name:
+            fixed = 300
+        elif "inferno x" in attack_name:
+            per_energy = per_energy or 50
+            discard = discard or fire_count
+
+    if per_energy is not None:
+        usable = fire_count if discard == 0 else min(fire_count, discard)
+        return per_energy * usable, usable
+    if fixed is not None:
+        if discard and fire_count < discard:
+            return 0, fire_count
+        return fixed, discard
+    return None
+
+
+def _attack_damage_and_discard(attack, mon=None):
+    if attack is None:
+        return 0, 0
+    card = _card_data().get(mon.id) if mon is not None else None
+    charizard_eval = _charizard_effect_damage_and_discard(card, attack, mon)
+    if charizard_eval is not None:
+        return charizard_eval
+    return getattr(attack, "damage", 0) or 0, 0
+
+
 def _best_play_index(options, indices, me):
     """Rank playable Basic Pokemon by likely board value."""
     cards = _card_data()
@@ -194,10 +286,10 @@
     """Score an in-play Pokemon as an immediate Active attacker."""
     if mon is None:
         return -10**9
-    dmg = _best_usable_damage(mon)
+    dmg, discard = _best_usable_attack_eval(mon)
     lethal_bonus = 3000 if opp_active is not None and dmg >= opp_active.hp else 0
     prize_penalty = 120 * _prize_value(mon)
-    return lethal_bonus + dmg * 20 + mon.hp + len(mon.energies) * 15 - prize_penalty
+    return lethal_bonus + dmg * 20 + mon.hp + len(mon.energies) * 15 - discard * 25 - prize_penalty
 
 
 def _ability_cap_reached(state) -> bool:
@@ -258,7 +350,8 @@
 
     # 1. Attack for lethal (engine only lists attacks we have Energy for).
     if OptionType.ATTACK in by_type and opp_active is not None:
-        idx, dmg = _best_attack_index(options, by_type[OptionType.ATTACK])
+        my_active = me.active[0] if me.active else None
+        idx, dmg = _best_attack_index(options, by_type[OptionType.ATTACK], my_active)
         if dmg >= opp_active.hp:
             return [idx]
 
@@ -283,7 +376,8 @@
 
     # 6. Attack anyway with the strongest available attack.
     if OptionType.ATTACK in by_type:
-        idx, _ = _best_attack_index(options, by_type[OptionType.ATTACK])
+        my_active = me.active[0] if me.active else None
+        idx, _ = _best_attack_index(options, by_type[OptionType.ATTACK], my_active)
         return [idx]
 
     # 7. Retreat only if the Active is dying and a stronger Benched Pokémon exists.
@@ -309,7 +403,11 @@
 def _choose_attack(obs: Observation) -> list[int]:
     sel = obs.select
     assert sel is not None
-    idx, _ = _best_attack_index(sel.option, list(range(len(sel.option))))
+    attacker = None
+    if obs.current is not None:
+        me = obs.current.players[obs.current.yourIndex]
+        attacker = me.active[0] if me.active else None
+    idx, _ = _best_attack_index(sel.option, list(range(len(sel.option))), attacker)
     return [idx]
 
 
@@ -462,18 +560,26 @@
 
 def _best_usable_damage(mon) -> int:
     """Highest damage this Pokémon can actually deal right now (cost affordable)."""
+    return _best_usable_attack_eval(mon)[0]
+
+
+def _best_usable_attack_eval(mon):
+    """Highest live attack estimate and its Energy discard burden."""
     if mon is None:
-        return 0
+        return 0, 0
     card = _card_data().get(mon.id)
     if card is None:
-        return 0
+        return 0, 0
     attacks = _attack_data()
-    best = 0
+    best_damage, best_discard, best_score = 0, 0, float("-inf")
     for aid in card.attacks:
         a = attacks.get(aid)
         if a is not None and _can_pay(a.energies, mon.energies):
-            best = max(best, a.damage)
-    return best
+            damage, discard = _attack_damage_and_discard(a, mon)
+            score = damage * 100 - discard * 25
+            if score > best_score:
+                best_damage, best_discard, best_score = damage, discard, score
+    return best_damage, best_discard
 
 
 def _prize_value(mon) -> int:
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.

## Opus Independent Review

Decision: MORE_EVIDENCE. Do not accept yet, and do not authorize deep evaluation
until the trace/estimate concerns below are checked.

Reason:
- The screening result is inconclusive: 107/200 wins, 53.5%, with p=0.3222 and
  a 95% interval that still crosses 50%. This is not acceptance evidence.
- The code is mostly scoped to Mega Charizard X/Y ex. Non-target attacks appear
  to fall back to printed damage, so the broad shared attack ranking is not
  obviously changed for unrelated Pokemon.
- The decision trace is broader than the hypothesis. It shows 24 MAIN
  differences across PLAY, ATTACH, EVOLVE, END, and RETREAT-like sequencing
  effects, not only direct Charizard attack choices. These may be downstream
  consequences of improved Charizard attacker scoring, but the current pack does
  not prove that.
- The damage estimator is safety-relevant because it feeds lethal attack
  selection. Regex/hardcoded estimates for zero-printed Charizard attacks need
  to be checked against actual engine-resolved damage before trusting the
  branch.

Required before proceeding:
- Annotated trace showing whether each of the 24 differences occurred with Mega
  Charizard X/Y ex active, on board, or directly affecting Charizard setup.
- Estimate-vs-actual evidence for encountered Charizard attacks, especially
  lethal decisions.
- A larger fresh-seed run or targeted Charizard mirror only after those cheap
  trace checks confirm the mechanism is really firing.

Audit:
- Full Opus CLI output saved at
  `sub-agents/human-review/pending/Fire-EXP-0003.opus-review.json`.


## Opus Auto Review

Decision: MORE_EVIDENCE.

## MORE_EVIDENCE

I am the correct reviewer here: the candidate was authored by Codex, and I am Opus/Claude, so the cross-family requirement is satisfied. I inspected the code diff, the experiment record, and the raw decision trace directly rather than relying on the summary.

### Why not APPROVE_DEEP_EVALUATION or REJECT

**Screening is statistically inconclusive.** 107/200 (53.5%), 95% CI 46.6%–60.3% (crosses 50%), head-to-head p=0.32 (z=0.99). The smoke run was 11/20. The win-rate evidence carries essentially no weight right now — it neither justifies spending on deep evaluation nor condemns the mechanism.

**The scoping claim is contradicted by the trace itself.** The hypothesis is "for Mega Charizard X/Y ex only … preserve all other attack logic," and the code path is guarded by `_is_target_charizard` (non-target attacks return `discard=0`, so `score = dmg*100` preserves the old strict-max ordering). That looks clean in isolation. But the *first* recorded divergence — game 1, step 17, turn 3 — is a `PLAY` vs `PLAY` choice with **Charmander active, Eevee benched, and no Charizard anywhere on either board**. `_best_play_index` was not modified, and as the first divergence the board states should be identical up to that point, so an identical-state PLAY-vs-PLAY split is not explained by the stated Charizard mechanism. This is either a benign downstream ripple or a scoping/determinism leak — and the pack does not distinguish the two. That is exactly the "broader-than-hypothesis footprint" concern, now confirmed on a concrete record rather than asserted.

**The estimator is safety-relevant and unvalidated.** `_charizard_effect_damage_and_discard` derives damage from regex over card text plus hard-coded fallbacks (`fixed=300` for "crimson"/"wild blaze", `per_energy=50` for "inferno x"). This value feeds the **lethal branch** (`dmg >= opp_active.hp`). If it over-reads, the agent commits to a "lethal" the engine resolves as non-lethal — a correctness failure, not a ranking nuance. Nothing in the pack compares these estimates to engine-resolved damage.

### What I need before this proceeds (all cheap, before any larger run)

1. **Annotated trace** classifying each of the 24 diffs by whether a target Charizard is active/benched/being set up — specifically explain the game-1/step-17 no-Charizard PLAY divergence.
2. **Estimate-vs-actual** comparison for every Charizard attack encountered, prioritizing lethal decisions.
3. Only after 1–2 confirm the mechanism is firing as claimed: a fresh-seed larger run and/or a Charizard-inclusive matchup to resolve the inconclusive screening with power.

I did not edit or promote anything. This aligns with the existing Opus CLI review on file, with the added independent finding that the trace's leading divergence occurs with no Charizard in play — which is the single most important thing to explain before this advances.

Audit artifact: `specialists/Fire/experiments/EXP-0003/reviews/screening-opus-auto-review.json`.
