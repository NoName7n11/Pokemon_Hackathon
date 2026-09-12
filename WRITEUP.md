# Measuring What Actually Moves a Pokémon TCG Agent

**Nine mechanisms tested, one accepted: a negative-results program that separates deck strength from agent strength, and finds the bottleneck is the evaluator.**

---

## TL;DR

I built a heuristic Pokémon TCG agent, then spent most of my effort trying to disprove my own improvements. Nine agent mechanisms were tested against pre-committed thresholds; **one was accepted, eight were rejected**, and two apparently-significant results evaporated when the sample size grew. The single accepted change (+7 points) fixed a decision context the baseline answered *at random* — not a ranking it already computed. That distinction turned out to predict every subsequent result.

**Main keypoints:**

- **The strongest evidence in this report is a controlled deck-vs-agent decomposition.** A rank-30 competitor's deck is 90% identical to mine by card name and ties mine head-to-head under my own agent — while scoring ~700 leaderboard points higher. The deck is not my bottleneck.
- **Fix arbitrary decisions, not existing rankings.** Mechanisms correcting contexts the baseline answered arbitrarily won (+7 pts). Mechanisms refining rankings it already computed measured 50.5%, 51.0%, 50.2%, 50.0%, 47.0% — indistinguishable from zero.
- **More search made things monotonically worse** (49.5% → 47.5% → 44.5% → 41.5% as search width grew), which is the signature of a weak *evaluator*, not weak search.
- **Two nominally-significant results did not replicate.** One stood at 53.4% with p=0.0315 over 1000 games and fell to 51.25% over 2000. A pre-committed effect-size bar, not a p-value gate, is what prevented adopting it.
- **A 200-game screen carries ~7 points of standard deviation.** I measured this directly with an inert control arm that scored 44.5% while making zero different decisions.
- **The agent is structurally blind to 24% of the card pool.** The engine reports variable-damage attacks (`50×`) as `damage=0`, and my ranking reads that field.

**Context**
- Simulation competition: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle
- Competition data: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/data

---

## 1. Approach and rationale

The agent is a **priority ladder with a 1-ply lookahead**. On each MAIN decision it evaluates every legal option by forking the real engine, applying the option, playing the rest of the turn greedily, and scoring the resulting board. Where search fails, it falls back to a fixed ordering:

> lethal attack → evolve → attach Energy → develop bench → ability → best attack → retreat if dying → end turn

The ordering is deliberate. Lethal is first because a prize taken is irreversible. Evolution precedes attachment because evolution is free while attachment is the scarce once-per-turn resource. Attacking sits *below* board development because developing compounds and a marginal attack does not.

**What the ladder rests on is that the win condition is prizes, not damage.** I have a deck that dealt 4.4× more printed damage than its opponent and lost anyway, because 10 of its 14 Pokémon were Rule Box cards conceding 2 prizes each.

I also established early that **agent quality and deck choice are coupled**. The same lookahead code measured 64.6% on one deck and 45% on another. "This agent is better" is incomplete without naming the deck — a constraint that shaped the entire protocol below.

---

## 2. Evidence: three findings, each with its test

### 2.1 The deck is not the bottleneck (controlled comparison)

I reconstructed a rank-30 competitor's deck from a public episode replay and compared it to my own. *(Figure 4)*

| | Their deck | My deck |
|---|---|---|
| Card-name overlap | **90%** (54/60 identical) | — |
| Head-to-head, my agent piloting both, 80 seat-balanced games | 53.8% [42.9–64.3] | **statistical tie** |
| Leaderboard score | ~1090 | 333 (active) / 441 (best) |

Two decks that are 90% the same list and tie in play, separated by ~700 leaderboard points. **The gap is the agent, not the deck.** This comparison redirected my remaining effort away from deck construction entirely.

Their six-slot edge is instructive anyway: they cut four scattered 1-ofs and bought search with the slots (+2 Ultra Ball, +1 Forest of Vitality, +1 Dawn, +1 Meowth ex, +1 Energy), and run **zero Mega ex** — 29 prizes conceded across 20 Pokémon, the lowest of any list I measured.

### 2.2 Fix arbitrary decisions, not existing rankings

My accepted mechanism (**EXP-0005**) came from noticing that `SelectType.ENERGY` fell through to a blind `range(minCount)` default. Every Solar Transfer and Energy Switch *source* — 44 selections per 10 games — was chosen arbitrarily. The deck's own energy engine was disarming its ready attacker.

Scoring the source by expendability, against a frozen baseline, seat-balanced, zero faults:

| Stage | Result | Win rate | p |
|---|---|---|---|
| Smoke | 13–7 | 65.0% | — |
| Screening | 112–88 | 56.0% | 0.090 |
| Main | 174–126 | 58.0% | 0.0056 |
| Confirmation | 283–217 | 56.6% | 0.0032 |
| **Aggregate (1020 games)** | **582–438** | **57.1%** | CI 52.2–60.9% |

It also generalized: the same fix improved play on two *foreign* decks by the same magnitude (58.0%, 56.5%), indicating a general repair rather than a deck-specific hack.

**The eight rejections then formed a pattern** *(Figure 3)*. Mechanisms improving a ranking the baseline *already computed* went nowhere: 50.5%, 51.0%, 50.2%, 50.0%, 47.0%. Mechanisms reallocating a resource the accepted fix depended on actively lost (45.0%). The rule — *fix what is arbitrary, not what is merely imperfect* — was derived from data, not assumed.

### 2.3 The agent cannot see 24% of the card pool

The engine reports variable-damage attacks (printed `50×`) as `damage=0`, and `_best_attack_index` ranks attacks by exactly that field. **381 of 1556 engine attacks (24%) are therefore tied at zero** and picked by list order.

Demonstrated on Mega Gardevoir ex, whose Mega Symphonia scales at 50 damage per Psychic Energy in play. Across 10 games the agent parked on a 120-printed-damage Basic (334 steps Active) over the card that actually hits for 200–400 (55 steps). Patching *only the agent's view of that one number*, deck untouched, moved the matchup **20% → 37%**.

---

## 3. Generalization and the limits of my own measurements

**My early benchmarks were structurally blind.** Self-play against a frozen copy of myself on a mirrored deck reported 99% vs random and 60/40 vs prior-self — while the ladder said otherwise. A mirror cannot expose a deck-consistency failure, because both sides brick identically. Naming this is the point: the metric was not noisy, it was *measuring the wrong thing*.

What replaced it, and what I would defend as the methodological core of this submission:

**A 200-game screen cannot distinguish 45% from 55%.** I measured the noise floor directly by running an **inert control arm** — a candidate making zero different decisions across 49 selections — which scored **44.5% over 200 games**. Screens are a filter for gross regressions and inertness, not a measurement of small gains.

**Two nominally-significant results did not replicate** *(Figure 2)*:

| Experiment | Early look | Final |
|---|---|---|
| EXP-0012 | 53.4%, p=0.0315, n=1000 | **51.25%**, CI [49.06, 53.44], n=2000 |
| EXP-0015 | 57.5%, p=0.034, n=200 | **50.3%**, CI [47.2, 53.4], n=1000 |

Both were multiple-looks artifacts: screening, main, confirmation and extension are four chances for noise to cross a threshold, and one of them did. **A pre-committed 55% effect-size bar is what prevented adoption; a p-value gate alone would have accepted EXP-0012.** I consider this the single most useful thing I learned.

Every accepted or rejected mechanism was additionally **proven non-inert before games were spent** (by diffing selections in the target context against the baseline), so no result reports the noise of a candidate that never actually behaved differently.

---

## 4. Deck concept and key cards

The active submission is a **Grass toolbox built on two 2/2/2 evolution lines sharing one Basic-heavy shell**:

- **Applin → Dipplin → Hydrapple ex** — a 330 HP wall that anchors the board
- **Chikorita → Bayleef → Meganium** — *Meganium's Wild Growth makes every Basic Grass Energy count double, which is what makes the deck's attack costs payable at all*
- **4× Teal Mask Ogerpon ex** — 210 HP Basic; its Tera clause makes it immune to attack damage while Benched, and Teal Dance works from the Bench

The concept is **energy multiplication plus a durable Active**, not raw damage. Meganium is the enabler, not the attacker; Hydrapple ex absorbs the KOs that would otherwise cost prizes.

**Alignment with the agent is deliberate and measured.** The one accepted agent change (§2.2) is an *energy-routing* fix — precisely the mechanism this deck's game plan depends on. That is not a coincidence: the deck's win condition told me which decision context was worth instrumenting.

**Alternatives were built and rejected, not assumed away.** I constructed and measured two challenger decks:

| Deck | Concept | Result vs. active deck |
|---|---|---|
| Zygarde Ramp | All-Basic attackers; zero evolution steps | **37.0%** [28.2–46.8] |
| Mega Gardevoir | Board-wide energy scaling, 1-cost attacker | **19–20%** |

Zygarde is the more useful failure. Its thesis — *I lose by never coming online, so remove every evolution step* — was **confirmed on its own terms and still lost**: it attacked earlier (turn 3.7 vs 4.0), more often (6.9 vs 4.8 attacks/game), and for 4.4× more printed damage (627 vs 142) than the deck that beat it. The explanation is prize economy: 10 of its 14 Pokémon were Rule Box cards, so the opponent needed only ~3 knockouts. **Out-damaging does not matter when every one of your knockouts pays double.**

---

## 5. What didn't work

**The heuristic line is exhausted, and I can show it.** Nine mechanisms, one accepted, and the last five all inside the noise floor (50.5, 51.0, 50.2, 50.0, 47.0). Further single-context heuristic scoring has a measured expected value near zero.

**Search did not rescue it** *(Figure 1)*. I replaced the 1-ply lookahead with bounded UCT, using the accepted heuristic as fallback, rollout policy and seed candidate. After fixing a wiring bug that voided the first attempt, all four configurations sat at or below the heuristic over 200 games each:

| Configuration | Result | Win rate |
|---|---|---|
| horizon_turns=1 | 99–101 | 49.5% |
| mcts_baseline | 95–105 | 47.5% |
| selective_budget | 89–111 | 44.5% |
| max_candidates=24 | 83–117 | **41.5%** (p=0.016) |

**The trend is monotonic in search width — the signature of a weak evaluator, not weak search.** Widening the root from 8 to 24 candidates gave UCT three times as many ways to exploit blind spots in the position evaluator. Latency was never the constraint (9.2 ms mean, 97 ms max, zero faults).

A parallel research track reached the same conclusion independently at larger scale: a root-sampled ISMCTS agent with a learned policy-value model was built through self-play and a frozen multi-deck league, then **rejected by its own promotion gate on 960 games** (worst-matchup win rate 11.11%). Its self-play corpus was dominated by fallback targets — a learner cannot substantially exceed its teacher when most targets encode teacher behavior. That track also demonstrated that **packaging success is orthogonal to playing strength**: the rejected candidate passed every deployment gate, manifest check and shadow game.

**Two rejections were my own errors, reported as such.** A deck-specific promotion policy scored 32.5% — not because the strategy was wrong, but because I encoded a "keep this Pokémon Benched" rule as an unconditional −900, burying a charged 210 HP attacker below a 70 HP Basic. Corrected, it still scored 37.5%: the diagnosis is magnitude, not direction — my positional adjustments swamped the signal the baseline was using.

**I also lost two submissions to a deployment bug worth naming**, because it is invisible locally: Kaggle executes `main.py` via `exec()`, so `__file__` is undefined. `Path(__file__)` raised `NameError`, the deck loaded empty, validation failed. It reproduces only under a replicated exec harness, never under a normal import.

---

## 6. Conclusion

I can state plainly what is proven and what is not.

**Proven:** the deck is not my bottleneck (90% identical list, statistical tie, ~700 point gap). Fixing arbitrarily-answered decision contexts pays; refining existing rankings does not. The evaluator, not search depth, is the binding constraint — demonstrated twice, independently, at two scales. My screening methodology carries ~7 points of standard deviation, and pre-committed effect-size bars are what keep multiple-looks artifacts out of the agent.

**Not proven, and I will not claim it:** that my agent is competitive. Its active leaderboard score is 333. Everything above is an account of *why*, with the measurements attached.

**The identified next step is specific**: `_eval_state` enrichment, measured against the cheap 1-ply lookahead first. If the evaluator improves, search becomes worth retesting on top of it — in that order, because the monotonic-degradation result says search amplifies whatever the evaluator gets wrong. The variable-damage estimator (§2.3) is an independent, already-quantified +17-point repair that is not deck-specific.

---

## Sources

- Simulation competition overview — https://www.kaggle.com/competitions/pokemon-tcg-ai-battle
- Competition data — https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/data
- Strategy competition overview — https://www.kaggle.com/competitions/pokemon-tcg-ai-battle-challenge-strategy
- Opponent deck reconstructed from public episode replay `92687782` via the competition's own replay endpoint
- All experiment results cited above are recorded with per-stage counts, p-values and pre-committed thresholds in the project's append-only progress log
