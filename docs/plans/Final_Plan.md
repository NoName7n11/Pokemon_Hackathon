# Final Plan — Perfect `My_Deck_Grass` (Mega Venusaur ex / Meganium)

**Scope:** make one deck — `No_Name_Decks/My_Deck_Grass.csv` — play as well as possible.
No cross-deck comparison, no portfolio decisions, no submission changes. The only
comparison used is **this deck's agent vs. this deck's own frozen baseline agent**
(same deck both seats, seat-balanced), which is what `benchmark_pair.py` already does.

---

## Context

### Why

The deck is new (sha256 `f091fe5a…`), registered nowhere, and no agent knows anything
about it. The active agent (`sample_submission/sample_submission/main.py`) is a
**deck-agnostic** heuristic ladder plus a 1-ply MAIN lookahead. It contains zero
card-ID logic.

### Measured baseline (Phase 0, done)

Frozen `snapshots/v000-baseline/main.py` on this deck, mirror self-play. Artifacts in
`sub-agents/specialists/My_Deck_Grass/benchmarks/`:

| Diagnostic | Result |
|---|---|
| `setup-census-baseline.json` (10 games) | Opening Active picks: **Meowth ex 4 of 7 offered**, Bulbasaur 3/5, Chikorita 2/2, Ogerpon ex **1 of 3**. Contexts seen: `MAIN` 419, `CARD/TO_HAND` **97**, `CARD/ATTACH_FROM` **53**, `ENERGY/SWITCH_ENERGY` **44**, `CARD/ATTACH_TO` 27, `CARD/SWITCH` 21. |
| `tempo-baseline-30.json` (30 games) | Jungle Dump first use: **13.2 ply in wins vs 17.5 in losses**; 48 uses in wins vs 8 in losses. Myriad Leaf Shower **32 uses in wins vs 1 in losses**. Bind Down (Bulbasaur, 10 dmg) **11 in wins vs 17 in losses**. Mega Venusaur ex Active: 9.3 ply win / 10.2 loss. Meganium reaches Active in only 8/30 games. |
| `play-census-baseline.json` (20 games) | **15.9 cards played per game** — Trainers *are* being played (Dawn 1.4, Bug Catching Set 1.4, Boss's Orders 1.3, Energy Switch 1.15/game). Abilities per game: **Solar Transfer 3.6**, Teal Dance 2.4, Flip the Script 0.85. Meganium in play 75% of games by ply ~9.6 (correctly Benched). |

### The three real defects (revised — Phase 0 corrected two guesses)

1. **~~Trainers are never played~~ — WRONG.** `_best_play_index` does refuse them, but
   `SEARCH_MAIN`'s 1-ply lookahead plays them anyway at 15.9/game. The lever is not
   *whether* Trainers get played but *which target they pick* — see defect 2.
2. **Blind selections in the deck's two busiest non-MAIN contexts.**
   `_greedy_select`'s `else` branch (main.py:468-469) returns `range(minCount)` for
   `SelectType.ENERGY` — that is **all 44 `SWITCH_ENERGY` selections per 10 games**, i.e.
   every Solar Transfer / Energy Switch source is chosen arbitrarily, while Solar Transfer
   fires 3.6×/game. `CARD/TO_HAND` (97 per 10 games — Dawn, Ultra Ball, Poké Pad, Bug
   Catching Set, Night Stretcher, Lana's Aid targets) falls through to `_option_card_power`
   descending, which ranks a Basic {G} Energy at **0** and so never fetches Energy.
   Verified option shape via `option_dump.py --context 33`: the option is the *source*
   energy, identified by `area`+`index`+`energyIndex`, `cardId` absent.
3. **`_can_pay` (main.py:484-500) does not model Wild Growth.** Meganium makes every
   Basic {G} count as {G}{G}. So `_best_usable_damage` under-reports Mega Venusaur ex
   (Jungle Dump reads as unaffordable at 2 Energy when it is actually payable), which
   corrupts `_eval_state.active_quality`, `ko_risk`, `_live_attacker_score`, and the
   lethal-attack gate at main.py:299-302. Meganium is in play in 75% of games.

### Deck logic, by part

**Card facts** (verified from `dataset/EN_Card_Data.csv`):

| Card | ID | n | Key text |
|---|---|---|---|
| Mega Venusaur ex | 652 | 3 | Stage 2 ← Ivysaur. HP 380. *Solar Transfer*: as often as you like, move a Basic {G} from one of your Pokémon to another. *Jungle Dump* `{G}{G}{G}{G}` 240, heal 30 self. Retreat 4. |
| Meganium | 710 | 2 | Stage 2 ← Bayleef. HP 160. *Wild Growth*: each Basic {G} on **all** your Pokémon provides {G}{G} (no stack). *Solar Beam* `{G}{G}●●` 140. |
| Teal Mask Ogerpon ex | 96 | 3 | Basic, Tera. HP 210. Bench = **immune to all attack damage**. *Teal Dance*: once/turn attach Basic {G} from hand to this Pokémon, then draw 1. *Myriad Leaf Shower* `{G}{G}{G}` 30 + 30 per Energy on **both** Actives. |
| Bulbasaur / Ivysaur | 650/651 | 3/3 | Venusaur line. |
| Chikorita / Bayleef | 917/918 | 2/2 | Meganium line. |
| Meowth ex | 1071 | 2 | Basic. *Last-Ditch Catch*: on play from hand to Bench, search deck for a **Supporter**. |
| Fezandipiti ex | 140 | 2 | Basic. *Flip the Script*: draw 3 if one of yours was KO'd last opponent turn. |
| Boss's Orders | 1182 | 3 | Supporter. Gust a Benched opponent to Active. |
| Bug Catching Set | 1094 | 3 | Item. Top 7 → take up to 2 ({G} Pokémon / Basic {G} Energy). |
| Dawn | 1231 | 3 | Supporter. Search deck for a Basic + a Stage 1 + a Stage 2. |
| Energy Switch | 1116 | 2 | Item. Move a Basic Energy between your Pokémon. |
| Forest of Vitality | 1261 | 2 | Stadium. {G} Pokémon may evolve into {G} the turn they are played (not turn 1). **Symmetric.** |
| Lana's Aid | 1184 | 2 | Supporter. Up to 3 non-Rule-Box Pokémon / Basic Energy from discard → hand. |
| Lillie's Determination | 1227 | 3 | Supporter. Shuffle hand into deck, draw 6 (8 if 6 prizes left). |
| Night Stretcher | 1097 | 2 | Item. Pokémon or Basic Energy from discard → hand. |
| Poké Pad | 1152 | 2 | Item. Search deck for a **non-Rule-Box** Pokémon. |
| Ultra Ball | 1121 | 2 | Item. Discard 2 → search any Pokémon. |
| Basic {G} Energy | 1 | 14 | — |

**The deck's actual plan, in four parts:**

- **Part A — Energy engine.** Meganium's Wild Growth turns 14 Basic {G} into effectively
  28. Jungle Dump costs 2 real Energy under Wild Growth; Solar Beam costs 2; Myriad Leaf
  Shower costs 2 (and its damage counts *attached Energy*, not provided Energy, so Wild
  Growth does **not** inflate its damage — only its cost). Solar Transfer + Energy Switch
  then move that Energy to whoever needs it, for free, any number of times.
  **Meganium is the single highest-value board piece in the deck and the baseline has no
  idea it exists.**
- **Part B — Attacker roles.** Ogerpon ex is the *early* attacker (turn 2-3, Teal Dance
  self-attaches) and, once Mega Venusaur ex is online, retreats to the Bench where it is
  damage-immune. Mega Venusaur ex is the *closer*: 380 HP, 240 damage, self-heal 30.
  Meganium is a *backup* attacker but primarily an engine — keep it Benched.
- **Part C — Setup / search.** Dawn is the deck's best card (fetches an entire evolution
  line in one Supporter). Meowth ex → Bench fetches Dawn. Bug Catching Set fixes both
  Energy and {G} Pokémon. Forest of Vitality compresses the Bulbasaur→Ivysaur→Venusaur
  clock by a turn. Ultra Ball's discard cost is nearly free because Lana's Aid and Night
  Stretcher recover.
- **Part D — Closing.** Boss's Orders drags a wounded/low-HP benched target into the
  Active spot for a Jungle Dump KO. This is the prize-race lever, and the baseline plays
  zero Supporters, so it currently never happens except by lookahead accident.

### Intended outcome

A deck-specialised `main.py` that measurably beats the frozen baseline agent on this deck,
with each mechanism proven non-inert *before* games are spent on it, and each accepted
change backed by a ≥200-game seat-balanced screen.

---

## Approach

Two layers, in order. Layer 1 is heuristic (cheap, high-yield, directly fixes the three
defects above). Layer 2 replaces the 1-ply lookahead with plan_1's bounded MCTS driven by
the Layer-1 heuristic as rollout policy.

**Why this order:** plan_1's own STRATEGY_REPORT concludes the search was only as good as
its handcrafted evaluator and its fallback policy — the learned candidate was rejected
960-games-conclusively, and `require_full_root_coverage=true` made search mostly *reproduce
its fallback*. So the fallback heuristic is the thing worth improving first. In
`Plan1MCTSAgent` the heuristic is simultaneously the fallback, the rollout policy, **and**
the seed candidate at every node — improving it improves the search three ways at once.

### Working location

Everything happens in a dedicated specialist so the active submission is untouched:

```
sub-agents/specialists/My_Deck_Grass/
```

created by `create_specialist.py`, driven **manually** (no orchestrator, no provider CLI —
those are broken/absent per PROGRESS 2026-08-15).

---

## Phases

Each phase: **verify non-inert → smoke 20 → screen 200 → keep or revert.**
A phase that screens below ~55% with p>0.05 gets reverted, not kept "because it looks right".

### Phase 0 — Infrastructure + honest baseline  ✅ DONE

Specialist `My_Deck_Grass` created (provider `claude`, baseline = the *active submission*
`sample_submission/sample_submission/main.py`, sha `29b95dac…` — not the older
`shared/baseline/main.py`, because the active one carries the Kaggle deck-load fixes).
Static + runtime validation PASS. `EXP-0001` started purely to freeze
`snapshots/v000-baseline/`; it is a diagnostics pass with no behavioural change and is
closed as rejected.

Two new diagnostic tools were added under `sub-agents/shared/tools/`:
- **`play_census.py`** — which cards the agent actually plays and which Abilities it uses,
  per game, split win/loss, plus first-in-play turn for watched Pokémon. Resolves PLAY /
  ABILITY options through `area`+`index` (their `cardId` is `None`).
- **`option_dump.py`** — dumps raw option payloads for one `SelectType`/`SelectContext`
  alongside the acting board, so a policy can be written for contexts the baseline
  currently answers blind.

Results are in the Context section above.

### Phase 1a — Wild Growth accounting  ❌ FALSIFIED BEFORE BENCHMARKING (`EXP-0002`)

Defect 3 above does not exist. A direct engine probe showed **`mon.energies` already reports
*provided* Energy, not attached cards**: with a Meganium in play, one Basic {G} card reads
`energies=[1,1]`. `_can_pay` is therefore already Wild-Growth-correct and the patch would have
been inert — the exact failure mode that cost PalSystem 440 games across EXP-0007/0008/0010.
Cost here: one probe, zero games. **This is the pattern to keep: probe the engine before
writing the patch, not after screening it.**

### Phase 1b — Live variable-damage estimation  *(`EXP-0003`, the real defect)*

The same probe found what is actually wrong. `Attack.damage` is a static print value, and this
deck has two attacks whose real damage it does not describe:

| Attack | Card | Printed | Actual |
|---|---|---|---|
| Myriad Leaf Shower (id 120) | Teal Mask Ogerpon ex | **30** | `30 + 30 × (provided Energy on both Actives)` — measured 120 / 150 / 180 |
| Cruel Arrow (id 183) | Fezandipiti ex | **0** | flat **100** to any one of the opponent's Pokémon |

The formula is *provided* Energy, not attached cards. The discriminating sample had the
opponent on 2 provided Energy from 1 card (their own Wild Growth) and the engine dealt 180,
which only the provided count explains.

Everything downstream of damage read the printed value, so the deck's early attacker was
valued at 30 and its support ex at 0. Changes, all in the candidate `main.py`:

- New `_live_attack_damage(atk, mon, opp_active)` — special-cases the two ids, returns
  `atk.damage` otherwise.
- `_best_attack_index(options, indices, mon, opp_active)` and
  `_best_usable_damage(mon, opp_active)` now route through it; the `opp_active` argument is
  threaded from `_choose_main`, `_choose_attack`, `_live_attacker_score`, and both
  `_eval_state` terms (`active_quality`, and `ko_risk` with the perspectives swapped).

**Evidence:**
- `check_live_damage.py` (in the experiment dir) pins all three measured samples plus the
  discriminating one — passes.
- Non-inertness `context_ab.py --context 0`: **105 of 488 MAIN selections differ (21.5%)**.
  (`--context 35` returns `no_observations`: attacks are chosen inside MAIN on this engine,
  never as a standalone ATTACK selection.)
- Smoke: **10/20**, 0 draws, 0 crashes, 0 illegal actions.
- **Screening 200: 101-99 (50.5%, z=0.141, p=0.888), 0 faults → REJECTED.**

The mechanism fires and the formulas are right, but it does not win games. Most likely
the 1-ply lookahead already rolls out through the real engine, so only the rollout's
*terminal* `_eval_state` ever saw the wrong number. The formulas are recorded in the
specialist `PROGRESS.md` under "Verified engine facts" and the patch survives at
`experiments/EXP-0003/` for reuse inside Phase 5, where gust-for-lethal actually needs
a true damage figure.

### Phase 2a — Attacker concentration bonus  ❌ INERT (`EXP-0004`)

Ported the `Claude_Grass_Venusaur` EXP-0002 mechanism (`+120 × prize_value + dmg × 5` for
an attack-ready ex/megaEx, added to `_live_attacker_score` in the own-board CARD branch),
which screened 121-79 (60.5%, p=0.00298) on that deck.

**0 differences across 96 own-board CARD selections** (`ATTACH_FROM` 0/51, `TO_ACTIVE`
0/20, `SWITCH` 0/25). It cannot change the argmax on *this* deck because
`_live_attacker_score` is already dominated by raw HP: a charged Mega Venusaur ex scores
~4880 (`240×20 + 380 − 360`) against ~175 for a Bulbasaur, so cancelling a 360-point
penalty moves nothing. The other deck's result does not transfer. Caught in three
minutes, zero games.

### Phase 2b — Energy-source selection  *(`EXP-0005`, the measured blind spot)*

`SelectType.ENERGY` was falling through `_greedy_select`'s blind `else` to
`range(minCount)` — **all 44 `SWITCH_ENERGY` selections per 10 games**, i.e. every Solar
Transfer and Energy Switch *source*, while Solar Transfer fires 3.6×/game. The deck's
whole engine exists to move Energy *onto* the attacker, so picking the source at random
is the one thing that must not happen.

- New `_choose_energy(obs)` wired into `_greedy_select` for `SelectType.ENERGY`.
- `_energy_source_score(opt, me)` ranks each source by expendability: `+300` Bench (idle),
  `+200` if that Pokémon cannot attack anyway, `−400` if losing the Energy drops a ready
  attacker below its cost, `−600` for a currently-able Active, `+10` per Energy already
  on the pile.
- `_EnergyView` is a two-slot stand-in so `_best_usable_damage` can be asked the
  counterfactual without touching live state. `opt.count` is in Energy **units**, which
  already accounts for Wild Growth doubling a Basic {G}.

**Evidence:**
- `check_energy_source.py` — pins that a ready Active is the worst donor, that an idle
  Bench Pokémon beats one that would be disarmed, that `count=2` is treated as strictly
  worse than `count=1` where it matters, and that an unmodelled area is inert not fatal.
- Non-inertness `context_ab.py --context 33`: **35 of 60 differ (58%)**. (`--context 30`,
  `DISCARD_ENERGY`, is inert at 0/17 — those selections are forced.)
- Smoke: **13/20 (65%)**, 0 draws, 0 crashes, 0 illegal actions.
- **Screening 200: 112-88 (56.0%, z=1.70, p=0.0897)**, CI [49.1%, 62.7%], 0 faults.
  Clears the 55% win-rate bar, misses `p<0.05` — inconclusive, not a rejection. This is
  the first candidate to move the number at all.
- **Main 300: 174-126 (58.0%, z=2.77, p=0.0056)**, CI [52.3%, 63.4%], 0 faults.
- **Combined screening + main, 500 games: 286-214 (57.2%), z≈3.22, p≈0.0013.** The
  screening CI's sub-50% lower bound was sample size, not absence of an effect.
- **Confirmation 500: 283-217 (56.6%, z=2.95, p=0.0032)**, CI [52.2%, 60.9%], 0 faults.
- **Aggregate across all four stages: 1020 games, 582-438 (57.1%)**, zero draws,
  timeouts, illegal actions or crashes at any stage.

**Overfit regression (agent check, not a deck comparison).** The built-in cross-deck
gate runs `matchup_pair.py` — this deck+agent *versus* another deck+agent — which is a
matchup and out of scope here. The check that actually answers "is this change overfit
to My_Deck_Grass" is `benchmark_pair.py` with the candidate and the frozen baseline
**both piloting a foreign deck**; this deck never enters it. Run against Hydrapple and
one further archetype. A change this generic (never disarm an Active that can attack)
should hold up on any deck; a regression there would mean the scoring is keyed to Grass
board shapes rather than to energy logic.

**Note on why this one worked where 0003 and 0004 did not.** Both of those tried to
improve a *ranking the agent already performed*. This one supplies a policy where there
was literally none — the blind `range(minCount)` default. The pattern to keep hunting:
find contexts the baseline answers arbitrarily, not scores it computes badly.

### Phase 2 — Energy routing: `SWITCH_ENERGY` source + `ATTACH_FROM` destination  *(fixes defect 2a)*

The single largest measured blind spot: **44 `SWITCH_ENERGY` selections per 10 games answered
with `range(minCount)`**, while Solar Transfer fires 3.6×/game. Verified option shape
(`option_dump.py --context 33`): `type=ENERGY(6)`, fields `area`, `index`, `playerIndex`,
`energyIndex`, `count`; the option is the **source** energy on one of my Pokémon.

- Add `SelectType.ENERGY` to `_greedy_select`'s dispatch instead of letting it fall into the
  blind `else`. Score each source energy by *how little that Pokémon needs it*:
  a Pokémon that is already at or above its best attack's cost, or that cannot attack at all
  (Fezandipiti ex, Meowth ex, an unevolved Bulbasaur behind a ready Venusaur), is the cheapest
  donor. Never strip an Active that is one Energy short of a lethal attack.
- `CARD/ATTACH_FROM` (53 per 10 games) is the **destination** and already routes to
  `_choose_card`'s own-board branch scored by `_live_attacker_score` — which penalises the
  Mega Venusaur ex closer by `-120 × prize_value = -360`. Phase 4's concentration bonus is
  the fix; keep the two phases separate so attribution is clean.

### Phase 3 — Search / fetch targeting (`TO_HAND`) and Ability scoring  *(fixes defect 2b)*

`CARD/TO_HAND` is 97 selections per 10 games — every Dawn, Ultra Ball, Poké Pad, Bug Catching
Set, Night Stretcher and Lana's Aid target. Baseline ranks by `_option_card_power`, which
scores a Basic {G} Energy at **0**, so it never fetches Energy and always takes the biggest
Pokémon. Replace with need-based scoring driven by the live board:

- missing evolution piece for a line I already have on board → highest
- Energy in hand + on board below what my intended attacker needs → fetch Energy
- a second copy of something I already hold → lowest

Then replace `by_type[ABILITY][0]` (main.py:320-321, no scoring at all) with a per-card
priority resolved from `opt.cardId`:

| Ability | Card | Rule |
|---|---|---|
| Last-Ditch Catch | 1071 | Highest — free Supporter tutor, one shot only. |
| Flip the Script | 140 | High when legal (draw 3). |
| Teal Dance | 96 | High — extra attach + draw, but only with a Basic {G} in hand. |
| Solar Transfer | 652 | **Conditional.** Only when it makes an attack payable that is not payable now, or saves Energy from a Pokémon about to be KO'd. Never a no-op shuffle. |

Solar Transfer needs its own guard: it is the exact ability the `ABILITY_CAP_PER_TURN` comment
(main.py:249-251) blames for infinite loops. Keep the global cap as a backstop and add a
purpose test. Re-run `check_ability_cap.py` after this phase.

### Phase 3b — Trainer play ordering  *(only if Phases 1-3 leave headroom)*

`_best_play_index` scores every non-Basic-Pokémon at `-1`, so Trainers reach the board only
through the lookahead's `_eval_state`, which has no hand/deck/development term. Give them real
scores: Dawn when a line is missing a stage; Lillie's Determination as hand size falls (bonus
at 6 prizes); Bug Catching Set / Poké Pad / Ultra Ball by what is missing; Energy Switch only
when it makes an attack payable; Night Stretcher / Lana's Aid by discard contents (Lana's Aid
cannot touch any ex — it is for Bulbasaur/Ivysaur/Chikorita/Bayleef/Meganium/Energy);
Forest of Vitality when a {G} Pokémon in hand wants to evolve this turn, noting it is
**symmetric**. Deferred behind Phases 1-3 because the census shows Trainers already reach
15.9 plays/game — the ordering, not the existence, is what is unproven.

### Phase 3c — Setup Active discipline

`setup_census` shows the baseline opens **Meowth ex 4 of the 7 times it is offered** — a
2-prize Colorless support ex with no {G} attack — and takes Teal Mask Ogerpon ex as Active
only 1 of 3 times. Ogerpon is the intended early attacker (Teal Dance self-attaches) *and* is
damage-immune on the Bench, so the correct opening is deck knowledge the generic
`_card_power` ranking cannot express. Note the PalSystem precedent: ~80% of setup Active
selections are single-option forced, so expect a small effect and gate it with
`context_ab.py --context 1` before spending games.

### Phase 4 — Attacker concentration / forced promotion

Port the `Claude_Grass_Venusaur` EXP-0002 mechanism, which screened **121-79 (60.5%,
p=0.00298, 0 faults)** and was rejected for portfolio reasons, not evidence
(`sub-agents/human-review/rejected/Claude_Grass_Venusaur-EXP-0002.json`):

- `_attacker_concentration_bonus(mon)` = `120 * _prize_value(mon) + usable_damage * 5`, gated
  on `card.ex or card.megaEx` and `usable_damage > 0`; added to `_live_attacker_score` in the
  own-board CARD branch.

Adapted for this deck: Ogerpon ex on the **Bench is damage-immune**, so promoting it out of
the Bench has a real cost the generic bonus does not model — add a penalty for pulling a
healthy Ogerpon out of Tera safety when another attacker is available.

### Phase 5 — Boss's Orders targeting + lethal closing

With Trainers playable (Phase 3), score Boss's Orders by the best gustable target:
`max over opponent bench of (KO-able by my usable damage) × prize_value`. Combine with the
existing lethal gate at main.py:299-302 so the sequence *gust → attack* is preferred over
attacking the current Active when the gust yields more prizes.

### Phase 6 — Swap the 1-ply lookahead for plan_1 MCTS

Only after Phases 1-5 have a proven heuristic. Wire `Plan1MCTSAgent`:

```python
Plan1MCTSAgent(
    api, deck, load_config(Path("search.json")),
    opponent_deck=deck,
    fallback_policy=grass._greedy_select,     # the Phase 1-5 heuristic
    rollout_policy=grass._greedy_select,
    action_observer=grass._record_if_ability,
    policy_value=None,                         # UCT, no model
)
```

Config: start from `plan_1/configs/mcts_selective_budget.json`
(`require_full_root_coverage: false`, 8 sims, 48 nodes, 24 ms / 8 ms reserve) and raise
`max_candidates` above 8 — with 8 candidates most multi-select contexts are non-exhaustive.
`horizon_turns: 0` (one-turn search) matches the current 1-ply behaviour; try `1` as an
ablation. Optionally subclass `HandcraftedEvaluator` with deck terms (Meganium in play,
Energy count vs. attacker count, Venusaur stage progress).

**This phase is optional and gated on Phases 1-5 landing.** If the heuristic alone screens
well, the MCTS swap is measured on its own merits, not assumed to help — plan_1's own report
says more search was not automatically better.

---

## Files

| File | Change |
|---|---|
| `sub-agents/specialists/My_Deck_Grass/` | **new** — created by `create_specialist.py` |
| `…/experiments/EXP-000N/candidate/main.py` | the only file edited per phase |
| `…/snapshots/v000-baseline/main.py` | frozen; **never** edited (PROGRESS 2026-08-15 records a Codex run that corrupted a baseline snapshot and broke the `agent_sha256` gate) |
| `sub-agents/shared/tools/` | possibly one small new census script in Phase 0 |
| `sample_submission/sample_submission/main.py` | **untouched** — no submission change without explicit sign-off |
| `PROGRESS.md` | append one entry per phase (append-only) |

Existing tooling reused, nothing rebuilt: `create_specialist.py`, `validate_agent.py`,
`run_experiment.py`, `benchmark_pair.py`, `context_ab.py`, `decision_trace.py`,
`setup_census.py`, `tempo_census.py`, `check_ability_cap.py`, `check_embedded_deck.py`.

---

## Hard constraints

- `agent()` must remain the **last `def`** in `main.py` (Kaggle uses the last def as entry).
  All helpers go above the banner at main.py:686-701.
- Setup-context options carry `option.cardId is None`; identify the card via
  `area == HAND (2)` + `index` into `current.players[yourIndex].hand`, then
  `all_card_data()[hand[index].id]`. Hand entries are `Card(id, serial, playerIndex)` —
  **`hand[i].name` does not exist** and returns `None`. This exact mistake wasted 440 games
  across PalSystem EXP-0007/0008/0010.
- Every mechanism gets a `context_ab.py` inertness check **before** any benchmark.
- No writes to the active submission, no Kaggle submission, no promotion.

---

## Verification

Per phase, from the repo root:

```powershell
# 1. non-inertness (must show disagreement > 0)
python sub-agents/shared/tools/context_ab.py `
  --candidate sub-agents/specialists/My_Deck_Grass/experiments/EXP-000N/candidate/main.py `
  --baseline  sub-agents/specialists/My_Deck_Grass/snapshots/v000-baseline/main.py `
  --deck      sub-agents/specialists/My_Deck_Grass/deck.csv --context 0 --games 20

# 2. smoke (20) then screening (200), seat-balanced, same deck both seats
python sub-agents/shared/tools/run_experiment.py run --specialist My_Deck_Grass --stage smoke
python sub-agents/shared/tools/run_experiment.py run --specialist My_Deck_Grass --stage screening

# 3. mechanism attribution
python sub-agents/shared/tools/decision_trace.py --candidate ... --baseline ... --deck ... --games 20

# 4. safety regressions
python sample_submission/sample_submission/check_ability_cap.py
python -c "import ast,sys; ..."   # agent() is still the last def
```

**Accept a phase only when:** 0 illegal actions, 0 crashes, 0 timeouts; screening win rate
≥55% with p<0.05 **or** clearly non-inferior with a proven on-mechanism trace; and the
decision trace shows the differences land in the context the phase targeted.

**Final gate for the deck as a whole:** 300-game main + 500-game confirmation vs. the frozen
baseline, on this deck only.

---

# Consolidated status (live)

## Accepted

**`EXP-0005` energy-source selection** — the only accepted mechanism. `SelectType.ENERGY`
fell through `_greedy_select`'s blind `else` to `range(minCount)`, so every Solar Transfer
and Energy Switch *source* was chosen arbitrarily (44 selections per 10 games, Solar
Transfer firing 3.6×/game). Now scored by expendability: never disarm an Active that can
attack, prefer idle Bench Energy.

| Stage | Games | Result | p |
|---|---|---|---|
| Smoke | 20 | 13-7 (65.0%) | 0.18 |
| Screening | 200 | 112-88 (56.0%) | 0.090 |
| Main | 300 | 174-126 (58.0%) | 0.0056 |
| Confirmation | 500 | 283-217 (56.6%) | **0.0032** |
| **Aggregate** | **1020** | **582-438 (57.1%)** | — |
| Overfit: Hydrapple deck | 200 | 116-84 (58.0%) | 0.024 |
| Overfit: Dragapult deck | 200 | 113-87 (56.5%) | 0.066 |

Promoted to `v001-accepted`. Not deck-overfit — same gain piloting foreign decks.

## Rejected, with the reason each one mattered

| EXP | Mechanism | Result | Lesson |
|---|---|---|---|
| 0002 | Wild Growth energy accounting | falsified by probe, **0 games** | `mon.energies` is *provided* energy; `_can_pay` was already correct |
| 0003 | Live variable attack damage | 50.5% | Formulas right (Myriad Leaf Shower = `30+30×provided on both Actives`; Cruel Arrow = 100), but correcting a value the rollout already resolves changes nothing |
| 0004 | Attacker concentration bonus | inert, **0 games** | `_live_attacker_score` is dominated by raw HP; a 360-point penalty cannot move a 4880-vs-175 gap |
| 0006 | Fetch-target need scoring | 51.0% | Made the line arrive **1.5-2.7 ply earlier** and still didn't win — the "deck is too slow" reading was confounded |
| 0007 | Ability priority ordering | 45.0% | Starving Solar Transfer of ability budget partly undoes EXP-0005 |
| 0008 | Ability cap 4→8 | 50.2% pooled (500) | Cap is a loop guard, not a strategic limit; costs nothing at 4 |
| 0009 | Attach-target scoring | 50.0% | Solar Transfer reroutes misplaced Energy anyway once the router is correct |
| 0010 | Discard-cost targeting | 47.0% | Real defect (pitched Meganium, pitched Boss's Orders) but ~1.1 decisions/game is too rare to move 200 games |
| — | Go second on `IS_FIRST` | 47.0% | Going first is correct; baseline default stands |

**The pattern:** mechanisms that fixed a context the baseline answered *arbitrarily* won
(EXP-0005). Mechanisms that improved a ranking it already computed did not (0003, 0006,
0009, 0010). Reallocating a resource the accepted fix depends on lost (0007).

## The MCTS wiring bug — why four results were void

`EXP-0011` wired plan_1's bounded UCT search. The first four screenings looked like
"search doesn't help" (49.0%, 37.5%, 49.0%, 44.5%). A decision trace found the real cause:
**ABILITY picked 1092 times vs END 18** in 10 games (baseline: 52 and 958). `Plan1MCTSAgent`
enumerates legal options straight from the engine and never sees `ABILITY_CAP_PER_TURN`, so
the unbounded Solar Transfer loop documented at main.py:249-263 reappeared through it.

Average steps per game tracked the pathology exactly, while win rate disguised it:

| Arm | Win rate | Steps/game |
|---|---|---|
| baseline reference | — | ~154 |
| `mcts_baseline` | 37.5% | 206 |
| `max_candidates=24` | 49.0% | 236 |
| `selective_budget` | 49.0% | 344 |
| `horizon_turns=1` | 44.5% | 398 |

Fixed by gating the search path on the same cap; trace confirms ABILITY 1092 → 97. All four
arms re-running. **Keep step-count as a standing health check** — two of those arms sat at a
perfectly innocuous 49.0% while looping.

## Deck experiments (never modify `My_Deck_Grass.csv`; variants live in `deck_experiments/`)

Same agent both seats, seat-balanced, so this isolates deck from agent.

| Variant | Change | Result |
|---|---|---|
| `variant_meowscarada` | +Sprigatito/Floragato/Meowscarada 2/2/2, +2 Rare Candy; −Meowth ex ×2, −Fezandipiti ex ×2, −Ogerpon ×1, −Poké Pad ×1, Energy 14→12 | **lost 169-331 (33.8%)**, p=4e-13 |
| `variant_consistency` | Boss's Orders/Dawn/Lillie's → 4, Ultra Ball → 3; −1 each Energy Switch, Lana's Aid, Night Stretcher, Poké Pad. **Pokémon and Energy untouched** | **won 263-237 (52.6%)**, p=0.245, extension running |

Meowscarada cut Basic Pokémon 12→9 and Energy 14→12 to fit a third line — card quality lost
to consistency. The consistency build is the only deck change with a positive signal, and it
matches the repo's own finding that Dipam (LB 1090.2) runs 5 four-of cards while the losing
Grass decks ran 2-3. **This deck runs zero.**

## Scoring context

`382.4` is a Gaussian skill rating (μ₀ = 600), not a percentage — below the starting rating
means net-losing. Reference: 1090.2 ≈ 30th of ~6,500; leader 1220.9. PROGRESS.md:1113-1141
already established our Hydrapple deck is **90% identical** to Dipam's at 1090.2 and
statistically tied in play (53.8% [42.9-64.3]). **The ~700-point gap is the agent, not the
deck** — which is why deck swaps are the low-yield axis here.

---

# Later results: domain-supplied rules, and a methodology lesson

## EXP-0012 — conditional ability priority (operator-supplied) — REJECTED

The operator's refinement of the failed EXP-0007: Teal Dance ahead of Solar Transfer
*unless the Active cannot currently attack*, in which case routing wins. Materially better
than my blanket version (45.0%), but the effect did not survive scale.

| Stage | Result | p |
|---|---|---|
| Screening | 101-99 (50.5%) | 0.89 |
| Main | 169-131 (56.3%) | **0.028** |
| Confirmation | 264-236 (52.8%) | 0.21 |
| Extension (fresh seed) | 491-509 (49.1%) | 0.57 |
| **Pooled 2,000** | **1025-975 (51.25%)** | **0.264** |

**The methodology lesson.** At n=1000 this stood at **53.4%, p=0.0315** — nominally
significant, CI excluding 50%. A further 1000 games on a fresh seed pulled it to 51.25%
with the interval spanning 50. Screening, main, confirmation and an extension are four
opportunities for noise to cross a threshold, and one did. **The pre-committed 55%
effect-size bar is the only thing that prevented adoption; a p-value gate alone would have
promoted a non-existent +3.4 point gain.**

## EXP-0013 / EXP-0014 — forced-promotion policy (operator-supplied) — REJECTED

Four deck-role rules for TO_ACTIVE / SWITCH: KO-capable first; Ogerpon ex held back for
Tera immunity; Meowth ex promoted as a Tuck Tail escape when the bench cannot attack;
Fezandipiti ex only when a target sits at ≤100 HP (Cruel Arrow's exact damage) and it
survives the reply.

| Version | Result |
|---|---|
| EXP-0013 (first encoding) | screening 65-135 (32.5%), main 105-195 (35.0%, p=2e-7) |
| chump arm (same + sacrifice logic) | 64-136 (32.0%) |
| EXP-0014 (both bugs fixed) | screening 75-125 (37.5%) |

**Two encoding defects, both mine, found by scoring inspection and by the self-check:**

1. "Keep Ogerpon Benched" was applied as an **unconditional −900**, so a charged 210 HP
   Ogerpon scored −915 and ranked *below a 70 HP Chikorita* — the agent chump-blocked
   while holding a live attacker.
2. The sacrifice branch evaluated "doomed" **per candidate** rather than once for the
   situation, so fragile Pokémon scored up to +1900 for being killable. It systematically
   promoted the weakest body available.
3. Even after fixing both, `all_doomed` still fired when a candidate *could* attack —
   chump-blocking is only right when there is no damage to trade. Caught by the self-check
   before any games were spent.

**Working diagnosis: magnitude, not direction.** `_live_attacker_score` spans roughly −50
to 5000 and is dominated by HP and damage×20. Adjustments of ±900–4000 do not refine that
ranking, they replace it. Single-rule ablation at ±200 supports this: the Ogerpon rule
scores 46.0% (p=0.258) as a nudge where it contributed to 32.5% as a veto.

**Also under-credited when proposing it:** Tuck Tail returns Meowth ex *and attached cards*
to hand, which removes it from play. That empties the Active slot and forces another
promotion, so it costs a turn to deal 60 — and if it were the only Pokémon in play, it
would be an immediate loss.

## Standing conclusion

13 mechanisms tested, 1 accepted (+7.1 points, 1420 games). Heuristic contexts exhausted;
search ruled out across 4 configs; evaluator enrichment flat; promotion meddling strongly
negative. Every benchmark is a **mirror match** — same deck and same agent lineage both
sides — and two competent copies converge toward 50% almost regardless of small policy
differences. That is why +7.1 was exceptional and why everything since sits in noise.
