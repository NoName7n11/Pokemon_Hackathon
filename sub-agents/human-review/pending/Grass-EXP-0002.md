# Human Review: Grass EXP-0002

## Hypothesis

When evolving the Chikorita line and no Wild Growth Meganium is already in play, prioritize establishing Meganium card 710 before competing Mega Meganium endpoints; preserve evolution ranking after the energy engine exists.

Expected effect: Establish Grass Energy doubling earlier and reduce expensive attackers stranded without usable Energy.

Mechanisms: wild_growth_engine_priority

## Evidence

- Stage: `screening`
- Candidate: `110/200` wins (55.0%)
- 95% interval: `48.1% - 61.7%`
- Head-to-head null test: `z=1.4142135623730963`, `p=0.15729920705028475`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `7.16 ms / 250.91 ms`

## Cross-Deck Evidence

[]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `1099`
- Different choices: `39` (3.5%)
- Games containing a difference: `12`
- Retained records: `39`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 39 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 1 | 12 | MAIN/MAIN | ATTACH | PLAY |
| 1 | 15 | MAIN/MAIN | RETREAT | PLAY |
| 3 | 5 | MAIN/MAIN | PLAY | PLAY |
| 6 | 23 | MAIN/MAIN | ABILITY | PLAY |
| 6 | 24 | MAIN/MAIN | EVOLVE | PLAY |

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
+# EXP-0002 wild_growth_engine_priority: card 710 is the Meganium whose Wild Growth
+# Ability doubles Grass Energy. The deck also carries competing "Mega Meganium"
+# endpoints that _card_power ranks higher, so the default strongest-first evolve
+# ranking always reaches for the Mega before the energy engine exists. Hypothesis:
+# when NO Wild Growth Meganium is already in play, establish card 710 first so the
+# Energy engine is online before expensive attackers land; once one is in play,
+# fall back to the normal ranking unchanged.
+WILD_GROWTH_ENGINE_ID = 710
 
 
 def _card_data():
@@ -110,6 +119,28 @@
 
 def _best_card_option(options, indices, reverse=True):
     return sorted(indices, key=lambda i: _option_card_power(options[i]), reverse=reverse)[0]
+
+
+def _wild_growth_in_play(state) -> bool:
+    """True if a Wild Growth Meganium (card 710) is already one of my in-play
+    Pokemon (Active or Bench)."""
+    if state is None:
+        return False
+    me = state.players[state.yourIndex]
+    mons = ([me.active[0]] if me.active and me.active[0] is not None else []) + list(me.bench)
+    return any(m is not None and m.id == WILD_GROWTH_ENGINE_ID for m in mons)
+
+
+def _prioritized_evolve_index(options, indices, state):
+    """Pick an evolve target. When no Wild Growth Meganium (card 710) is in play
+    yet, establish the Energy engine first if evolving into it is an option;
+    otherwise keep the default strongest-resulting-card ranking (which also
+    applies unchanged once the engine exists)."""
+    if not _wild_growth_in_play(state):
+        engine = [i for i in indices if options[i].cardId == WILD_GROWTH_ENGINE_ID]
+        if engine:
+            return engine[0]
+    return _best_card_option(options, indices)
 
 
 def _option_pokemon(opt, state):
@@ -262,9 +293,11 @@
         if dmg >= opp_active.hp:
             return [idx]
 
-    # 2. Evolve — free stat upgrade, no downside.
+    # 2. Evolve — free stat upgrade, no downside. Establish the Wild Growth
+    # Energy engine (card 710) before competing Mega endpoints when none is yet
+    # in play (see _prioritized_evolve_index / EXP-0002).
     if OptionType.EVOLVE in by_type:
-        return [_best_card_option(options, by_type[OptionType.EVOLVE])]
+        return [_prioritized_evolve_index(options, by_type[OptionType.EVOLVE], state)]
 
     # 3. Attach Energy if we haven't this turn.
     if OptionType.ATTACH in by_type and not state.energyAttached:
@@ -314,10 +347,11 @@
 
 
 def _choose_evolve(obs: Observation) -> list[int]:
-    """Prefer evolving into the strongest resulting card."""
+    """Prefer evolving into the strongest resulting card, but establish the Wild
+    Growth Energy engine (card 710) first when none is in play (EXP-0002)."""
     sel = obs.select
     assert sel is not None
-    return [_best_card_option(sel.option, list(range(len(sel.option))))]
+    return [_prioritized_evolve_index(sel.option, list(range(len(sel.option))), obs.current)]
 
 
 def _choose_card(obs: Observation) -> list[int]:
@@ -607,6 +641,35 @@
     return _clamp([best_i], sel, len(sel.option))
 
 
+def _engine_evolve_override(obs: Observation):
+    """EXP-0002 wild_growth_engine_priority, decisive form for the MAIN phase.
+
+    SEARCH_MAIN picks the top-level MAIN action by rollout eval, which bypasses
+    the greedy evolve ladder, so the priority is applied here before search. When
+    no Wild Growth Meganium (card 710) is in play and evolving the Chikorita line
+    into it is available, force that evolution -- UNLESS a lethal attack is on
+    the table (never skip a KO to set up the engine). Returns an index list or
+    None to defer to the normal search/greedy path."""
+    sel = obs.select
+    state = obs.current
+    if sel is None or state is None:
+        return None
+    options = sel.option
+    by_type = _group_by_type(options)
+    if OptionType.EVOLVE not in by_type or _wild_growth_in_play(state):
+        return None
+    engine = [i for i in by_type[OptionType.EVOLVE] if options[i].cardId == WILD_GROWTH_ENGINE_ID]
+    if not engine:
+        return None
+    opp = state.players[1 - state.yourIndex]
+    opp_active = opp.active[0] if opp.active else None
+    if OptionType.ATTACK in by_type and opp_active is not None:
+        _, dmg = _best_attack_index(options, by_type[OptionType.ATTACK])
+        if dmg >= opp_active.hp:
+            return None  # a lethal is available; take the KO, not the engine
+    return _clamp([engine[0]], sel, len(options))
+
+
 def agent(obs_dict: dict) -> list[int]:
     """Pokémon TCG agent entry point. Delegates to `_agent_impl`; on ANY unexpected
     exception there (e.g. the native cg engine failing to load on an unfamiliar
@@ -644,6 +707,11 @@
     if not obs.select.option:
         return []
 
+    if obs.select.type == SelectType.MAIN and obs.current is not None:
+        override = _engine_evolve_override(obs)
+        if override is not None:
+            return override  # evolve into card 710; never an ABILITY, no cap bookkeeping
+
     if SEARCH_MAIN and obs.select.type == SelectType.MAIN and obs.current is not None:
         chosen = _search_choose_main(obs)
         if chosen is not None:
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.
