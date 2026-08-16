# Human Review: My_Deck_Grass EXP-0005

## Hypothesis

SelectType.ENERGY falls through _greedy_select's blind else-branch to range(minCount), so all 44 SWITCH_ENERGY selections per 10 games -- every Solar Transfer and Energy Switch SOURCE -- are chosen arbitrarily while Solar Transfer fires 3.6 times per game. Scoring the source by how expendable that Energy is should stop the deck's own energy engine from disarming its ready attacker.

Expected effect: Solar Transfer and Energy Switch take Energy from idle Bench Pokemon and from Pokemon that cannot attack, never from an Active that is currently able to attack, and never the unit that drops a ready attacker below its attack cost.

Mechanisms: energy_source_selection

## Review Assignment

- Implemented by: `claude` (`provider=claude`, `model=default`)
- Assigned reviewer: `codex` (`provider=codex`, `model=gpt-5.5`)
- Reason: Claude/Opus-authored experiments require an independent Codex review.

## Evidence

- Stage: `confirmation`
- Candidate: `283/500` wins (56.6%)
- 95% interval: `52.2% - 60.9%`
- Head-to-head null test: `z=2.95160973029972`, `p=0.003161222020906981`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `16.88 ms / 668.71 ms`

## Cross-Deck Evidence

[
  {
    "status": "complete",
    "opponent": "Hydrapple",
    "opponent_version": "n/a",
    "evidence_kind": "agent_overfit_regression",
    "note": "NOT a matchup_pair deck-vs-deck comparison. This is benchmark_pair.py with the EXP-0005 candidate and the frozen v000-baseline BOTH piloting the opponent specialist's deck, so My_Deck_Grass never enters the game. It measures whether the energy-source policy is overfit to this deck, which is what the operator authorized; a deck-strength matchup was explicitly out of scope for this specialist.",
    "games": 200,
    "wins": 116,
    "losses": 84,
    "draws": 0,
    "win_rate": 0.58,
    "p_value": 0.02365161665535606,
    "result": "results/overfit-regression-Hydrapple.json"
  },
  {
    "status": "complete",
    "opponent": "PalSystem_Dragapult",
    "opponent_version": "n/a",
    "evidence_kind": "agent_overfit_regression",
    "note": "NOT a matchup_pair deck-vs-deck comparison. This is benchmark_pair.py with the EXP-0005 candidate and the frozen v000-baseline BOTH piloting the opponent specialist's deck, so My_Deck_Grass never enters the game. It measures whether the energy-source policy is overfit to this deck, which is what the operator authorized; a deck-strength matchup was explicitly out of scope for this specialist.",
    "games": 200,
    "wins": 113,
    "losses": 87,
    "draws": 0,
    "win_rate": 0.565,
    "p_value": 0.06599205505934778,
    "result": "results/overfit-regression-PalSystem_Dragapult.json"
  }
]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `1682`
- Different choices: `198` (11.8%)
- Games containing a difference: `19`
- Retained records: `198`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 156 |
| SWITCH_ENERGY | 42 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 1 | 4 | MAIN/MAIN | PLAY | PLAY |
| 1 | 68 | MAIN/MAIN | ABILITY | ATTACH |
| 1 | 70 | MAIN/MAIN | ATTACH | RETREAT |
| 1 | 73 | MAIN/MAIN | EVOLVE | RETREAT |
| 1 | 74 | MAIN/MAIN | RETREAT | END |

## Required Human Checks

- Does the diff implement only the stated mechanism?
- Does the observed result justify more evaluation rather than acceptance?
- Could the change affect unrelated selection contexts or deck archetypes?
- Is representative decision-trace evidence required before the next benchmark?

## Agent Diff

```diff
--- baseline/main.py
+++ candidate/main.py
@@ -432,6 +432,85 @@
     return [best_i]
 
 
+class _EnergyView:
+    """Minimal stand-in for a Pokemon with a hypothetical Energy set.
+
+    _best_usable_damage only reads `.id` and `.energies`, so this is enough to ask
+    "could this Pokemon still attack if that Energy left?" without touching live state.
+    """
+
+    __slots__ = ("id", "energies")
+
+    def __init__(self, card_id, energies):
+        self.id = card_id
+        self.energies = energies
+
+
+def _energy_source_score(opt, me) -> int:
+    """Rank one SWITCH_ENERGY / DISCARD_ENERGY source Energy: higher = more expendable.
+
+    This context was previously answered by the blind `range(minCount)` default in
+    _greedy_select, which on this deck means every Solar Transfer and Energy Switch
+    source -- 44 selections per 10 games, with Solar Transfer firing 3.6 times a game --
+    was picked arbitrarily. The whole point of the deck's energy engine is to move Energy
+    ONTO the attacker, so taking it off the attacker is the one outcome that must not
+    happen by accident.
+
+    `opt.count` is documented as the number of Energy UNITS the option corresponds to,
+    which already accounts for Meganium's Wild Growth doubling a Basic {G}.
+    """
+    mon = None
+    if opt.area == AreaType.ACTIVE:
+        mon = me.active[0] if me.active and me.active[0] is not None else None
+    elif opt.area == AreaType.BENCH and opt.index is not None and opt.index < len(me.bench):
+        mon = me.bench[opt.index]
+    if mon is None:
+        return 0
+
+    is_active = opt.area == AreaType.ACTIVE
+    units = opt.count if getattr(opt, "count", None) else 1
+    before = _best_usable_damage(mon)
+
+    # What this Pokemon could still do without the Energy being taken.
+    remaining = list(mon.energies)
+    drop = mon.energies[opt.energyIndex] if (
+        opt.energyIndex is not None and opt.energyIndex < len(mon.energies)
+    ) else None
+    for _ in range(units):
+        if drop is not None and drop in remaining:
+            remaining.remove(drop)
+        elif remaining:
+            remaining.pop()
+    after = _best_usable_damage(_EnergyView(mon.id, remaining))
+
+    score = len(mon.energies) * 10          # a bigger pile has more to spare
+    if not is_active:
+        score += 300                        # Bench Energy is idle by default
+    if before <= 0:
+        score += 200                        # this Pokemon cannot attack either way
+    if before > 0 and after <= 0:
+        score -= 400                        # taking this disarms a ready attacker
+    if is_active and before > 0:
+        score -= 600                        # never disarm the Active
+    return score
+
+
+def _choose_energy(obs: Observation) -> list[int]:
+    """Pick which attached Energy to move/discard, most expendable first."""
+    sel = obs.select
+    assert sel is not None
+    state = obs.current
+    if state is None:
+        return list(range(sel.minCount))
+    me = state.players[state.yourIndex]
+    ranked = sorted(
+        range(len(sel.option)),
+        key=lambda i: _energy_source_score(sel.option[i], me),
+        reverse=True,
+    )
+    return ranked[: max(sel.minCount, 1)]
+
+
 def _clamp(idx_list, sel, n_options):
     """Enforce minCount <= len <= maxCount, no duplicates, valid range."""
     idx_list = [i for i in dict.fromkeys(idx_list) if 0 <= i < n_options]
@@ -464,8 +543,10 @@
         idx_list = _choose_yes_no(obs)
     elif sel.type == SelectType.COUNT:
         idx_list = _choose_count(obs)
+    elif sel.type == SelectType.ENERGY:
+        idx_list = _choose_energy(obs)
     else:
-        # ENERGY, SKILL, SPECIAL_CONDITION, and any future types: safe minimal default.
+        # SKILL, SPECIAL_CONDITION, and any future types: safe minimal default.
         idx_list = list(range(sel.minCount))
 
     return _clamp(idx_list, sel, len(options))
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.
