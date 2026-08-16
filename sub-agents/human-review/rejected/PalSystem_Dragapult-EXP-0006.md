# Human Review: PalSystem_Dragapult EXP-0006

## Hypothesis

For this deck's MAIN-phase Trainer choices only, delay Unfair Stamp, Judge, Boss's Orders, Crushing Hammer, and Jamming Tower unless their current board-state effect is materially useful, while preserving the shipped play ranking for all other Trainers and decks.

Expected effect: Reduce low-value disruption plays and retain timing-sensitive cards for turns where they create prize or tempo advantage.

Mechanisms: dragapult_disruption_timing

## Review Assignment

- Implemented by: `codex` (`provider=codex`, `model=gpt-5.5`)
- Assigned reviewer: `opus` (`provider=claude`, `model=opus`)
- Reason: Codex-authored experiments require an independent Opus/Claude review.

## Evidence

- Stage: `screening`
- Candidate: `107/200` wins (53.5%)
- 95% interval: `46.6% - 60.3%`
- Head-to-head null test: `z=0.9899494936611675`, `p=0.3221988061625811`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `8.61 ms / 201.80 ms`

## Cross-Deck Evidence

[]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `2134`
- Different choices: `137` (6.4%)
- Games containing a difference: `19`
- Retained records: `137`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 137 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 1 | 14 | MAIN/MAIN | PLAY | PLAY |
| 1 | 15 | MAIN/MAIN | PLAY | EVOLVE |
| 1 | 20 | MAIN/MAIN | PLAY | RETREAT |
| 1 | 38 | MAIN/MAIN | PLAY | PLAY |
| 1 | 98 | MAIN/MAIN | PLAY | PLAY |

## Required Human Checks

- Does the diff implement only the stated mechanism?
- Does the observed result justify more evaluation rather than acceptance?
- Could the change affect unrelated selection contexts or deck archetypes?
- Is representative decision-trace evidence required before the next benchmark?

## Agent Diff

```diff
--- baseline/main.py
+++ candidate/main.py
@@ -34,6 +34,15 @@
 ABILITY_CAP_PER_TURN = 4    # see _ability_cap_reached: guards against unbounded Abilities
 _live_ability_count: dict = {}
 _last_seen_turn = -1
+
+_DRAGAPULT_MARKERS = ("dragapult ex", "dreepy", "drakloak")
+_TIMING_TRAINERS = (
+    "unfair stamp",
+    "judge",
+    "boss's orders",
+    "crushing hammer",
+    "jamming tower",
+)
 
 
 def _card_data():
@@ -106,6 +115,36 @@
 
 def _option_card_power(opt):
     return _card_power(opt.cardId) if opt.cardId is not None else 0
+
+
+def _card_name(card_id) -> str:
+    card = _card_data().get(card_id)
+    if card is None:
+        return ""
+    for attr in ("name", "cardName", "label"):
+        name = getattr(card, attr, None)
+        if name:
+            return str(name)
+    return ""
+
+
+def _norm_name(name: str) -> str:
+    return name.replace("\u2019", "'").lower()
+
+
+def _is_dragapult_deck() -> bool:
+    names = [_norm_name(_card_name(card_id)) for card_id in set(_my_deck_ids())]
+    return all(any(marker in name for name in names) for marker in _DRAGAPULT_MARKERS)
+
+
+def _timing_trainer_name(opt):
+    name = _norm_name(_card_name(opt.cardId))
+    if not name:
+        return None
+    for trainer in _TIMING_TRAINERS:
+        if trainer in name:
+            return trainer
+    return None
 
 
 def _best_card_option(options, indices, reverse=True):
@@ -484,6 +523,84 @@
     return 3 if card.megaEx else 2 if card.ex else 1
 
 
+def _all_in_play(player):
+    mons = []
+    if player.active and player.active[0] is not None:
+        mons.append(player.active[0])
+    mons.extend(player.bench)
+    return mons
+
+
+def _attached_card_ids(mon) -> list[int]:
+    ids = []
+    for attr in ("attachedCards", "attached", "attachments", "tools", "tool", "pokemonTools"):
+        value = getattr(mon, attr, None)
+        if value is None:
+            continue
+        values = value if isinstance(value, (list, tuple)) else [value]
+        for item in values:
+            if isinstance(item, int):
+                ids.append(item)
+            else:
+                card_id = getattr(item, "cardId", getattr(item, "id", None))
+                if isinstance(card_id, int):
+                    ids.append(card_id)
+    return ids
+
+
+def _has_tool_attached(mon) -> bool:
+    for card_id in _attached_card_ids(mon):
+        name = _norm_name(_card_name(card_id))
+        card = _card_data().get(card_id)
+        trainer_type = _norm_name(str(getattr(card, "trainerType", ""))) if card else ""
+        if "tool" in name or "tool" in trainer_type:
+            return True
+    return False
+
+
+def _boss_orders_useful(me, opp) -> bool:
+    if not opp.bench:
+        return False
+    my_active = me.active[0] if me.active else None
+    opp_active = opp.active[0] if opp.active else None
+    active_power = _card_power(opp_active.id) if opp_active is not None else 0
+    available_damage = _best_usable_damage(my_active)
+    for target in opp.bench:
+        if available_damage and target.hp <= available_damage:
+            return True
+        if target.hp <= 60 and target.hp < (opp_active.hp if opp_active is not None else 10**9):
+            return True
+        if _card_power(target.id) >= active_power + 160:
+            return True
+    return False
+
+
+def _timing_trainer_useful(trainer: str, obs: Observation) -> bool:
+    state = obs.current
+    if state is None:
+        return True
+    me = state.players[state.yourIndex]
+    opp = state.players[1 - state.yourIndex]
+    if trainer == "boss's orders":
+        return _boss_orders_useful(me, opp)
+    if trainer == "crushing hammer":
+        return any(getattr(mon, "energies", None) for mon in _all_in_play(opp))
+    if trainer == "judge":
+        return opp.handCount >= 5 and (opp.handCount - me.handCount >= 2 or me.handCount <= 4)
+    if trainer == "unfair stamp":
+        return opp.handCount > 2 or me.handCount < 5
+    if trainer == "jamming tower":
+        return any(_has_tool_attached(mon) for mon in _all_in_play(opp))
+    return True
+
+
+def _delay_low_value_timing_trainer(opt, obs: Observation) -> bool:
+    if not _is_dragapult_deck() or opt.type != OptionType.PLAY:
+        return False
+    trainer = _timing_trainer_name(opt)
+    return trainer is not None and not _timing_trainer_useful(trainer, obs)
+
+
 def _eval_state(state, my_index: int) -> float:
     """Score a board from my_index's perspective.
 
@@ -596,6 +713,8 @@
         for i in range(len(sel.option)):
             if ability_capped and sel.option[i].type == OptionType.ABILITY:
                 continue  # per-turn cap already used; don't let search re-pick it
+            if _delay_low_value_timing_trainer(sel.option[i], obs):
+                continue
             choice = _clamp([i], sel, len(sel.option))
             score = _rollout_score(choice, obs, my_index, my_deck, opp_deck)
             if score > best_score:
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.


## Opus Auto Review

Decision: MORE_EVIDENCE.

**MORE_EVIDENCE**

I'm Opus reviewing a Codex-authored candidate (`provider=codex`, `model=gpt-5.5`) — the cross-family assignment is correct, so I can proceed.

## Reasoning

**The statistical evidence does not justify acceptance, and the trace does not confirm the mechanism.** Both need to be addressed before spending deep-eval compute, so I'm not approving yet — but the implementation is clean enough that outright rejection is premature.

### 1. Win-rate is statistically indistinguishable from noise
- 107/200 = 53.5%, 95% CI **46.6% – 60.3%** — the interval straddles 50%.
- Head-to-head null test: **p = 0.322** (z ≈ 0.99). This is a non-result. At screening this can still gate forward, but nothing here demonstrates a real effect yet; a single fresh-seed run could easily land at ≤50%.

### 2. The trace does not verify the claimed mechanism
This is the core of my job, and the pack doesn't let me do it. The mechanism only *removes* timing-trainer PLAY options from search (`continue`). If it were firing as claimed, I'd expect to see the **candidate choosing a non-PLAY where the baseline played a timing Trainer**. Instead the representative rows show the opposite/unrelated shape:

- G1/15: candidate **PLAY** vs baseline **EVOLVE**
- G1/20: candidate **PLAY** vs baseline **RETREAT**

These are consistent with **cascade divergence** — once one early decision differs, the two games walk different trajectories and every later "difference" is just a different board state, not the mechanism firing. With 137 diffs across 19 of 20 games from a single skipped option per game, that's exactly what I'd expect. The table also has **no card-level detail**, so I cannot confirm the delayed cards were actually Unfair Stamp / Judge / Boss's Orders / Crushing Hammer / Jamming Tower, nor that the "useful" heuristics gated correctly.

### 3. Scoping looks correct, but downstream reach is unverified
Positives: the change is gated to `OptionType.PLAY`, guarded by `_is_dragapult_deck()` (requires all three markers), and only Trainers can be played in MAIN so the "MAIN-phase only" claim holds structurally. The `unfair stamp` / boss heuristics are conservative. But because skipping an option reshapes the whole rollout, I can't rule out that it perturbs unrelated selection contexts within the Dragapult deck — the trace as presented can't distinguish "narrow mechanism + cascade" from "broader behavior change."

## What I need

1. **A mechanism-level trace**: decisions filtered to contexts where a timing Trainer was a legal PLAY, showing candidate-delayed vs baseline-played **with card names**, to confirm `_timing_trainer_useful` gates on the intended five cards and nothing else.
2. **A fresh-seed replication** (independent seeds), since p = 0.322 is currently indistinguishable from noise.
3. Preferably an **ablation** isolating the delay logic (e.g., each of the five Trainers toggled) so the effect can be attributed rather than inferred.

I am not editing files or promoting anything.

Audit artifact: `specialists/PalSystem_Dragapult/experiments/EXP-0006/reviews/screening-opus-auto-review.json`.
