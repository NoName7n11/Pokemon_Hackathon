# Human Review: Grass EXP-0004

## Hypothesis

During MAIN-phase Basic Pokemon PLAY choices, prioritize missing Grass core Bench roles in this order: Yanma for Yanmega relay, Chikorita for Meganium 710, Bulbasaur for Mega Venusaur, then Teal Mask Ogerpon ex when Grass Energy is available; avoid redundant support Pokemon when they block those roles.

Expected effect: Build the Grass deck's required engines more consistently without changing attack, evolution, or Energy-transfer logic.

Mechanisms: grass_core_bench_role_priority

## Review Assignment

- Implemented by: `opus` (`provider=claude`, `model=opus`)
- Assigned reviewer: `codex` (`provider=codex`, `model=gpt-5.5`)
- Reason: Claude/Opus-authored experiments require an independent Codex review.

## Evidence

- Stage: `screening`
- Candidate: `113/200` wins (56.5%)
- 95% interval: `49.6% - 63.2%`
- Head-to-head null test: `z=1.8384776310850222`, `p=0.06599205505934778`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `13.21 ms / 1691.35 ms`

## Cross-Deck Evidence

[]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `801`
- Different choices: `93` (11.6%)
- Games containing a difference: `20`
- Retained records: `93`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 93 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 1 | 19 | MAIN/MAIN | PLAY | EVOLVE |
| 1 | 26 | MAIN/MAIN | ATTACH | ABILITY |
| 1 | 30 | MAIN/MAIN | ATTACH | ABILITY |
| 1 | 40 | MAIN/MAIN | ABILITY | RETREAT |
| 1 | 60 | MAIN/MAIN | PLAY | PLAY |

## Required Human Checks

- Does the diff implement only the stated mechanism?
- Does the observed result justify more evaluation rather than acceptance?
- Could the change affect unrelated selection contexts or deck archetypes?
- Is representative decision-trace evidence required before the next benchmark?

## Agent Diff

```diff
--- baseline/main.py
+++ candidate/main.py
@@ -173,21 +173,92 @@
     return best_i
 
 
+# Grass core Bench role priority (see context/STRATEGY.md "Preferred early Bench
+# roles"). ID fallbacks let a line be recognized even if card names are absent:
+# Yanma/Yanmega ex, Meganium(710)/Mega Meganium ex(919), Mega Venusaur ex(652),
+# Teal Mask Ogerpon ex(96).
+_ROLE_BY_ID = {
+    339: "yanma", 340: "yanma",
+    710: "chikorita", 919: "chikorita",
+    652: "bulbasaur",
+    96: "ogerpon",
+}
+_ROLE_PRIORITY = {"yanma": 4, "chikorita": 3, "bulbasaur": 2, "ogerpon": 1}
+
+
+def _card_role(card):
+    """The Grass core Bench role a card belongs to, or None for support/other.
+    Prefers the card name (so every evolution stage of a line is recognized) and
+    falls back to known card IDs when a name attribute is unavailable."""
+    if card is None:
+        return None
+    name = (getattr(card, "name", "") or "").lower()
+    if "yanma" in name:
+        return "yanma"
+    if "chikorita" in name or "bayleef" in name or "meganium" in name:
+        return "chikorita"
+    if "bulbasaur" in name or "ivysaur" in name or "venusaur" in name:
+        return "bulbasaur"
+    if "ogerpon" in name:
+        return "ogerpon"
+    return _ROLE_BY_ID.get(getattr(card, "cardId", None))
+
+
+def _in_play_mons(p):
+    return ([p.active[0]] if p.active and p.active[0] is not None else []) + list(p.bench)
+
+
+def _roles_in_play(me):
+    """Grass core roles already represented on our board at any evolution stage."""
+    roles = set()
+    for m in _in_play_mons(me):
+        role = _card_role(_card_data().get(m.id))
+        if role is not None:
+            roles.add(role)
+    return roles
+
+
+def _grass_energy_available(me) -> bool:
+    """True if a Basic Grass Energy is available to power a played attacker:
+    already attached to one of our Pokemon, or sitting in hand. The deck's only
+    Basic Energy is Grass, so any attached/held Basic Energy qualifies."""
+    for m in _in_play_mons(me):
+        if any(e == EnergyType.GRASS for e in m.energies):
+            return True
+    hand = getattr(me, "hand", None) or []
+    for h in hand:
+        cid = h if isinstance(h, int) else getattr(h, "cardId", None)
+        card = _card_data().get(cid)
+        if card is not None and getattr(card, "cardType", None) == CardType.ENERGY:
+            return True
+    return False
+
+
 def _best_play_index(options, indices, me):
-    """Rank playable Basic Pokemon by likely board value."""
+    """Rank playable Basic Pokemon by Grass core Bench role first, then by static
+    board value. Roles are filled only when MISSING, highest first: Yanma
+    (Yanmega relay) > Chikorita (Meganium 710) > Bulbasaur (Mega Venusaur) >
+    Teal Mask Ogerpon ex when Grass Energy is available. A role already present
+    in play (any stage) is not re-prioritized, so a redundant second copy ranks
+    as ordinary support and does not block a still-missing core role."""
     cards = _card_data()
-    best_i, best_score = indices[0], -1
+    present = _roles_in_play(me)
+    grass_ready = _grass_energy_available(me)
+    best_i, best_key = None, None
     for i in indices:
         card = cards.get(options[i].cardId)
-        score = 0
-        if card is not None and card.cardType == CardType.POKEMON:
-            if card.basic and len(me.bench) < me.benchMax:
-                score = 5000 + _card_power(card.cardId)
-            else:
-                score = -1
-        if score > best_score:
-            best_i, best_score = i, score
-    return best_i if best_score >= 0 else None
+        if card is None or card.cardType != CardType.POKEMON:
+            continue
+        if not (card.basic and len(me.bench) < me.benchMax):
+            continue
+        role = _card_role(card)
+        if role == "ogerpon" and not grass_ready:
+            role = None
+        role_score = 0 if role is None or role in present else _ROLE_PRIORITY.get(role, 0)
+        key = (role_score, _card_power(card.cardId))
+        if best_key is None or key > best_key:
+            best_i, best_key = i, key
+    return best_i
 
 
 def _live_attacker_score(mon, opp_active=None) -> int:
```

## Decision

After screening, use `review_gate.py approve` only to authorize deep evaluation.
After confirmation and cross-deck evaluation, use `review_gate.py accept` for
private acceptance. Neither command promotes the active submission. Use
`review_gate.py reject` to close the experiment.


## Codex Auto Review

Decision: APPROVE_DEEP_EVALUATION.

APPROVE_DEEP_EVALUATION

The implementation is narrowly scoped to `_best_play_index`, so it should only directly alter Basic Pokemon `PLAY` selection. The mechanism matches the hypothesis: missing Yanma, Chikorita/Meganium line, Bulbasaur/Venusaur line, then Ogerpon with Grass Energy availability are prioritized, while already-represented roles fall back to ordinary card power.

The evidence is enough for deep evaluation, not private acceptance. The win rate is promising at `113/200` or `56.5%`, but the null test is marginal (`p=0.066`) and there is no cross-deck evidence. The trace shows all direct differences in `MAIN`, consistent with the changed selector, but the representative rows include downstream `ATTACH`, `ABILITY`, and `RETREAT` divergence, so a larger trace review should confirm these are state consequences of better bench setup rather than unrelated sequencing regressions.

Residual concerns for deep evaluation:
- The helper is in shared decision code, so non-Grass or mixed archetypes could be affected if they contain matching card names or IDs.
- `_grass_energy_available` treats any Energy card in hand as qualifying, relying on the Grass deck assumption.
- No evidence yet on ignored lethal attacks, losses, or slow outliers beyond the max decision time.

Recommended next step: run deep evaluation with cross-deck/matchup coverage and include trace slices for early Basic `PLAY` choices, downstream attack/retreat decisions after divergent benches, and losses.

Audit artifact: `specialists/Grass/experiments/EXP-0004/reviews/screening-codex-auto-review.json`.
