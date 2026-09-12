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

## 2026-08-16 — EXP-0006

- **REJECTED: CARD/TO_HAND is the second-busiest context on this deck (97 selections per 10 games: every Dawn, Ultra Ball, Poke Pad, Bug Catching Set, Night Stretcher and Lana's Aid target) and falls through to _option_card_power descending, which scores a Basic G Energy at 0. The agent therefore never fetches Energy and always takes the biggest Pokemon, regardless of what the board actually lacks.**
  - Mechanisms: fetch_target_need_scoring.
  - Baseline: `v001-accepted`; candidate: `v002-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: Non-inert, mechanism verifiably works, but no win-rate effect. Screening 102-98 over 200 games (51.0%, z=0.283, p=0.777), 0 draws/timeouts/illegal actions/crashes, vs the accepted v001 baseline. Proven non-inert first (context_ab TO_HAND: 37 of 105 selections differ, 35%). A play_census on the candidate confirms it does exactly what it claimed: Mega Venusaur ex first reaches play at ply 6.22 vs 7.73 for baseline, Meganium 6.88 vs 9.59, Ivysaur 4.83 vs 5.65, Bayleef 5.97 vs 7.47. IMPORTANT NEGATIVE RESULT: assembling the Venusaur line 1.5-2.7 ply faster does NOT win more games, so the baseline census correlation (first Jungle Dump at ply 13.2 in wins vs 17.5 in losses) is confounded -- winning games are games where you survived to attack, not games where you rushed the line. This is the same trap as the PalSystem Dreepy-opening correlation. Cost of speed: reached-rate fell (Venusaur 0.85 to 0.80, Meganium 0.75 to 0.60) and cards played per game fell 15.9 to 13.25, so prioritising evolutions in fetches trades consistency for tempo the deck does not need. Future fetch work should optimise for reliability, not speed.

## 2026-08-16 — EXP-0007

- **REJECTED: _choose_main takes by_type[ABILITY][0] with no scoring, so the first-listed ability always wins. Measured over 10 games: 266 of 570 ABILITY-offering MAIN selections (47%) offer a real choice, the dominant menu is Solar Transfer vs Teal Dance (111 times), and Solar Transfer is taken 118 times to Teal Dance's 64 purely by list order. With ABILITY_CAP_PER_TURN=4 the unlimited energy-mover consumes the turn's ability budget and starves the once-per-turn abilities that ADD resources.**
  - Mechanisms: ability_priority_ordering.
  - Baseline: `v001-accepted`; candidate: `v002-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: Directionally NEGATIVE. Screening 90-110 over 200 games (45.0%, z=-1.414, p=0.157), 0 draws/timeouts/illegal actions/crashes, vs the accepted v001 baseline. Proven non-inert first (context_ab MAIN: 69 of 593 selections differ). The hypothesis was that once-per-turn resource-ADDING abilities should outrank the unlimited Energy router under ABILITY_CAP_PER_TURN=4; the measurement says the opposite. Coherent explanation, and it links to the accepted EXP-0005: correct Solar Transfer routing is worth about +7 points on this deck, so spending the 4-use ability budget on Teal Dance starves the very mechanism that produced that gain. Teal Dance adds one Energy and one card; Solar Transfer decides where every Energy on the board sits. NEXT HYPOTHESIS IMPLIED BY THIS RESULT: the binding constraint is the cap itself, not the ordering -- if both abilities are worth running, ABILITY_CAP_PER_TURN=4 is too tight. Raising it is the isolated follow-up, with timeouts as the self-detecting guard against the ability loop the cap exists to prevent.

## 2026-08-16 — EXP-0008

- **REJECTED: EXP-0007 showed that reallocating the 4-use-per-turn ability budget away from Solar Transfer LOSES games (45.0%), because correct Solar Transfer routing is what produced the accepted +7 point gain. If both Teal Dance and Solar Transfer are individually worth running, then ABILITY_CAP_PER_TURN=4 is the binding constraint rather than the ordering, and the cap is an anti-infinite-loop guard tuned on a different deck rather than a strategic limit.**
  - Mechanisms: ability_cap_budget.
  - Baseline: `v001-accepted`; candidate: `v002-candidate`.
  - Benchmark runs recorded: 3.
  - Decision reason: No effect at the pre-committed sample size. Screening 107-93 (53.5%, p=0.322) was inconclusive and below the 55% accept bar, so the main stage was run under an explicit prior commitment to judge on the POOLED result rather than on whichever stage read better. Main 144-156 (48.0%, p=0.488). Pooled 500 games: 251-249 (50.2%, z=0.089, p=0.929). Rejected. Zero draws, timeouts, illegal actions or crashes across all 520 games. Useful secondary finding: raising ABILITY_CAP_PER_TURN from 4 to 8 did NOT reopen the unbounded-ability loop the cap guards against -- no timeouts and no step-count runaway -- but it did lengthen games from about 154 to about 172 steps for no win-rate gain, so the cap at 4 is not costing this deck anything strategically and the extra decisions are pure overhead. Conclusion for the ability line of work: neither reordering (EXP-0007, 45.0%) nor enlarging (EXP-0008, 50.2% pooled) the ability budget helps; the accepted EXP-0005 routing fix already extracts what is available from this deck's ability engine.

## 2026-08-16 — EXP-0009

- **REJECTED: _best_attach_index scores the Active 10000+hp and any Bench target only hp, so the once-per-turn manual Energy attachment always goes to the Active regardless of who is being built. Measured over 10 games: 177 of 188 ATTACH-offering MAIN selections (94%) offer more than one target, and 22 of 93 attachments land on Meowth ex or Fezandipiti ex, support Pokemon that will never attack.**
  - Mechanisms: attach_target_attacker_scoring.
  - Baseline: `v001-accepted`; candidate: `v002-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: Dead flat. Screening 100-100 over 200 games (50.0%, p=1.0), 0 draws/timeouts/illegal actions/crashes, vs the accepted v001 baseline. Proven non-inert first (context_ab MAIN: 49 of 433 selections differ). The waste it targeted is real -- 22 of 93 manual attachments landed on Meowth ex or Fezandipiti ex, which never attack -- but correcting it changes nothing, and the reason is almost certainly the accepted EXP-0005: Solar Transfer reroutes misplaced Energy anyway, so the attachment target matters far less once the router is correct. Pattern across this specialist now: mechanisms that fix a context the baseline answered ARBITRARILY win (EXP-0005, +7 points); mechanisms that improve a ranking the baseline already computed do not (EXP-0003 50.5%, EXP-0006 51.0%, EXP-0009 50.0%), and reallocating a resource the accepted fix depends on loses (EXP-0007 45.0%).

## 2026-08-16 — EXP-0010

- **REJECTED: Hand-area DISCARD options carry cardId=None, so _option_card_power scores every one 0 and the stable sort discards hand slots 0 and 1. Ultra Ball's two-card cost is therefore paid blind. Observed directly: with hand [Meganium, Basic G Energy, Energy Switch, Night Stretcher, Night Stretcher] it discarded Meganium and the Energy while keeping two spare Night Stretchers; with hand [Lana's Aid, Boss's Orders, Bayleef] it discarded Boss's Orders. Meganium's Wild Growth is what makes every attack in this deck cost half.**
  - Mechanisms: discard_cost_targeting.
  - Baseline: `v001-accepted`; candidate: `v002-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: No gain, mildly negative. Smoke 8-12 (40.0%); screening 94-106 over 200 games (47.0%, p=0.396), 0 draws/timeouts/illegal actions/crashes vs the accepted v001 baseline. Proven non-inert first (context_ab DISCARD: 11 of 15 selections differ). The defect was real and confirmed by direct engine observation -- Ultra Ball's two-card cost was paid with hand slots 0 and 1, discarding Meganium plus an Energy while holding two spare Night Stretchers, and discarding Boss's Orders while holding a Bayleef -- but fixing it does not win games. Volume is the likely reason: about 1.1 such decisions per game is too rare to move a 200-game result even when each individual decision is much better. CLOSING THE HEURISTIC LINE: this was the last decision context the baseline answered arbitrarily. Nine mechanisms tested, one accepted (EXP-0005, +7 points). The last five all landed within noise (50.5, 51.0, 50.2, 50.0, 47.0). Further single-context heuristic scoring has a measured expected value near zero; the remaining headroom is structural, i.e. replacing the 1-ply lookahead with real search.

## 2026-08-16 — EXP-0011

- **REJECTED: The heuristic line is exhausted: nine mechanisms tested, one accepted, and the last five all landed within noise (50.5, 51.0, 50.2, 50.0, 47.0). The remaining headroom is structural. Replace the 1-ply greedy lookahead with plan_1's bounded UCT search, using the accepted v001 heuristic as fallback, rollout policy and seed candidate so the EXP-0005 energy routing feeds the search three ways. Probe confirms the search runs on this deck with a 0 percent fallback rate and 22.8 ms worst-case decision time, so it genuinely overrides the heuristic rather than reproducing it.**
  - Mechanisms: plan1_uct_search.
  - Baseline: `v001-accepted`; candidate: `v002-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: Search does not help this deck, established across four configurations after fixing a wiring bug that voided the first attempt. BUG FIRST: Plan1MCTSAgent enumerates legal options straight from the engine and never sees ABILITY_CAP_PER_TURN, so the unbounded Solar Transfer loop documented at main.py:249-263 reappeared through it -- a 10-game trace showed ABILITY picked 1092 times and END 18, against 52 and 958 for the heuristic, with games running 344 steps instead of 154. Win rate disguised this at an innocuous 49.0 percent; average step count exposed it. Gating the search path on the same cap fixed it (ABILITY 1092 to 97, steps back to 164). MEASURED PROPERLY, all four cap-fixed configs sit at or below the v001 heuristic over 200 games each: horizon_turns=1 99-101 (49.5%), mcts_baseline 95-105 (47.5%), selective_budget 89-111 (44.5%), max_candidates=24 83-117 (41.5%, p=0.016, significantly worse). The trend is monotonic in search width, which is the signature of a weak EVALUATOR rather than weak search: UCT scores leaf positions, so widening the root from 8 to 24 candidates gave it three times as many ways to exploit _eval_state's blind spots. This independently reproduces plan_1's 960-game finding that more search exposed evaluator and horizon weaknesses, on a deck they never tested. Latency was never the issue (9.2 ms mean, 97 ms max, zero faults across all arms). NEXT: the evaluator is the bottleneck, so _eval_state enrichment is being measured against the cheap 1-ply lookahead first; if that pays, search becomes worth retesting on top of it.

## 2026-08-16 — EXP-0012

- **REJECTED: Operator-supplied domain rule, refining the failed EXP-0007. Teal Dance pulls a NEW Basic G from hand and draws, so it is the better use of the per-turn ability budget UNLESS the Active cannot currently attack, in which case Solar Transfer routing is what converts the turn into damage. EXP-0007 tested a BLANKET reorder (Teal Dance always first) and lost at 45.0%; this conditional form screened 104-96 (52.0%) as a sweep arm, a 7-point swing over the blanket version. Teal Dance is additionally gated on actually holding a Basic G so it cannot burn an ability slot as a no-op.**
  - Mechanisms: conditional_ability_priority.
  - Baseline: `v001-accepted`; candidate: `v002-candidate`.
  - Benchmark runs recorded: 4.
  - Decision reason: Effect did not replicate at scale. Stage-by-stage: screening 101-99 (50.5%), main 169-131 (56.3%, p=0.028), confirmation 264-236 (52.8%), extension 491-509 (49.1%). POOLED 2000 games: 1025-975 (51.25%), CI [49.06, 53.44], z=1.118, p=0.264. Zero draws, timeouts, illegal actions or crashes across all 2020 games. IMPORTANT METHODOLOGICAL RESULT: at n=1000 this stood at 53.4% with p=0.0315 -- nominally significant, CI excluding 50% -- and 1000 further games on a fresh seed pulled it to 51.25% with the interval spanning 50. The apparent significance was a multiple-looks artifact: screening, main, confirmation and an extension are four opportunities for noise to cross a threshold, and one of them did. The pre-committed 55% effect-size bar is what prevented adoption at the n=1000 look; a p-value gate alone would have accepted this. The mechanism is not harmful and may be very slightly positive, but it is not distinguishable from zero and does not justify promotion. Operator's conditional formulation was still materially better than the blanket EXP-0007 reorder (45.0%), so the domain insight was sound; the remaining effect is just too small to bank.

## 2026-08-16 — EXP-0013

- **REJECTED: Operator-supplied forced-promotion policy for this deck. Four rules for the TO_ACTIVE/SWITCH contexts only: (1) a Pokemon that can KO the opponent's Active goes first; (2) Teal Mask Ogerpon ex stays Benched unless it can KO, because its Tera clause makes it immune to all attack damage on the Bench and its Teal Dance works from there; (3) Meowth ex is promoted when NOTHING else on the bench can attack -- Tuck Tail deals 60 and returns it plus attached cards to hand, dodging the 2-prize liability and enabling a second Last-Ditch Catch when replayed; (4) Fezandipiti ex is promoted only when an opponent Pokemon sits at or below 100 HP (exactly Cruel Arrow's damage) AND the opponent's Active cannot KO it in reply.**
  - Mechanisms: deck_promotion_policy.
  - Baseline: `v001-accepted`; candidate: `v002-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: REJECTED ON MY IMPLEMENTATION ERROR, not on the operator's strategy -- the rules as stated were never actually tested. Screening 65-135 (32.5%, p<0.0001); the parallel chump-block arm scored 64-136 (32.0%). Zero faults, so this is decision quality, not a crash. Two encoding defects found by direct scoring inspection. (1) The 'keep Teal Mask Ogerpon ex Benched for Tera immunity' rule was applied as an unconditional -900, with the only exception being 'it can KO right now'. The operator said 'unless it is very necessary'. Result: a charged 210 HP Ogerpon scored -915 and ranked BELOW a 70 HP Chikorita at -50, so the agent chump-blocked with its worst body while holding a live attacker. Same defect in the -700 Fezandipiti ex penalty. (2) In the chump arm, 'doomed' was evaluated PER CANDIDATE rather than once for the situation, so a fragile Pokemon scored up to +1900 for being killable while a sturdy one scored 0 -- it systematically promoted the weakest body on the bench. Correct encoding: the Ogerpon and Fezandipiti penalties must be conditional on an alternative that can actually attack existing, and the sacrifice branch must trigger on whether the opponent can KO our BEST option, not each candidate in turn. Rebuilding with those fixes; the operator's promotion policy remains untested.

## 2026-08-16 — EXP-0014

- **REJECTED: Retest of the operator's promotion policy with my two encoding errors fixed. EXP-0013 scored 32.5% because the 'keep Ogerpon Benched' rule was an unconditional -900, burying a charged 210 HP Ogerpon below a 70 HP Chikorita, and the sacrifice branch evaluated 'doomed' per candidate so it rewarded fragility. Corrected: the Ogerpon and Fezandipiti positional penalties apply ONLY when another benched Pokemon can actually attack, and the sacrifice branch triggers once for the situation, on whether the opponent can knock out our best option.**
  - Mechanisms: deck_promotion_policy_v2.
  - Baseline: `v001-accepted`; candidate: `v002-candidate`.
  - Benchmark runs recorded: 2.
  - Decision reason: Still strongly negative after both encoding errors were fixed, so the policy itself is harmful on this deck rather than merely miscoded. Screening 75-125 (37.5%), smoke 7-13 (35.0%), zero faults. For comparison the miscoded EXP-0013 scored 32.5% screening and 35.0% main (105-195, p=2e-7). The corrected version verifies against a self-check that pins the exact EXP-0013 failure (a charged Ogerpon must outrank a 70 HP Chikorita) plus the operator's scenario and the sacrifice case, and it is non-inert (16 of 29 TO_ACTIVE selections differ). Working diagnosis: magnitude, not direction. _live_attacker_score spans roughly -50 to 5000 and is dominated by HP and usable damage; adjustments of plus or minus 900 to 4000 override that signal wholesale, so even a correctly-directed rule swamps the information the baseline was using. Running a single-rule ablation to isolate which of the three rules carries the loss before spending anything further on this context, which has now cost roughly 1200 games across three experiments.

## 2026-08-16 — EXP-0015

- **REJECTED: Operator's Meowth ex Tuck Tail escape, with the precondition that the ablation exposed. Tuck Tail deals 60 and returns Meowth ex plus attached cards to hand, dodging its 2-prize liability and re-enabling Last-Ditch Catch on replay. The rule fires when nothing else on the bench can attack -- but that condition almost always means no Energy is in play, so Meowth ex cannot pay Tuck Tail's 3 Colorless either and simply dies for 2 prizes. Isolated without the guard it measured 73-127 (36.5%, p=0.0001). Adding 'and Meowth ex can actually attack right now' screened 115-85 (57.5%, p=0.034), a 21-point swing on the same rule.**
  - Mechanisms: meowth_tuck_tail_escape.
  - Baseline: `v001-accepted`; candidate: `v002-candidate`.
  - Benchmark runs recorded: 4.
  - Decision reason: The 57.5% screen was noise, exactly as the freshly measured noise floor predicted. Stage results: smoke 7-13 (35.0%), screening 105-95 (52.5%), main 143-157 (47.7%), confirmation 255-245 (51.0%). POOLED 1000 games: 503-497 (50.3%), CI [47.2, 53.4], p=0.850. Zero faults throughout. The single 200-game ablation screen that motivated this read 115-85 (57.5%, p=0.034) and did not survive a fivefold increase in sample size. WHAT IS STILL TRUE: the precondition was a genuine fix. Without the 'Meowth ex can actually pay Tuck Tail' guard the rule measured 73-127 (36.5%, p=0.0001) in isolation, because the trigger condition (nothing else can attack) almost always implies no Energy is in play, so Meowth ex could not escape and simply donated two prizes. Adding the guard moved it from actively harmful to exactly neutral. The rule is safe but adds nothing. METHODOLOGICAL NOTE, now demonstrated twice: an inert control arm (ko_only, 0 differences across 49 selections) scored 44.5% over 200 games, so a 200-game screen carries about 7 points of standard deviation and cannot distinguish 45% from 55%. EXP-0012 at 53.4%/p=0.0315 over 1000 games and this candidate at 57.5%/p=0.034 over 200 both evaporated at larger samples. Screens are a filter for gross regressions and inertness, not a measurement of small gains.
