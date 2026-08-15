# PalSystem Dragapult Strategy

Dataset-grounded strategy context for the dedicated `PalSystem_Dragapult`
specialist. These are hypotheses for bounded experiments, not pre-approved code
changes.

## Deck Identity

The deck is a Stage 2 Dragapult ex control/tempo deck. Its primary attack,
Phantom Dive, requires one Fire and one Psychic Energy, deals 200 damage to the
Active Pokemon, and places six damage counters on opposing Benched Pokemon.
The deck combines that pressure with Drakloak draw selection, Munkidori damage
movement, Item lock from Budew, hand disruption, Energy denial, and targeted
gust effects.

## Core Priorities

1. Establish enough Dreepy to survive an early knockout without filling every
   Bench slot with low-value support Pokemon.
2. Evolve through Drakloak and use every legal Recon Directive before evolving
   the same Drakloak into Dragapult ex when action ordering allows it.
3. Prepare at least one Dragapult ex with Fire and Psychic Energy. Crispin can
   obtain two different Basic Energy types and attach one, so its choices must
   account for the Energy already in hand and attached in play.
4. Prefer Phantom Dive when its 200 Active damage plus six Bench counters has
   more value than Jet Headbutt. Counter placement must consult live HP,
   existing damage, prize value, and reachable multi-knockout lines.
5. Attach Darkness Energy to Munkidori only when enabling Adrena-Brain is worth
   delaying another attacker. Move counters away from threatened friendly
   Pokemon and onto opponents where they produce a knockout or a credible
   follow-up threshold.

## Timing-Dependent Resources

- Budew is an early zero-Energy Item-lock option. It should not remain Active
  once a materially stronger attack is ready unless the lock has greater
  immediate value.
- Fezandipiti ex and Unfair Stamp depend on a knockout during the opponent's
  previous turn. They should be evaluated from live eligibility rather than
  generic card ranking.
- Meowth ex tutors a Supporter when benched. Bench capacity and its two-Prize
  liability must be weighed against the specific Supporter it enables.
- Boss's Orders should prioritize prize conversion, removal of a key engine
  Pokemon, or a target already prepared by Phantom Dive or Adrena-Brain.
- Crushing Hammer, Judge, Jamming Tower, and Unfair Stamp are disruption tools;
  their value depends on opponent resources and current tempo.
- Night Stretcher should recover the card that restores the highest-value live
  line, not simply the Pokemon or Energy with the highest static score.

## Initial Experiment Backlog

Run one mechanism at a time in this order:

1. **Energy routing:** Fire/Psychic completion for Dragapult ex, Darkness
   activation for Munkidori, and Crispin choice/attachment coordination.
2. **Ability/evolution ordering:** Recon Directive before evolution and
   knockout-triggered Fezandipiti ex timing.
3. **Spread targeting:** live-HP and prize-aware Phantom Dive counter placement,
   including multi-knockout opportunities.
4. **Damage movement:** legal and useful Adrena-Brain source/target selection.
5. **Tempo and promotion:** Budew exit timing, prepared-attacker promotion, and
   retreat decisions.
6. **Disruption timing:** Boss's Orders, Unfair Stamp, Judge, Crushing Hammer,
   and Jamming Tower based on live state.

Each candidate must retain the frozen baseline pair, use seat-balanced fresh
seeds, pass decision-trace review, and be checked against Hydrapple and
No_Name_Grass. Mirror-only improvement is insufficient.
