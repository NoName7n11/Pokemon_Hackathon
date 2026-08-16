# My_Deck_Grass Specialist Progress

Append-only experiment log for this private Plan_2 specialist. This directory is
not the active submission.

---

## 2026-08-16

- **Specialist initialized**:
  - Worker provider: `claude`.
  - Source deck: `No_Name_Decks/My_Deck_Grass.csv`.
  - Agent baseline: `sample_submission/sample_submission/main.py`.
  - Static deck and Python-interface validation passed.
  - Runtime import and gameplay benchmarks remain pending in an environment with
    the competition `cg` engine.
  - **Reason:** establish an isolated, reproducible deck-agent workspace before
    any automated strategic experiments begin.

## 2026-08-16 — EXP-0001

- **REJECTED: Baseline instrumentation pass: measure deck tempo, trainer usage and Meganium presence for the unchanged generic agent on My_Deck_Grass**
  - Mechanisms: infrastructure_baseline.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 0.
  - Decision reason: Diagnostics-only pass: candidate is byte-identical to baseline. Purpose was to freeze snapshots/v000-baseline and collect setup/tempo/play censuses. No gameplay change, so nothing to accept.

## 2026-08-16 — EXP-0002

- **REJECTED: Meganium Wild Growth doubles every Basic G Energy, so _can_pay/_best_usable_damage understate every attacker while Meganium is in play (75% of games). Modelling it should correct lethal detection, active_quality and attacker ranking.**
  - Mechanisms: wild_growth_energy_accounting.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 0.
  - Decision reason: Hypothesis falsified by direct engine probe before any games were spent. mon.energies already reports PROVIDED energy, not attached cards: with Meganium in play a single Basic G card shows as energies=[1,1]. _can_pay is therefore already Wild-Growth-correct and the patch would have been inert. Probe also found the real defect: attack.damage is static, so Myriad Leaf Shower (id 120) reads 30 when it deals 30+30*provided-energy-on-both-Actives (measured 120/150/180), and Cruel Arrow (id 183) reads 0 when it deals 100.

## 2026-08-16 — EXP-0003

- **REJECTED: Static Attack.damage undervalues this deck's two variable-damage attacks: Myriad Leaf Shower reads 30 vs a measured 120-210, and Cruel Arrow reads 0 vs 100. Every damage-derived judgement (lethal gate, attack choice, active_quality, ko_risk, attacker ranking) is therefore wrong about Teal Mask Ogerpon ex and Fezandipiti ex.**
  - Mechanisms: live_variable_attack_damage.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: Non-inert but no effect. Screening 101-99 over 200 games (50.5%, z=0.141, p=0.888), 0 draws/timeouts/illegal/crashes. The damage formulas are correct (pinned by check_live_damage.py against three engine-measured samples) and the mechanism demonstrably fires (context_ab MAIN: 105 of 488 selections differ, 21.5%), so this is a real measurement of the hypothesis, not another inert candidate. Conclusion: correcting the static damage estimate does not by itself win games, most likely because the 1-ply lookahead already rolls out through the real engine and only the rollout's terminal _eval_state used the wrong number. The formulas are retained as knowledge in PROGRESS.md and will be re-introduced inside the phase that actually needs them (Boss's Orders gust-for-lethal), where they can be measured against a mechanism with a plausible win path.

---

## Verified engine facts for this deck

Measured directly against the live engine, not read off the cards. Re-verify before
trusting; do not re-derive from card text.

- **`mon.energies` is PROVIDED Energy, not attached cards.** With a Meganium (710) in
  play, one Basic {G} card reads `energies=[1,1]` while `energyCards` stays length 1.
  So `_can_pay` is already Wild-Growth-correct and needs no special handling. A patch
  that "fixes" Wild Growth in `_can_pay` is inert — this was `EXP-0002`.
- **Myriad Leaf Shower (attack id 120, Teal Mask Ogerpon ex)** deals
  `30 + 30 × (provided Energy on BOTH Active Pokemon)`; printed `Attack.damage` is 30.
  Measured 120 / 150 / 180. The discriminating sample had the opponent on 2 provided
  Energy from 1 card, and the engine dealt 180 — counting attached cards would predict
  150, so the count is provided, not cards.
- **Cruel Arrow (attack id 183, Fezandipiti ex)** has printed damage **0** and deals a
  flat **100** to any one of the opponent's Pokemon.
- `EXP-0003` implements both formulas as `_live_attack_damage`; the patch and its
  self-check survive at `experiments/EXP-0003/candidate/main.py` and
  `experiments/EXP-0003/check_live_damage.py` for reuse.

### Baseline behaviour census (frozen `v000-baseline` on this deck, mirror self-play)

Artifacts under `benchmarks/`. Tools: `setup_census.py`, `tempo_census.py`, and the two
added for this deck, `play_census.py` and `option_dump.py`.

- Jungle Dump first use **13.2 ply in wins vs 17.5 in losses**; 48 uses in wins vs 8 in
  losses. Myriad Leaf Shower 32 uses in wins vs 1 in losses. Bind Down (Bulbasaur,
  10 damage) 11 in wins vs **17 in losses** — the "stuck on an unevolved Active" loss
  signature.
- Opening Active: **Meowth ex chosen 4 of the 7 times it was offered**; Teal Mask
  Ogerpon ex only 1 of 3.
- Context volume per 10 games: `MAIN` 419, `CARD/TO_HAND` 97, `CARD/ATTACH_FROM` 53,
  **`ENERGY/SWITCH_ENERGY` 44**, `CARD/ATTACH_TO` 27, `CARD/SWITCH` 21. Every
  `SWITCH_ENERGY` is answered by the blind `range(minCount)` default while Solar
  Transfer fires 3.6×/game.
- Trainers are already played at 15.9 cards/game via the 1-ply lookahead, so the open
  question is target quality, not whether they get played.

## 2026-08-16 — EXP-0004

- **REJECTED: _live_attacker_score subtracts a 120*prize_value liability penalty that pushes every own-board CARD choice (post-KO forced promotion, and the 53-per-10-games ATTACH_FROM Solar Transfer destination) toward a cheap support Pokemon instead of this deck's rule-box attackers. Cancelling that penalty for an already-attack-ready ex/megaEx should concentrate energy and promotion on Mega Venusaur ex and Teal Mask Ogerpon ex.**
  - Mechanisms: attacker_concentration_bonus.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 0.
  - Decision reason: Inert: 0 differences across 96 own-board CARD selections (ATTACH_FROM 0/51, TO_ACTIVE 0/20, SWITCH 0/25) via context_ab.py. The bonus cannot change the argmax on this deck because _live_attacker_score is already dominated by raw HP: a charged Mega Venusaur ex scores ~4880 (240 dmg x20 + 380 hp - 360 prize penalty) against ~175 for a Bulbasaur, so cancelling the 360-point liability penalty moves nothing. The mechanism's 60.5% result on Claude_Grass_Venusaur does not transfer to this deck's board composition. No games spent.

## 2026-08-16 — EXP-0005

- **ACCEPTED: SelectType.ENERGY falls through _greedy_select's blind else-branch to range(minCount), so all 44 SWITCH_ENERGY selections per 10 games -- every Solar Transfer and Energy Switch SOURCE -- are chosen arbitrarily while Solar Transfer fires 3.6 times per game. Scoring the source by how expendable that Energy is should stop the deck's own energy engine from disarming its ready attacker.**
  - Mechanisms: energy_source_selection.
  - Baseline: `v000-baseline`; candidate: `v001-candidate`.
  - Benchmark runs recorded: 4.
  - Decision reason: final human approval: Operator accepted after reviewing the full evidence pack. Energy-source selection vs the frozen v000-baseline on this deck, seat-balanced, zero draws/timeouts/illegal actions/crashes in every run: smoke 13-7 (65.0%); screening 112-88 (56.0%, p=0.0897); main 174-126 (58.0%, p=0.0056); confirmation 283-217 (56.6%, z=2.95, p=0.0032, CI 52.2-60.9%); aggregate 582-438 (57.1%) over 1020 games. Non-inertness proven before any games were spent (context_ab SWITCH_ENERGY: 35 of 60 selections differ) and the logic pinned by check_energy_source.py. CROSS-DECK SCOPE: the two cross_deck_results rows are labelled evidence_kind=agent_overfit_regression and are NOT matchup_pair deck-vs-deck comparisons; candidate and baseline both pilot the foreign deck (Hydrapple 116-84, 58.0%, p=0.024; PalSystem_Dragapult 113-87, 56.5%, p=0.066) so My_Deck_Grass never plays in them. Deck-strength matchups are out of scope for this specialist by operator instruction. Both foreign decks improved by the same magnitude, indicating a general fix to a context the baseline answered at random rather than a Grass-specific hack. Acceptance is private to this specialist; the active submission is untouched and no Kaggle submission is authorized.
