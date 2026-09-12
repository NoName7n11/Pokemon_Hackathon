No_Name_Grass strategy specification
====================================

Core roles
----------

1. Mega Kangaskhan ex (756): opening Active, draw engine, and emergency attacker.
2. Yanmega ex (340): midgame Energy acceleration and cross-turn Energy relay.
3. Meganium (710): primary Energy engine. Wild Growth makes each Basic Grass
   Energy attached to our Pokemon provide two Grass Energy. The effect does not
   stack, so normally establish only one copy before prioritizing finishers.
4. Mega Venusaur ex (652): durable secondary attacker and unrestricted Basic
   Grass Energy redistribution through Solar Transfer.
5. Mega Meganium ex (919): primary scalable finisher.
6. Teal Mask Ogerpon ex (96): draw/acceleration support and secondary scalable
   finisher.

Opening and board construction
------------------------------

Preferred opening Active:

    Mega Kangaskhan ex > another expendable/retreatable Pokemon

Yanma should normally begin on the Bench. Buzzing Boost activates only when an
evolved Yanmega ex moves from the Bench to the Active Spot; evolving an Active
Yanma does not trigger it.

Preferred early Bench roles, adjusted for cards actually available:

1. One Yanma for the Yanmega acceleration line.
2. One Chikorita for Meganium (710).
3. One Bulbasaur for Mega Venusaur ex.
4. Teal Mask Ogerpon ex when Grass Energy is available in hand.
5. A second Yanma or a second attacker only when a slot remains and the first
   copy is threatened, prized, or needed for a multi-turn relay plan.

Do not attempt to fill all evolution lines automatically. Preserve a Bench slot
for the next required engine/attacker, and avoid placing redundant support
Pokemon when doing so blocks Yanma, Chikorita, Bulbasaur, or a needed finisher.

Early game: prefer Mega Kangaskhan ex as Active when Run Errand is useful and it
is not exposed to an immediate knockout. Mid/late game: stop protecting the draw
loop when an attacker can take prizes or Kangaskhan's three-prize liability is
unsafe. Mega Kangaskhan has a retreat cost of three, so do not make it Active
without an exit plan when the opponent can threaten it.

Turn sequencing
---------------

Do not use every Ability before every Trainer. Sequence effects according to
what they change:

1. Use search/top-deck effects before draw effects when planning a specific draw.
2. Ciphermaniac's Codebreaking must be used before Run Errand when using their
   combo. Put the two situationally best cards on top, then draw them with Run
   Errand. Selecting another Ciphermaniac is useful only when next turn's repeat
   is more valuable than the alternatives and the deck still contains both
   required targets.
3. Use a card that obtains Basic Grass Energy before Teal Dance if there is no
   Grass Energy in hand.
4. Trigger Buzzing Boost before deciding the final Solar Transfer distribution.
5. Use Solar Transfer after the intended attacker and required knockout damage
   are known. Move only the Energy needed for the plan unless consolidating
   Energy is strategically safer.
6. Take an available valuable knockout before low-impact setup, unless the setup
   prevents an immediate loss or creates a clearly superior prize line.

Forest of Vitality allows a Grass Pokemon to evolve during the turn it entered
play, except during the first turn. It does not remove Rare Candy's first-turn
restriction. Only choose evolution actions that the engine currently exposes as
legal.

Evolution and Rare Candy priorities
------------------------------------

When no Meganium (710) is in play and the Energy engine is useful:

    Chikorita -> Meganium (710)
        > Bulbasaur -> Mega Venusaur ex (652)
        > Chikorita -> Mega Meganium ex (919)

Exceptions:

- Never skip an immediate valuable knockout merely to establish Meganium 710.
- If the board already has enough effective Energy for the prize plan, Mega
  Venusaur or Mega Meganium may be the higher-value evolution.
- Once one Meganium 710 is in play, do not prioritize a second copy for Wild
  Growth because the Ability does not stack.
- If Yanmega has just relayed Energy to a Bulbasaur line, Mega Venusaur receives
  extra priority when Solar Transfer or Jungle Dump is immediately useful.

Meganium (710) is an engine piece and should normally remain on the Bench. Do
not voluntarily promote it unless it is the best legal attacker, all alternatives
are worse, or promotion is required to avoid losing immediately.

Yanmega acceleration and relay plan
-----------------------------------

Buzzing Boost is a once-per-turn Ability that triggers when Yanmega ex moves
from the Bench to the Active Spot. A valid sequence is:

1. Develop Yanma on the Bench and evolve it into Yanmega ex.
2. Move Yanmega from the Bench to Active through Switch, retreat, or promotion.
3. Use Buzzing Boost to attach up to three Basic Grass Energy from the deck.
4. Ensure Yanmega can pay Jet Cyclone's four-Energy cost. Buzzing Boost supplies
   at most three, so it generally needs one Energy already attached or another
   acceleration source.
5. Attack with Jet Cyclone for 210 and move exactly three Energy to one Benched
   Pokemon.

Jet Cyclone ends the turn. A second Yanmega cannot attack in the same turn. A
two-Yanmega relay is a multi-turn plan: prepare Yanmega B on the Bench, then move
it Active on a later turn, trigger Buzzing Boost, attack, and relay again.

Jet Cyclone destination priority is state-dependent:

1. A Bulbasaur/Ivysaur line when Mega Venusaur will become a useful attacker or
   enable Solar Transfer.
2. Mega Meganium ex or its Chikorita/Bayleef line when preparing a near-term
   Giant Bouquet knockout.
3. Mega Kangaskhan ex when it must become the next attacker and lacks its three
   Colorless Energy requirement.
4. Teal Mask Ogerpon ex when it is the best scalable attacker or safe Energy bank.
5. Another Yanmega only when doing so enables the next turn's attack and no
   higher-value destination exists.

Preserve enough Energy on the Active Yanmega to understand the post-attack
state: Jet Cyclone moves three Energy away, so the agent must not assume it will
remain powered next turn.

Solar Transfer and finisher calculations
-----------------------------------------

Mega Venusaur ex may move Basic Grass Energy between our Pokemon as often as
needed during the turn. Use it to concentrate Energy for a knockout, repair a
new Active after a knockout, or remove stranded Energy from a support Pokemon.

For Mega Meganium ex, Giant Bouquet damage is:

    70 + 50 * number_of_Grass_Energy_cards_attached_to_Mega_Meganium

Calculate the minimum attached Grass Energy cards required from the opponent's
current HP, not max HP. Apply known Weakness and Resistance when the engine does
not already encode them in the available outcome. Wild Growth changes how much
Energy each card provides for paying attack costs; it does not create additional
attached Energy cards for Giant Bouquet's damage count.

Move only enough Energy to secure the intended knockout while preserving the
next attacker when possible. Do not drain the whole board into a finisher that
will be knocked out immediately unless that trade wins the prize race.

Teal Mask Ogerpon ex is a secondary finisher. Myriad Leaf Shower scales with all
Energy attached to both Active Pokemon, so compare its live damage with Mega
Meganium and Yanmega rather than assuming one fixed finisher.

Boss's Orders and prize planning
--------------------------------

Use Boss's Orders when the selected target provides the best live outcome:

1. An immediate knockout that wins the game.
2. A multi-prize knockout with acceptable retaliation risk.
3. Removal of the opponent's most dangerous engine or prepared attacker.
4. A favorable stall target only when it materially improves the prize race.

Do not pull a Mega/ex merely because it awards multiple prizes. Verify current
HP, achievable damage, Weakness/Resistance, required Energy movement, remaining
prizes, and the likely knockout in return.

General decision rules
----------------------

- Prefer legal attacks that take valuable prizes over setup-only actions.
- Use live HP, attached Energy, current prize counts, and board roles rather
  than one unconditional static card priority.
- Preserve one Wild Growth Meganium and one viable attacker whenever possible.
- Avoid exposing three-prize Mega Pokemon solely for low-value Ability use.
- Treat all multi-card combos as conditional plans. If a required card, Bench
  slot, Energy, or legal action is unavailable, fall back to the strongest
  immediate board development or prize-taking line.
