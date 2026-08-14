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

- Stage: `confirmation`
- Candidate: `248/500` wins (49.6%)
- 95% interval: `45.2% - 54.0%`
- Head-to-head null test: `z=-0.17888543819998334`, `p=0.858027656987521`
- Draws/timeouts/illegal actions/crashes: `0/0/0/0`
- Mean/max decision time: `16.33 ms / 1111.16 ms`

## Cross-Deck Evidence

[
  {
    "status": "complete",
    "opponent": "Claude_Grass_Venusaur",
    "opponent_version": "v000-baseline",
    "games": 200,
    "wins": 73,
    "losses": 127,
    "draws": 0,
    "win_rate": 0.365,
    "result": "results/cross-deck-Claude_Grass_Venusaur.json"
  },
  {
    "status": "complete",
    "opponent": "Dark",
    "opponent_version": "v000-baseline",
    "games": 200,
    "wins": 142,
    "losses": 58,
    "draws": 0,
    "win_rate": 0.71,
    "result": "results/cross-deck-Dark.json"
  },
  {
    "status": "complete",
    "opponent": "Hydrapple",
    "opponent_version": "v000-baseline",
    "games": 200,
    "wins": 39,
    "losses": 161,
    "draws": 0,
    "win_rate": 0.195,
    "result": "results/cross-deck-Hydrapple.json"
  }
]

## Decision-Difference Trace

- Trace games: `20`
- Candidate decisions observed: `783`
- Different choices: `71` (9.1%)
- Games containing a difference: `15`
- Retained records: `71`; truncated: `False`

| Selection context | Differences |
|---|---:|
| MAIN | 71 |

Representative differences:

| Game | Step | Type/context | Candidate option types | Baseline option types |
|---:|---:|---|---|---|
| 1 | 4 | MAIN/MAIN | PLAY | PLAY |
| 1 | 19 | MAIN/MAIN | PLAY | ATTACH |
| 1 | 21 | MAIN/MAIN | EVOLVE | ATTACH |
| 1 | 22 | MAIN/MAIN | ATTACH | ATTACH |
| 1 | 26 | MAIN/MAIN | ATTACH | ATTACK |

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
