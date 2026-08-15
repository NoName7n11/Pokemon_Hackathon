# Human Review: PalSystem_Dragapult EXP-0005

## Hypothesis

For Munkidori Adrena-Brain selections only, move damage counters from the most strategically endangered friendly Pokemon to an opposing Pokemon where the moved damage secures a knockout or creates the strongest live-HP prize setup; do not alter generic Ability choice or unrelated damage-counter selection.

Expected effect: Turn existing self-damage into prize pressure while improving survival of prepared Dragapult attackers.

Mechanisms: munkidori_adrena_brain_damage_transfer

## Review Assignment

- Implemented by: `codex` (`provider=codex`, `model=gpt-5.5`)
- Assigned reviewer: `opus` (`provider=claude`, `model=opus`)
- Reason: Codex-authored experiments require an independent Opus/Claude review.

## Evidence

- Stage: `screening`
- Candidate: `122/200` wins (61.0%)
- 95% interval: `54.1% - 67.5%`
- Head-to-head null test: `z=3.1112698372208087`, `p=0.001862846297981894`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `9.34 ms / 453.11 ms`

## Cross-Deck Evidence

[]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `1939`
- Different choices: `152` (7.8%)
- Games containing a difference: `20`
- Retained records: `152`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 152 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 1 | 36 | MAIN/MAIN | ATTACH | RETREAT |
| 1 | 37 | MAIN/MAIN | EVOLVE | RETREAT |
| 1 | 41 | MAIN/MAIN | PLAY | PLAY |
| 1 | 65 | MAIN/MAIN | PLAY | PLAY |
| 1 | 102 | MAIN/MAIN | ATTACH | PLAY |

## Required Human Checks

- Does the diff implement only the stated mechanism?
- Does the observed result justify more evaluation rather than acceptance?
- Could the change affect unrelated selection contexts or deck archetypes?
- Is representative decision-trace evidence required before the next benchmark?

## Agent Diff

```diff
--- baseline/main.py
+++ candidate/main.py
@@ -19,6 +19,8 @@
 _CARD_DATA = None
 _ATTACK_DATA = None
 _MY_DECK = None
+_ADRENA_BRAIN_CARD_IDS = {235}
+_adrena_brain_pending_card_choices = 0
 
 # MAIN-phase 1-ply lookahead config.
 SEARCH_MAIN = True          # MAIN-phase 1-ply lookahead. MEASURED (Hydrapple deck,
@@ -154,6 +156,84 @@
     else:
         live_pressure = damage_taken * 20 - pokemon.hp * 10
     return lethal_bonus + active_bonus + live_pressure + static_threat + prize_value * 1000
+
+
+def _adrena_brain_source_score(opt, obs):
+    """Prefer rescuing damaged, strategically valuable friendly Pokemon."""
+    state = obs.current
+    if state is None:
+        return _option_card_power(opt)
+    pokemon = _option_pokemon(opt, state)
+    if pokemon is None:
+        return _option_card_power(opt)
+    damage_taken = max(0, pokemon.maxHp - pokemon.hp)
+    low_hp_bonus = max(0, 90 - pokemon.hp) * 40
+    ko_save_bonus = 3000 if pokemon.hp <= 30 else 0
+    attacker_value = _best_usable_damage(pokemon) * 20 + len(pokemon.energies) * 80
+    active_bonus = 300 if opt.area == AreaType.ACTIVE else 0
+    return (
+        damage_taken * 70
+        + low_hp_bonus
+        + ko_save_bonus
+        + attacker_value
+        + _prize_value(pokemon) * 900
+        + active_bonus
+        + _card_power(pokemon.id)
+    )
+
+
+def _adrena_brain_target_score(opt, obs):
+    """Place moved counters where 30 damage converts or best sets up prizes."""
+    state = obs.current
+    if state is None:
+        return _option_card_power(opt)
+    pokemon = _option_pokemon(opt, state)
+    if pokemon is None:
+        return _option_card_power(opt)
+    sel = obs.select
+    moved_damage = 30
+    if sel is not None and getattr(sel, "remainDamageCounter", None) is not None:
+        moved_damage = min(30, sel.remainDamageCounter * 10)
+    prize_value = _prize_value(pokemon)
+    damage_taken = max(0, pokemon.maxHp - pokemon.hp)
+    remaining_after = max(0, pokemon.hp - moved_damage)
+    lethal_bonus = 120000 * prize_value if remaining_after == 0 else 0
+    setup_bonus = max(0, 80 - remaining_after) * 60
+    active_bonus = 1200 if opt.area == AreaType.ACTIVE else 0
+    return (
+        lethal_bonus
+        + setup_bonus
+        + damage_taken * 30
+        - remaining_after * 20
+        + active_bonus
+        + prize_value * 1200
+        + _card_power(pokemon.id)
+    )
+
+
+def _choose_adrena_brain_damage_transfer(obs: Observation, indices: list[int]):
+    global _adrena_brain_pending_card_choices
+    state = obs.current
+    if state is None:
+        return None
+    own_indices = [
+        i for i in indices
+        if obs.select.option[i].playerIndex == state.yourIndex
+        and _option_pokemon(obs.select.option[i], state) is not None
+    ]
+    opp_indices = [
+        i for i in indices
+        if obs.select.option[i].playerIndex is not None
+        and obs.select.option[i].playerIndex != state.yourIndex
+        and _option_pokemon(obs.select.option[i], state) is not None
+    ]
+    if own_indices and not opp_indices:
+        _adrena_brain_pending_card_choices = max(0, _adrena_brain_pending_card_choices - 1)
+        return sorted(own_indices, key=lambda i: _adrena_brain_source_score(obs.select.option[i], obs), reverse=True)
+    if opp_indices:
+        _adrena_brain_pending_card_choices = max(0, _adrena_brain_pending_card_choices - 1)
+        return sorted(opp_indices, key=lambda i: _adrena_brain_target_score(obs.select.option[i], obs), reverse=True)
+    return None
 
 
 def _best_attach_index(options, indices, me):
@@ -345,7 +425,14 @@
         if opponent_indices:
             indices = opponent_indices
 
-    if sel.context in opponent_target_contexts:
+    if (
+        _adrena_brain_pending_card_choices > 0
+        and sel.context in (SelectContext.DAMAGE_COUNTER, SelectContext.DAMAGE_COUNTER_ANY)
+    ):
+        ranked = _choose_adrena_brain_damage_transfer(obs, list(range(len(options))))
+        if ranked is None:
+            ranked = sorted(indices, key=lambda i: _target_score(options[i], obs), reverse=True)
+    elif sel.context in opponent_target_contexts:
         ranked = sorted(indices, key=lambda i: _target_score(options[i], obs), reverse=True)
     else:
         reverse = sel.context not in weakest_first_contexts
@@ -659,9 +746,16 @@
 def _record_if_ability(obs: Observation, chosen: list[int]) -> None:
     """If the action actually being returned to the engine is ABILITY, count
     it against the per-turn cap (see _record_ability_use)."""
+    global _adrena_brain_pending_card_choices
     if not chosen or obs.current is None:
         return
     i = chosen[0]
     options = obs.select.option if obs.select else []
     if 0 <= i < len(options) and options[i].type == OptionType.ABILITY:
+        opt = options[i]
+        pokemon = _option_pokemon(opt, obs.current)
+        if opt.cardId in _ADRENA_BRAIN_CARD_IDS or (pokemon is not None and pokemon.id in _ADRENA_BRAIN_CARD_IDS):
+            _adrena_brain_pending_card_choices = 2
+        else:
+            _adrena_brain_pending_card_choices = 0
         _record_ability_use(obs.current)
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.


## Opus Auto Review

Decision: REJECT.

## REJECT

I verified the pack against the actual candidate code, the trace records, and the live board states. This experiment should be rejected — the implemented mechanism is not the one the hypothesis claims, and the evidence never shows the claimed mechanism acting.

### Decisive finding: the code keys on the wrong card

The hypothesis is explicitly about **Munkidori Adrena-Brain**. But the gate is:

```python
_ADRENA_BRAIN_CARD_IDS = {235}
```

and the trace's own board state (`decision-trace-screening.json`, game 1 step 36) shows:

- `card_id: 235` → **"Budew"**
- `card_id: 112` → **"Munkidori"**

So the entire trigger (`_record_if_ability` setting `_adrena_brain_pending_card_choices = 2` when `opt.cardId in _ADRENA_BRAIN_CARD_IDS` / `pokemon.id == 235`) fires on **Budew**, never on Munkidori (112). The damage-transfer re-ranking the hypothesis describes is wired to the wrong Pokemon. Whatever the 61% is measuring, it is **not** "Munkidori Adrena-Brain damage transfer." This fails the core review requirement — confirm the evidence matches the claimed mechanism — outright.

### The trace independently confirms the mechanism never fires

All 152 differences are classified `MAIN`, and every option-type in the summary is PLAY/ATTACH/EVOLVE/ABILITY/RETREAT/ATTACK/END — **zero `DAMAGE_COUNTER` selections**. The representative diffs (step 36: candidate ATTACH vs baseline RETREAT; step 37: EVOLVE vs RETREAT) are ordinary main-phase choices, i.e. pure downstream state drift once games diverge. We cannot observe a single damage-counter transfer, so there is no evidence connecting the win-rate delta to the stated mechanism. This is the same failure mode that already got EXP-0004 rejected in this campaign.

### Secondary concern (would matter even if the card ID were fixed)

`_adrena_brain_pending_card_choices` is a module-global set to `2` and decremented on any subsequent `DAMAGE_COUNTER`/`DAMAGE_COUNTER_ANY` selection. If the triggering ability produces fewer than two counter selections (or an interleaving effect resolves first), the leftover pending count leaks into the **next, unrelated** damage-counter selection and routes it through the Adrena-Brain scorer. That directly violates the hypothesis's "do not alter unrelated damage-counter selection" scope guarantee. It's a latent correctness bug independent of the win rate.

### Why REJECT rather than MORE_EVIDENCE

This isn't a measurement gap that another trace or fresh-seed run would resolve — the mechanism is bound to the wrong card ID, so a re-run would still not exercise Munkidori. The screening number (122/200, p=0.0019) is real but unattributable to the claimed change; it is confounded by acting on Budew and by state drift. The author needs to fix the card mapping (Munkidori = 112), close the global-state leak, and produce a trace that actually shows Adrena-Brain source→target transfers before this deserves evaluation budget.

Assignment check: implemented by Codex/gpt-5.5, reviewed here by Opus/Claude — cross-family rule satisfied. I did not edit the candidate, run promotion, or modify any files.

Audit artifact: `specialists/PalSystem_Dragapult/experiments/EXP-0005/reviews/screening-opus-auto-review.json`.
