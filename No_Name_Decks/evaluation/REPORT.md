# No Name Deck Evaluation

Date: 2026-08-13

## Scope

This report evaluates the executable CSV lists in `No_Name_Decks/` against the
current Hydrapple deck. It does not adopt or activate any candidate specialist.

- All four decks used the same current generic `sample_submission/main.py`.
- Six pairings were run at 100 games per seat: 200 games per pairing and 1,200
  games total.
- First-player orientation was balanced. There were no draws, timeouts, engine
  crashes, agent crashes, or illegal actions.
- This measures deck strength under the current generic pilot. It does not prove
  the ceiling of a future dedicated agent.

## Field Ranking

| Rank | Deck | W-L | Field win rate | Worst matchup |
|---:|---|---:|---:|---:|
| 1 | Hydrapple | 480-120 | 80.0% | 74.0% vs Fire |
| 2 | Fire | 257-343 | 42.8% | 26.0% vs Hydrapple |
| 3 | Grass | 248-352 | 41.3% | 18.5% vs Hydrapple |
| 4 | Dark | 215-385 | 35.8% | 15.5% vs Hydrapple |

## Matchup Matrix

Each cell is the row deck's win rate over 200 games.

| Deck | Hydrapple | Dark | Fire | Grass |
|---|---:|---:|---:|---:|
| Hydrapple | - | 84.5% | 74.0% | 81.5% |
| Dark | 15.5% | - | 57.0% | 35.0% |
| Fire | 26.0% | 43.0% | - | 59.5% |
| Grass | 18.5% | 65.0% | 40.5% | - |

The candidate-to-candidate differences were statistically significant at the
unadjusted 0.05 level: Dark over Fire (`p=0.0477`), Grass over Dark
(`p=0.000022`), and Fire over Grass (`p=0.00721`). These three results form a
matchup cycle, so no candidate is uniformly superior.

## Deck Reviews

### Hydrapple

Hydrapple remains the measured control and the only selected specialist. Its
Ogerpon acceleration/draw, Forest evolution acceleration, Meganium energy
doubling, and Hydrapple attack scaling form a coherent engine that the current
agent already pilots reasonably well. It beat every submitted candidate by at
least 48 percentage points.

### Fire

**Measured position:** best candidate by aggregate field rate and the strongest
candidate into Hydrapple, though 26% is still far from competitive with it.

The shell has a clear progression: Charmander into either Mega Charizard,
Oricorio ex accelerates Fire Energy after a Fire Mega enters play, Flareon ex
searches and attaches Energy, and Eevee can fetch the Fire/Water/Lightning mix
needed for Carnelian. Firebreather supplies Oricorio with a large Energy hand.

The main structural risks are only two Rare Candy for four Charmander and four
Stage 2 Mega Charizard cards, a three-type Energy package that is useful mainly
for one Flareon attack, and several recovery/healing slots that do not improve
early setup. The generic agent also reads dynamic-damage Charizard attacks as
zero printed damage and does not reason about Inferno X's discard amount,
Explosion Y's Energy discard, repeated Oricorio acceleration, or the setup value
of Burning Charge. This deck has the best next-specialist case, but it should be
tested after a small consistency review rather than accepted unchanged.

### Grass

**Measured position:** second candidate by aggregate rate. It decisively beat
Dark but lost to Fire and Hydrapple.

This list has the deepest combo ceiling: Ogerpon supplies Energy and draw,
regular Meganium doubles Grass Energy, Mega Venusaur can redistribute Energy,
Mega Meganium scales from attached Grass Energy, Yanmega accelerates on promotion
and transfers Energy after attacking, and Forest allows same-turn evolution.

It is also the most setup-congested list: 26 Pokemon, two separate Stage 2 lines,
a Stage 1 line, only two Ultra Ball, no Mega Signal, two Ogerpon, and 11 Energy.
Four Rare Candy are shared between Venusaur and two Meganium endpoints. Mega
Kangaskhan adds another attacker without helping those evolution lines.

The archived Venusaur specialist had beaten its own older deck baseline 121-79,
but transferring that exact agent to this CSV produced 101-99 over 200 games
(`50.5%`, `p=0.888`). Therefore that prior gain does not validate this shell.
Grass remains a high-upside redesign candidate, not a currently proven specialist.

The Grass TXT and CSV disagree: the TXT lists Bug Catching Set `[1094]`, while
the executable CSV contains Buddy-Buddy Poffin `[1086]`. This report uses the CSV.

### Dark

**Measured position:** lowest aggregate rate and weakest Hydrapple matchup, but it
beat Fire 57-43. That result confirms real matchup-specific value.

The combinations are legitimate: Pecharunt and Munkidori reduce Prize loss;
Mega Gengar adds further Prize denial; Toxtricity accelerates to a Benched Dark
Pokemon and places damage that can activate Mega Sharpedo's 270-damage Hungry
Jaws; Pecharunt provides switching; Punk Helmet adds retaliation damage; Risky
Ruins punishes opposing non-Dark Basics; and Fezandipiti supplies recovery draw.

The problem is concentration. The deck contains 22 Pokemon spread across three
evolution packages and five different Basic ex support/attack roles, mostly at
two copies each. Only two Ultra Ball and two Rare Candy support that breadth.
The generic agent does not understand exact-six-counter Absol knockouts,
Prize-denial board requirements, intentional poison switching, damage-conditioned
Sharpedo attacks, or the best target for Toxtricity acceleration. A specialist
could improve it substantially, but the current list has both deck-consistency
and agent-complexity debt. It should be refined before receiving one of four
scarce specialist slots.

## Selection Recommendation

1. Keep **Hydrapple** as the only confirmed specialist.
2. Put **Fire** first in the candidate queue for the next specialist slot.
3. Keep **Grass** as a high-ceiling redesign candidate; simplify its Pokemon and
   search engine, then rerun the same matrix.
4. Keep **Dark** as a matchup-specialist redesign candidate; concentrate its
   primary attacker/engine before assigning a worker.
5. Do not fill all five worker slots merely to use capacity. Select the remaining
   decks after they clear legality, paper-synergy review, generic-agent screening,
   and at least one dedicated-agent transfer or ablation test.

The current evidence does not justify replacing Hydrapple or activating any of
these three lists unchanged. Fire is the best of the submitted candidates, not a
proven equal to Hydrapple.
