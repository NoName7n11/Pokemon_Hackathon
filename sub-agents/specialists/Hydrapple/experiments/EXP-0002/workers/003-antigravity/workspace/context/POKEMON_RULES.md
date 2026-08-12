# Pokémon Trading Card Game — Rules Reference

> Source: `par_rulebook_en.pdf` (Scarlet & Violet — Paradox Rift edition, official TPCI rulebook).
> Compiled as ML/agent context for the Kaggle **Pokémon TCG AI Battle Challenge** (cabt simulator).
> **Note:** For the competition, **simulator behavior is the ground truth** where it differs from these
> official rules — see `## Simulator Deviations` at the end and the cabt engine docs.

---

## 1. Win Conditions

You win the game in any of **3 ways**:

1. **Take all your Prize cards** (you start with 6; first to take the last one wins).
2. **Knock Out all opponent Pokémon in play** (opponent has no Pokémon left to promote to Active).
3. **Deck-out opponent**: opponent has no cards to draw at the *beginning* of their turn.

**Simultaneous win** → play **Sudden Death** (see §10). If you win in both ways and opponent wins in only
one, you are the victor outright.

---

## 2. Energy Types (11 total)

| Type | Symbol notes |
|------|--------------|
| Grass | often heals / poisons |
| Fire | big attacks, need recharge (discard energy) |
| Water | energy manipulation, repositioning |
| Lightning | recover energy from discard, paralyze |
| Psychic | special effects; sleep/confuse/poison |
| Fighting | risk/reward, coin-flip combos |
| Darkness | discard effects, poison |
| Metal | resistance-heavy, durable |
| Dragon | strong attacks, usually need 2 energy types |
| Fairy | exists only in older sets (SV uses Psychic instead) |
| Colorless (`✷`) | versatile; **any** energy type pays a `✷` cost |

**Key rule:** attack costs must be matched by attached Energy. A `✷` (Colorless) symbol in a cost can be
paid by **any** energy type. A typed symbol (e.g. Water) must be paid by that type. Cost of 0 = attack
needs no energy.

---

## 3. Card Types

### Pokémon
- **Basic** — playable directly from hand.
- **Stage 1 / Stage 2** — Evolution cards; play on top of the named lower stage ("Evolves from X").
- Evolution order: Basic → Stage 1 → Stage 2.

### Energy
- **Basic Energy** (Grass/Fire/Water/Lightning/Psychic/Fighting/Darkness/Metal/Fairy) — unlimited copies allowed in deck.
- **Special Energy** — deckbuild-limited to 4 like normal cards.

### Trainer (subtypes)
- **Item** — play any number per turn.
- **Supporter** — only **one per turn**; first player **cannot** play a Supporter on their first turn.
- **Stadium** — see §6.
- **Pokémon Tool** — attach to a Pokémon; **max 1 Tool per Pokémon**.

---

## 4. Board Zones

| Zone | Description |
|------|-------------|
| **Active Spot** | Exactly 1 Active Pokémon; only the Active can attack. Losing your last in-play Pokémon = loss. |
| **Bench** | Up to **5** Pokémon. Any non-Active in-play Pokémon must be here. |
| **Hand** | Starts at 7 cards; hidden from opponent. |
| **Deck** | 60 cards; order hidden unless a card says otherwise. |
| **Prize Cards** | 6 face-down, set aside during setup. Take 1 into hand per opponent KO. |
| **Discard Pile** | Face-up, public. KO'd Pokémon + attached cards go here (unless card says otherwise). |
| **Lost Zone** | Out of play permanently; cards sent here **cannot** be recovered (see §11 appendices). |

---

## 5. Setup Sequence

1. Coin flip → winner decides who goes first.
2. Each player shuffles 60-card deck, draws 7.
3. Must place **1 Basic Pokémon** face-down as Active.
4. May place up to 5 more Basic Pokémon face-down on Bench.
5. Set top 6 cards aside face-down as Prizes.
6. Reveal (flip up) Active + Bench, begin.

**Mulligan (no Basic in opening hand):** see §10 for full timing. Short version: reveal hand, shuffle
back, redraw 7, repeat until you have a Basic. Opponent may draw 1 extra card per extra mulligan you took.

---

## 6. Turn Structure

Each turn = **3 parts**:

### 1) Draw a card
- If deck empty at start of turn and you cannot draw → you **lose**.

### 2) Actions (any order, any number unless noted)
- **A. Play Basic Pokémon** to Bench (as many as you want, up to bench cap 5).
- **B. Evolve** Pokémon (as many as you want).
- **C. Attach Energy** from hand — **once per turn**.
- **D. Play Trainer cards** — Items unlimited; **1 Supporter/turn**; **1 Stadium/turn**.
- **E. Retreat** Active — **once per turn**.
- **F. Use Abilities** — as many as available (Abilities are **not** attacks).

### 3) Attack, then end turn
- Attacking **ends your turn** — do all step-2 actions first.
- **First player's very first turn: skip the attack step** (turn ends after other actions).

### 4) Pokémon Checkup (between-turns step)
Resolve **in this order**:
1. **Poisoned** → place 1 damage counter (10 dmg).
2. **Burned** → place 2 damage counters (20 dmg), then flip coin; heads = recover.
3. **Asleep** → flip coin; heads = wake up (recover), tails = stays asleep.
4. **Paralyzed** → recovers after its owner's next turn (during that checkup).

Apply any "during Pokémon Checkup / between turns" card effects here too. You may order
Special-Conditions vs other effects either way, **but cannot interleave** them. After checkups, any
Pokémon at 0 HP is Knocked Out.

---

## 7. Evolution Rules

- Play Evolution card on top of the named lower-stage Pokémon ("Evolves from X").
- Evolving **keeps**: attached cards (Energy, Tools), damage counters.
- Evolving **clears**: Special Conditions, and any attack effects on that Pokémon.
- **Cannot evolve** a Pokémon on the turn it was played (new in play).
- Neither player may evolve on their **first turn** of the game.
- Can evolve Active **or** Benched Pokémon.
- Evolved Pokémon **cannot** use the attacks/Abilities of its previous stage unless a card says so.
- "Evolves from" name must match **exactly**, including owner/form prefixes (e.g. Paldean Wooper ≠ Wooper).

---

## 8. Attacking (full detail)

**Step order for a complex attack:**
1. Choose attack; confirm correct Energy attached; announce it.
2. Apply effects that alter/cancel the attack (from prior turns). Effects referencing "this Pokémon"
   go away if the Active changed (e.g. moved to Bench).
3. If Active is **Confused**, flip coin now: tails = attack fails + 3 damage counters (30) to self.
4. Make required choices (e.g. "choose 1 Benched Pokémon").
5. Do required actions (coin flips, etc.).
6. Apply pre-damage effects → place damage counters → apply post-damage effects.

**Damage calculation order (when modifiers stack):**
1. Start with **base damage** printed. (If attack only says "put N damage counters," skip Weakness/
   Resistance/modifiers entirely — just place those counters.)
2. Add attacker-side damage boosts (before Weakness/Resistance).
3. Apply **Weakness** (× multiplier, usually ×2) if defender is weak to attacker's type — **increases**.
4. Apply **Resistance** (usually −30) if defender resists attacker's type — **decreases**.
5. Apply defender-side reductions (e.g. "takes 20 less damage after W&R").
6. Place 1 damage counter per 10 final damage. 0 or less → no counters.

**Weakness & Resistance apply to the ACTIVE (defending) Pokémon only — never Bench.**

**Knock Out:** damage ≥ HP → KO. KO'd Pokémon + all attached cards → discard. Opponent takes Prize card(s)
(1 normally; 2 or 3 for rule-box Pokémon — see appendices). KO'd player promotes a new Active from Bench.

**What counts as an attack:** anything with a cost + name in the attack area — **even if 0 damage**
(e.g. "Call for Family"). **Abilities are NOT attacks.** Cards that block attacks don't block Abilities,
and vice-versa.

---

## 9. Special Conditions

Only affect the **Active** Pokémon. **Cleared** when the Pokémon goes to Bench (retreat/switch) or evolves.

| Condition | Card orientation | Effect |
|-----------|-----------------|--------|
| **Asleep** | rotate counterclockwise | can't attack/retreat; checkup coin flip heads = wake |
| **Burned** | marker | checkup: 2 dmg counters + coin, heads = recover |
| **Confused** | rotate 180° (toward you) | must flip before attacking; tails = attack fails + 3 counters self |
| **Paralyzed** | rotate clockwise | can't attack/retreat; recovers after owner's next turn |
| **Poisoned** | marker | checkup: 1 dmg counter (or more if card specifies) |

- Asleep / Confused / Paralyzed all rotate the card → only **one** applies at a time (last one wins).
- Poisoned + Burned use **markers** → stack independently; a Pokémon can be Burned + Paralyzed + Poisoned simultaneously.
- Only **Asleep** and **Paralyzed** prevent **retreating**.

---

## 10. Advanced / Edge-Case Rules

### Mulligan (full)
- Both players no Basic → both reveal, reshuffle, restart normally.
- Only one player no Basic:
  1. Announce mulligan, wait for opponent to finish setup.
  2. Reveal hand, shuffle back, redraw 7; repeat until a Basic appears.
  3. Opponent (who didn't mulligan) may draw up to 1 extra card **per extra mulligan** taken; Basics among them may be benched.
  4. Reveal Active + Bench, begin.

### "up to" vs "any amount"
- **"up to X"** → choose any number 0..X (exception: "draw up to X cards" also allows 0).
- **"any amount" / "any number"** → may choose 0.
- **"you may ..."** → optional, may decline.

### Draw/look more than you have
- Draw/look at as many as exist, continue. You lose only if you **cannot draw at start of turn** — not if a
  card effect tells you to draw and there aren't enough.

### Sudden Death (tie-break)
- New game, each player uses **1 Prize** instead of 6. Coin flip for first, set up normally. Winner = overall winner. Repeat if it ties again.

### Pokémon name rules (deck-building identity)
- **Level / `SP`-style symbols / Team Plasma / TAG TEAM / Battle Style labels** → NOT part of name.
- **Suffix symbols** (`ex`, `EX`, `GX`, `V`, `VMAX`, `VSTAR`, `V-UNION`, `M`/Mega, `BREAK`, Alakazam ☆) → ARE part of name (different names → 4 of each allowed).
- **δ (Delta Species)** → NOT part of name.
- **Owner/form prefixes** (Alolan, Galarian, Paldean, Hisuian, Brock's, Rocket's) → ARE part of name.
- Deck limit: **max 4 copies** of any one name (except Basic Energy = unlimited).

---

## 11. Deck-Building Rules

- Deck must be **exactly 60 cards**.
- **Max 4** of any card by name (Basic Energy exempt — unlimited).
- Must contain **at least 1 Basic Pokémon**.
- **ACE SPEC** Trainer: max **1 total** ACE SPEC card in the whole deck.
- **Prism Star (`◇`)**: max 1 per name, but different-named Prism Stars allowed; go to Lost Zone instead of discard.
- **Radiant Pokémon**: max **1 Radiant** total in deck; always Basic; never evolve.
- **Pokémon V-UNION**: 4 pieces = 1 deck slot's worth (4 total cards, one of each piece, same set/artist).

**Starter guidelines:** 1–2 energy types; 12–15 Energy; ~20–25 Trainers; rest Pokémon (4-of key lines).

---

## 12. Card-Category Appendices (rule boxes & prize penalties)

Pokémon with **Rule Boxes** give extra Prize cards when KO'd. Summary of Prize-on-KO:

| Category | Prizes on KO | Notes |
|----------|:---:|-------|
| Regular Pokémon | 1 | — |
| **Pokémon ex** | 2 | `ex` part of name; Basic/Stage vary per card |
| **Tera Pokémon ex** | 2 | **No attack damage while on Bench** (all attacks, both players) |
| **Pokémon-EX** | 2 | older; `EX` ≠ `ex` (different names) |
| **Mega Evolution / Primal Reversion** | 2 | evolving into Mega **ends your turn** |
| **Pokémon-GX** | 2 | one **GX attack per game**; can be Basic/Stage |
| **TAG TEAM (GX)** | 3 | Basic GX with 2+ Pokémon; GX attack w/ bonus |
| **Pokémon V** | 2 | powerful Basic |
| **Pokémon VSTAR** | 2 | evolves from V; one **VSTAR Power per game** |
| **Pokémon VMAX** | 3 | evolves from V; 300+ HP |
| **Pokémon V-UNION** | 3 | assemble 4 pieces from discard onto Bench |

**Other appendix notes:**
- **Ancient / Future** (Paradox) — flavor label, hard-hitting vs technical.
- **Battle Styles** (Single/Rapid/Fusion Strike) — flavor + synergy tags.
- **Ancient Traits** (`Ω Barrier`, `Ω Recovery`, etc.) — special powers under the name; NOT attacks/Abilities → can't be shut off by attack/Ability lockdown.
- **Team Flare Hyper Gear** — Tools attached to *opponent's* Pokémon-EX; return to original player's discard when removed.
- **Ultra Beasts** — GX with crimson coloring; all have Prize-related attacks.
- **Dual-Type Pokémon** — two types at once; apply Weakness **then** Resistance if both relevant.
- **BREAK Evolution** — keeps prev-stage attacks/Abilities/W/R/retreat, gains more; new stage "BREAK."
- **Regional Variants** — Alolan/Galarian/Paldean/Hisuian in the name; evolution must match the variant.
- **Prism Star / ACE SPEC** — see §11 limits.
- **Rare Fossil / Unidentified Fossil** — Item cards playable **as Basic Pokémon**; evolve into Fossil Pokémon.
- **Restored Pokémon** — special stage; only enter play via the matching Fossil Item's effect; NOT Basic, NOT Evolution; still need a real Basic in deck.

---

## 13. Retreat (detail)

- Discard Energy from Active equal to its **Retreat Cost** (`✷` count, lower-right of card). 0 cost = free.
- Switch retreating Active with a Benched Pokémon; keep all counters + attached cards.
- **Once per turn.** Asleep/Paralyzed **cannot** retreat.
- Going to Bench (retreat or otherwise) clears Special Conditions + attack effects.
- You **may still attack** the same turn with the new Active.

---

## 14. Glossary (key terms)

- **Ability** — non-attack effect on a Pokémon; some are always-on, some activated. Read each.
- **Active Pokémon** — the one non-Bench Pokémon; only it can attack.
- **attach** — take a card from hand, put on an in-play Pokémon.
- **between-turns step / Pokémon Checkup** — resolves Special Conditions + timed effects.
- **damage counter** — standard = 10 damage.
- **Defending Pokémon** — the Pokémon receiving an attack.
- **devolve** — remove top Evolution card; loses Special Conditions + effects (opposite of evolve).
- **KO (Knocked Out)** — damage ≥ HP; Pokémon + attachments → discard; opponent takes Prize(s).
- **Pokémon Tool** — Item-like Trainer attached to a Pokémon; max 1 per Pokémon.
- **Rule Box** — box on rule-box Pokémon (ex/V/GX/etc.) → extra prizes + Stadium-based Ability lock affects them.
- **Stadium** — persistent Trainer; 1 in play at a time; new one discards old; can't replay same-named; 1/turn.
- **Weakness** — extra damage from a type (× multiplier). **Resistance** — less damage (−N). Active only.

---

## 15. Simulator Deviations (cabt engine — COMPETITION GROUND TRUTH)

Where the cabt simulator differs from the official rules above, **the simulator wins**. Known differences
(from competition discussion #708586):

1. **Unresolvable attacks are unselectable upfront** (vs official "declare then fail"): e.g. bench-fill
   attack with full bench, draw attack with empty deck, hand-interaction attack when opponent has 0 cards.
2. **Mega Zygarde ex "Nullifying Zero"**: damage target order not choosable; coins auto-flip left→right.
3. **Simultaneous-KO prize order**: sim = next-player picks+takes, then opponent picks+takes (official
   interleaves). Both-take-all still resolves as a **draw**.
4. **"Moved from Bench to Active this turn"** checks refer to the Pokémon's **current form**, not its
   pre-evolution (e.g. Buneary→Mega Lopunny ex same turn does NOT count as Mega Lopunny moving).
5. **Bench "cleans" all effects** — retreat + re-promote resets next-turn attack locks (e.g. Mega Brave).
6. **Ability vs Skill (engine OptionType)**: `ABILITY` = agent-selected activated action; `SKILL`/
   continuous effects auto-apply (no per-turn selection, e.g. weakness auras).
7. **Setup bench is optional**: when `select.context == SETUP_BENCH_POKEMON` and `minCount == 0`, return
   `[]` to skip benching (no explicit "end turn" option appears).

See the cabt engine API docs (`api.py` / `game.py`) for the observation/action data model.
