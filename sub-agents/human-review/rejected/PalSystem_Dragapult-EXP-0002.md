# Human Review: PalSystem_Dragapult EXP-0002

## Hypothesis

During MAIN-phase evolution ordering, when a Drakloak can use Recon Directive and can also evolve into Dragapult ex, use that Drakloak's draw Ability before evolving it; preserve the existing evolve and Ability ordering for every other Pokemon and when Recon Directive is unavailable or already used.

Expected effect: Gain the Drakloak draw opportunity that the generic evolve-before-Ability policy currently discards, without changing unrelated evolution lines or globally raising Ability priority.

Mechanisms: drakloak_recon_before_evolution

## Review Assignment

- Implemented by: `codex` (`provider=codex`, `model=gpt-5.5`)
- Assigned reviewer: `opus` (`provider=claude`, `model=opus`)
- Reason: Codex-authored experiments require an independent Opus/Claude review.

## Evidence

- Stage: `screening`
- Candidate: `91/200` wins (45.5%)
- 95% interval: `38.7% - 52.4%`
- Head-to-head null test: `z=-1.272792206135785`, `p=0.2030917875771681`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `8.27 ms / 300.36 ms`

## Cross-Deck Evidence

[]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `1975`
- Different choices: `135` (6.8%)
- Games containing a difference: `20`
- Retained records: `135`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 135 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 1 | 18 | MAIN/MAIN | ATTACH | PLAY |
| 1 | 34 | MAIN/MAIN | PLAY | PLAY |
| 1 | 36 | MAIN/MAIN | PLAY | ATTACH |
| 1 | 38 | MAIN/MAIN | ATTACH | ATTACH |
| 1 | 39 | MAIN/MAIN | PLAY | RETREAT |

## Required Human Checks

- Does the diff implement only the stated mechanism?
- Does the observed result justify more evaluation rather than acceptance?
- Could the change affect unrelated selection contexts or deck archetypes?
- Is representative decision-trace evidence required before the next benchmark?

## Agent Diff

```diff
--- baseline/main.py
+++ candidate/main.py
@@ -112,6 +112,11 @@
     return sorted(indices, key=lambda i: _option_card_power(options[i]), reverse=reverse)[0]
 
 
+def _card_name(card_id) -> str:
+    card = _card_data().get(card_id)
+    return (getattr(card, "name", "") or "").lower()
+
+
 def _option_pokemon(opt, state):
     if opt.playerIndex is None or opt.area is None or opt.index is None:
         return None
@@ -122,6 +127,66 @@
         return player.active[0] if player.active and player.active[0] is not None else None
     if opt.area == AreaType.BENCH and opt.index < len(player.bench):
         return player.bench[opt.index]
+    return None
+
+
+def _option_source_key(opt):
+    area = getattr(opt, "inPlayArea", None)
+    index = getattr(opt, "inPlayIndex", None)
+    if area is None:
+        area = getattr(opt, "area", None)
+    if index is None:
+        index = getattr(opt, "index", None)
+    if area is None:
+        return None
+    if area == AreaType.ACTIVE:
+        index = 0
+    if index is None:
+        return None
+    return (area, index)
+
+
+def _option_source_pokemon(opt, me):
+    key = _option_source_key(opt)
+    if key is None:
+        return None
+    area, index = key
+    if area == AreaType.ACTIVE:
+        return me.active[0] if me.active and me.active[0] is not None else None
+    if area == AreaType.BENCH and index < len(me.bench):
+        return me.bench[index]
+    return None
+
+
+def _is_drakloak_recon_option(opt, me) -> bool:
+    source = _option_source_pokemon(opt, me)
+    source_name = _card_name(source.id) if source is not None else _card_name(getattr(opt, "cardId", None))
+    if "drakloak" not in source_name:
+        return False
+    ability_text = " ".join(
+        str(getattr(opt, attr, "") or "")
+        for attr in ("abilityName", "name", "label", "text")
+    ).lower()
+    return "recon directive" in ability_text or not ability_text
+
+
+def _drakloak_recon_before_evolution_index(options, by_type, me):
+    if OptionType.ABILITY not in by_type or OptionType.EVOLVE not in by_type:
+        return None
+
+    dragapult_evolve_keys = set()
+    for i in by_type[OptionType.EVOLVE]:
+        if "dragapult" in _card_name(options[i].cardId):
+            key = _option_source_key(options[i])
+            if key is not None:
+                dragapult_evolve_keys.add(key)
+
+    if not dragapult_evolve_keys:
+        return None
+
+    for i in by_type[OptionType.ABILITY]:
+        if _option_source_key(options[i]) in dragapult_evolve_keys and _is_drakloak_recon_option(options[i], me):
+            return i
     return None
 
 
@@ -262,31 +327,38 @@
         if dmg >= opp_active.hp:
             return [idx]
 
-    # 2. Evolve — free stat upgrade, no downside.
+    # 2. Use Drakloak's Recon Directive before evolving that same Pokemon into
+    # Dragapult, preserving the generic ordering for all other evolution lines.
+    if not _ability_cap_reached(state):
+        recon_idx = _drakloak_recon_before_evolution_index(options, by_type, me)
+        if recon_idx is not None:
+            return [recon_idx]
+
+    # 3. Evolve — free stat upgrade, no downside.
     if OptionType.EVOLVE in by_type:
         return [_best_card_option(options, by_type[OptionType.EVOLVE])]
 
-    # 3. Attach Energy if we haven't this turn.
+    # 4. Attach Energy if we haven't this turn.
     if OptionType.ATTACH in by_type and not state.energyAttached:
         return [_best_attach_index(options, by_type[OptionType.ATTACH], me)]
 
-    # 4. Develop the board: play the strongest Basic to Bench while there's room.
+    # 5. Develop the board: play the strongest Basic to Bench while there's room.
     if OptionType.PLAY in by_type and len(me.bench) < me.benchMax:
         play_idx = _best_play_index(options, by_type[OptionType.PLAY], me)
         if play_idx is not None:
             return [play_idx]
 
-    # 5. Use an Ability if one is available (capped per real turn, see
+    # 6. Use an Ability if one is available (capped per real turn, see
     # _ability_cap_reached).
     if OptionType.ABILITY in by_type and not _ability_cap_reached(state):
         return [by_type[OptionType.ABILITY][0]]
 
-    # 6. Attack anyway with the strongest available attack.
+    # 7. Attack anyway with the strongest available attack.
     if OptionType.ATTACK in by_type:
         idx, _ = _best_attack_index(options, by_type[OptionType.ATTACK])
         return [idx]
 
-    # 7. Retreat only if the Active is dying and a stronger Benched Pokémon exists.
+    # 8. Retreat only if the Active is dying and a stronger Benched Pokémon exists.
     # ponytail: deliberately the simple pre-2026-08-08 rule. A tactical
     # "retreat to a better attacker" gate was built and ABLATED to exactly zero
     # (retreat_ablation.py: card_off 62.4% vs neither 62.8%, n=500/arm) — attacker
@@ -299,7 +371,7 @@
             if low_hp and any(b.hp > my_active.hp for b in me.bench):
                 return [by_type[OptionType.RETREAT][0]]
 
-    # 8. Nothing useful left to do.
+    # 9. Nothing useful left to do.
     if OptionType.END in by_type:
         return [by_type[OptionType.END][0]]
 
@@ -590,6 +662,12 @@
     my_index = obs.current.yourIndex
     opp_deck = my_deck  # mirror opponent (irrelevant during my own turn)
     ability_capped = _ability_cap_reached(obs.current)
+    if not ability_capped:
+        me = obs.current.players[my_index]
+        by_type = _group_by_type(sel.option)
+        recon_idx = _drakloak_recon_before_evolution_index(sel.option, by_type, me)
+        if recon_idx is not None:
+            return _clamp([recon_idx], sel, len(sel.option))
 
     try:
         best_i, best_score = None, float("-inf")
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.


## Opus Auto Review

Decision: REJECT.

REJECT

## Reasoning

**Recommendation: REJECT** (do not authorize deep evaluation; I am not editing or promoting anything).

I'm the correctly-assigned reviewer here: the candidate was implemented by Codex (`gpt-5.5`), and I'm Opus/Claude, so the cross-family independence rule is satisfied.

**1. The evidence shows no benefit — the point estimate is on the losing side.**
- 91/200 = **45.5%** wins, 95% CI **38.7%–52.4%**, head-to-head **z = −1.27, p = 0.20**.
- This does not merely "fail to prove improvement" — the best point estimate is *below* even parity, and the null of no-difference is not rejected. Screening exists to filter for candidates that look better; this one trends worse and is statistically inconclusive.
- The hypothesis claims a **strictly free extra draw** (recovering a discarded Drakloak Recon Directive before evolving). A genuinely free card-draw that nets a 45.5% win rate is a red flag: either the mechanism isn't actually cost-free in this engine (deck-out / ability-cap interactions), or trajectory noise dominates any gain. Nothing here justifies spending deep-evaluation budget.

**2. The trace contradicts the mechanism's core containment claim.**
The hypothesis promises the change happens only in the Recon-before-Dragapult-evolve window, "without changing unrelated selection contexts." But the trace's own breakdown of the 135 divergences is overwhelmingly in *other* contexts:
- Candidate-selected differing types: **PLAY 78, ATTACH 19**, ABILITY 18, EVOLVE 11, RETREAT 5, END 3, ATTACK 1.

So only ~13% of divergences are the ABILITY/EVOLVE decisions the mechanism is supposed to touch; ~74% are PLAY/ATTACH/RETREAT/END. These are cascade effects — drawing extra cards reshuffles the whole hand and downstream turn — which is expected, but it means the evidence does **not** cleanly attribute the outcome to the stated mechanism, and the "no unrelated contexts changed" claim is empirically false. The representative rows (ATTACH↔PLAY, PLAY↔ATTACH, PLAY↔RETREAT) confirm the visible diffs are downstream drift, not the Recon-before-evolve choice itself.

**3. Latent code over-trigger.** `_is_drakloak_recon_option` returns `True` when the ability text is empty (`"recon directive" in ability_text or not ability_text`). The "only Recon Directive" guarantee is therefore not enforced by the code — it relies on the assumption that Drakloak's sole ability is Recon Directive. Not a blocker on its own, but it undermines the "surgical, one-mechanism" framing.

**Bottom line:** below-50% point estimate, no significant signal, and a trace that shows the effect is diffuse cascade rather than the claimed narrow mechanism. That combination does not justify deep evaluation.

If the author wants to revisit rather than close it outright, the bar would be a fresh-seed run showing a clear >50% trend **plus** an ablation isolating just the ABILITY-before-EVOLVE decisions to prove those are the driver — but on the current pack, REJECT.

Audit artifact: `specialists/PalSystem_Dragapult/experiments/EXP-0002/reviews/screening-opus-auto-review.json`.
