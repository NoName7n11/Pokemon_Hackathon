# Pokémon Hackathon — Progress Log

Local change log for this repo. Every implementation gets recorded here, newest first,
signed with the implementer's name at the end of the entry.

**APPEND-ONLY.** Never edit or delete an existing entry — only add new ones. This log is
a permanent record; past entries stay exactly as written, even if later reverted (note
the reversal as a new entry instead).

---

## 2026-08-11

- **Ability-cap fix confirmed clean on the shipped Hydrapple baseline (follow-up to
  the entry below)**:
  - `self_play_benchmark.py 500` (main.py with the fix, vs frozen `previous_agent`,
    Hydrapple mirror): **48.6% [95% CI 44.2-53.0%]** (243/257/0), avg 126.4 steps. CI
    spans 50% -- a tie, and average steps sits in the same ~121-131 band logged since
    the 08-08 freeze. Exactly the expected result: Hydrapple's own Abilities (Teal
    Dance, Ripening Charge) are already "once during your turn" -- bounded -- so the
    cap never engages on them and should be a no-op, which this confirms.
  - The fix is now validated on both ends: `check_ability_cap.py` shows it eliminates
    the hang on the deck that exposed the bug, and this run shows it does not change
    behavior on the deck that must not regress. Committed and pushed as `569ca1d`
    together with the fix itself. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **First `Claude_Decks/` build exposed a genuine infinite-loop bug in `main.py`'s
  MAIN ladder; root-caused and fixed at the actual decision point**:
  - `Claude_Decks/Claude_Grass_Venusaur.txt` / `.csv` — first deck built from the
    user's flagged-card research: extends the proven Hydrapple core (Teal Mask
    Ogerpon ex / Meganium / Hydrapple ex) with a second Stage-2 Grass attacker line,
    Bulbasaur -> Ivysaur -> **Mega Venusaur ex** (380 HP, `Solar Transfer` ability
    moves a Basic {G} Energy between own Pokemon "as often as you like"). 24 Pokemon /
    23 Trainers / 13 Energy, legal by direct Card-ID check against the dataset (all 60
    IDs exist, no name over 4 copies outside Energy, >=1 Basic present) and confirmed
    playable end-to-end through the real engine.
  - **First measurement was alarming: 80% vs random (Hydrapple's own baseline is
    96-97%) and 23.5% [18.2-29.8] head-to-head vs Hydrapple, n=200 seat-balanced.**
    Investigated rather than accepted at face value, per house discipline. A 20-game
    instrumented mirror run showed **avg 831-963 steps** (Hydrapple's proven average is
    ~121-131) with **7 of 20 games (35%) hitting the 3000-step harness cap and never
    finishing**, scored as non-wins. Not a weak deck -- a hang.
  - **Root cause, confirmed by direct trace of the actual option sequence:** the agent
    cycles `ENERGY -> CARD -> ABILITY -> ENERGY -> CARD -> ABILITY ...` on one turn for
    1500+ consecutive steps. Mega Venusaur ex's `Solar Transfer` is legal forever (moves
    Energy between your own in-play Pokemon at zero net cost, so nothing runs out), and
    `_eval_state`'s Active-quality term (`energies * 5`, shipped 2026-08-04) rewards
    hoarding Energy with **no penalty for never attacking**. Once an unlimited
    energy-move source exists, `_search_choose_main` finds "use Ability again" scores
    higher than "attack" on literally every turn and re-picks it forever. This pathway
    was invisible until now because Hydrapple's own abilities (Teal Dance, Ripening
    Charge) are all "once during your turn" -- bounded.
  - **First fix attempt was wrong and is recorded as such.** Capped Ability re-selection
    inside `_choose_main`'s greedy ladder (`_take_ability`, a per-(turn,seat) counter).
    Re-ran the same trace: **identical infinite loop, unchanged.** Cause: when
    `SEARCH_MAIN` is on, the top-level MAIN decision is chosen by `_search_choose_main`,
    which evaluates every `sel.option` candidate directly and **never calls
    `_choose_main`'s ladder for the live pick** -- that function is only used for the
    ROLLOUT TAIL inside each candidate's preview. The cap gated a code path the bug
    didn't go through.
  - **Working fix gates the actual decision point.** Replaced the ladder-only cap with
    `_ability_cap_reached()` (read-only, checked by both `_choose_main`'s ladder AND
    `_search_choose_main`'s candidate loop, which now skips ABILITY-type options once
    the cap is hit) and `_record_ability_use()` / `_record_if_ability()` (the only
    writer, called once in `_agent_impl` on the action actually returned to the engine
    -- never from inside a rollout, so hypothetical search deliberation can't burn the
    real turn's budget before the live game acts). `ABILITY_CAP_PER_TURN = 4`: high
    enough that legitimate multi-use turns (consolidating Energy from several sources
    before attacking) aren't restricted, low enough to guarantee the MAIN phase always
    terminates.
  - `sample_submission/sample_submission/check_ability_cap.py` — new persistent
    regression check (ponytail: one runnable check for non-trivial logic). Plays N
    games with the Grass/Venusaur deck and asserts none hit the step cap.
    **Before the working fix: 6/30 games at ~2998-2999 steps (right at the cap).
    After: 0/30, all finishing in a normal 30-239 step range.**
  - **Verification status, stated plainly rather than assumed:** the no-regression
    check on the shipped Hydrapple baseline (`self_play_benchmark.py 500` vs frozen
    `previous_agent`) and a clean re-measure of the new deck vs random were both
    **launched but not yet returned** when this entry was written (the shell session
    restarted mid-run and orphaned the first attempt). Do not read this fix as fully
    validated on the shipped deck until a follow-up entry confirms the ~71.6% Hydrapple
    baseline is unchanged. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Deck builder full-TXT import and persistent saved-deck folders added**:
  - `deck_builder/index.html`, `app.js`, and `styles.css` — expanded deck import
    from pasted card IDs into a multi-file TXT workflow that accepts the grouped
    `count card name - card ID` format used by `Codex_MegaCharizard_FireTurbo.txt`,
    `Codex_FireCamerupt.txt`, and `Hydrapple.txt`. **Reason for the
    implementation:** imported deck lists needed to remain available for visual
    comparison instead of only replacing the single editable deck and then being
    forgotten.
  - Added a persistent **Saved Decks** catalog section. Each imported file becomes
    a separate folder named from its filename; opening a folder shows its unique
    cards with local card artwork and imported copy counts in the same visual form
    as the Card Catalog. Saved folders can be loaded explicitly into the editable
    builder or deleted, and re-importing the same deck name updates that folder.
  - Multiple TXT files can be selected in one import. Pasted deck lists remain
    supported with an explicit deck name, unknown IDs are reported and skipped,
    and saved folders persist in browser storage alongside the working deck and
    flags.
  - Verification passed against all three requested examples: Mega Charizard Fire
    Turbo imported as 60 cards / 21 unique / 0 unknown IDs, Fire Camerupt as 60 /
    18 / 0, and Hydrapple as 60 / 26 / 0. JavaScript syntax and diff checks also
    passed. No submission `main.py` or active `deck.csv` was changed. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Codex Mega Charizard Fire Turbo candidate built from updated flagged pool**:
  - `Codex_Decks/Codex_MegaCharizard_FireTurbo.txt` and `.csv` — added a separate
    60-card candidate deck, leaving active submission files unchanged. **Reason for
    the implementation:** the updated `My_Deck_flags.txt` added enough Fire Mega
    pieces to form a coherent Pokemon shell and support shell around Mega
    Charizard X ex, Mega Charizard Y ex, Oricorio ex, and Firebreather without
    mixing unrelated flagged engines.
  - The deck uses a compact 17-Pokemon shell: 4 Charmander split across two legal
    printings, 2 Charmeleon, 3 Mega Charizard X ex as the primary scalable finisher,
    2 Mega Charizard Y ex as a high-impact secondary snipe attacker, 3 Oricorio ex
    for Fire Energy acceleration once a Fire Mega is in play, plus Fezandipiti ex,
    Latias ex, and Mega Audino ex as utility/support basics.
  - Trainer shell follows the World Champion deck lesson of high consistency:
    4 Firebreather, 4 Hilda, 4 Ultra Ball, 4 Rare Candy, 3 Mega Signal, 3 Pokegear
    3.0, 2 Boss's Orders, 2 Air Balloon, 2 Night Stretcher, and 1 Precious Trolley
    ACE SPEC. Energy shell is 14 Basic {R} Energy so Firebreather and Oricorio ex
    have enough targets and Charizard X has fuel across the board.
  - Validation passed locally: 60 total cards, exactly 1 ACE SPEC, and no
    non-Basic card name above four copies. This deck is exploratory only and was
    not copied into `sample_submission/sample_submission/deck.csv`. —
    <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-08-10

- **World Champion deck import reviewed — use as structure reference, not direct copy**:
  - Reviewed the newly added `World_Champion_Decks_2025/` folder and sampled lists
    across Junior, Senior, and Master divisions. **Reason for the implementation:**
    the original entry only recorded that the files were added; the more useful
    project takeaway is what their deck structure teaches for our own deck-building
    process.
  - The strongest repeated pattern is Trainer density and consistency, not large
    Pokemon piles. Across the sampled champion lists, Pokemon counts generally sit
    around 13-23, Trainer counts around 28-39, and Energy around 6-12. Repeated
    staples include search/draw/recovery/gust cards such as Ultra Ball, Boss's
    Orders, Iono, Fezandipiti ex, Nest Ball, Buddy-Buddy Poffin, Night Stretcher,
    Counter Catcher, Arven, Rare Candy, and Super Rod.
  - Current user workflow clarified: the immediate focus is intentionally only on
    building a **Pokemon shell** from the flagged card pool. Trainer and Energy
    shells should be added later after the Pokemon core is chosen, because the
    correct support package depends on the chosen attackers, evolution depth,
    Energy types, acceleration needs, and whether the deck asks the agent to pilot
    complex sequencing.
  - Practical rule carried forward: use the champion lists as deck-construction
    templates for ratios and consistency philosophy, but do not copy them directly.
    The hackathon card pool is different, and our submitted `main.py` must be able
    to pilot the resulting deck reliably. No deck files, `main.py`, or active
    `deck.csv` were changed. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Added ``World_Champion_Decks_2025`` for understanding deck creation and learning strategies:**
  - ``/Junior`` contains all the decks from Junior Division.
  - ``/Senior`` contains all the decks from Senior Division.
  - ``/Master`` contains all the decks from Master Division. - <span style="background-color:rgba(50, 205, 50, 0.31); color:#12db12">no_name</span>

- **Card-pool research pass on the user's 53 flagged cards; multi-type Energy solved;
  `Claude_Decks/` created**:
  - `Claude_Decks/` — new directory. All decks I build from now on go here only, kept
    separate from `Decs/` (user-authored + replay-derived), `Codex_Decks/`, and the
    active submission `deck.csv`.
  - **Leafeon ex `{G}{R}{W}` rainbow-cost problem — solved.** The user asked which
    cards can supply Energy of different types. Findings from the full 2,022-row pool:
    - **Terapagos [234]** is the single best answer: `Prism Charge ●` searches the deck
      for **up to 3 Basic Energy of different types and attaches them to your Tera
      Pokémon**. Leafeon ex is Tera(Stellar), so one attack costing one Colorless pays
      the entire `{G}{R}{W}` cost straight from deck. It also pairs with Leafeon ex's
      `[Tera]` (no damage while Benched), so the attacker loads in total safety.
    - **Sparkling Crystal [1165]** (Tool) makes any **Tera** Pokémon's attacks cost
      **1 Energy less, of any type** — it does not fix the rainbow so much as delete a
      third of it, and it applies to six already-flagged Tera cards.
    - Trap recorded: **Prism Energy [16]** is rainbow **only on Basic** Pokémon and
      **Neo Upper Energy [10]** only on **Stage 2**. Leafeon ex is Stage 1, so both
      provide plain `{C}` on it and are dead there. **Legacy Energy [12]** is genuinely
      wild but is **ACE SPEC** (1 copy) and competes with Energy Search Pro for the slot.
  - **Direct-attach sweep (non-Pokémon cards).** Confirmed **no Stadium in the pool
    attaches Energy** — all 26 checked; Levincia [1254] is the only Energy-related
    Stadium at all and it only moves Basic {L} from discard to *hand*. Direct attach
    lives on 11 Items/Supporters/Tools. Generic, any-type, any-target: **Waitress
    [1235]** (deck -> any 1 Pokémon, Active or Bench), **Crispin [1198]**, **Powerglass
    [1163]** (discard -> Active, repeats every turn, no Supporter slot), **Energy Coin
    [1135]** (coin-flip), **Rosa's Encouragement [1240]** (Stage 2, prize-gated).
    Archetype-locked: **Janine's Secret Art [1195]** is the strongest single card of the
    group (2 Basic {D} from deck onto 2 different {D} Pokémon) but is dark-only.
    **Heavy Baton [1160]** moves up to 3 Basic Energy to the Bench when a **retreat-4**
    Active is KO'd — four flagged cards qualify (Iron Thorns ex, Cetitan ex, Mega
    Venusaur ex, Orthworm ex).
  - **Review of `My_Deck_flags.txt` (53 cards).** Structural finding: the list is
    **53 Pokémon, 0 Trainers, 0 Energy**. Deck strength in this pool has repeatedly
    tracked Trainer consistency (LiamK sits at #1 on a 36-Trainer build), so ~30 slots
    of every deck built from this list are still unscouted.
  - Cards judged strongest, grouped by what they actually do:
    - *Passive/always-on:* Meganium [710] (each Basic {G} provides {G}{G} — a doubler,
      not accel), Aurorus [1033] (-50 to all {W}-attached), Ludicolo [262] (+40 HP to
      every Pokémon in play), Cornerstone Mask Ogerpon ex [117] (immune to any Pokémon
      **with an Ability**), Serperior ex [481] (+20 to all your attacks).
    - *Anti-meta hosers — the most interesting group:* **Iron Thorns ex [37]** turns off
      **every Rule Box Pokémon's Ability in play, both sides** while Active (this would
      blank Mega Lopunny/Mega Froslass, and also our own Teal Dance); **Tyranitar [290]**
      Item-locks the opponent while Active; **Genesect [142]** blocks ACE SPEC;
      **Farigiraf ex [83]** is immune to Basic Pokémon ex. Worth noting because copying
      LiamK's *deck* measured as a tie (49.2%) — attacking their *engine* is a different
      axis that has not been tried.
    - *Cost-break attackers:* Incineroar ex [79] (-{C} per opponent Bench Pokémon),
      Decidueye ex [1022] (ignores all {C} when opponent holds exactly 4 cards),
      Yanmega ex [340] (self-loads 3 Basic {G} on Bench->Active), Azumarill [315]
      (230 for `{P}` with any Tera in play).
  - **Corrections to my own review, after the user pushed back — all three of their
    challenges were right and are recorded as such:**
    - **Seviper [829]** — I called it a dead card without a {D} Mega ex. **Wrong.**
      `Pitch-Black Fangs` is **120 base**, 240 with the Ability live. It is also already
      enabled by **Mega Gengar ex [772]** ({D} Mega ex) on the same list.
    - **Oricorio ex [795] + Charizard** — the user's played combo checks out and is
      stronger than I credited. **Mega Charizard X ex [790]**'s `Inferno X {R}{R}` is
      **90x per {R} Energy discarded from among your Pokémon** — not just itself — so
      Oricorio's unlimited attach to the **Bench** builds a fuel tank Charizard spends.
      The hand-dependency the user then solved themselves with **Firebreather [1232]**
      (Supporter: search up to **7** Basic {R} Energy to hand), verified in the pool.
    - **Magneton [211] self-KO** — I logged the conceded Prize as a drawback. The user's
      read is better: it *powers your own cards*. Eight cards scale on "Prize cards your
      opponent has taken" — best fit is **Zekrom ex [515]** (`Voltage Burst` 130 **+50
      per prize**, same {L} type), so Magneton loads it from the discard, dies, and pays
      for the concession on the same turn. Also **Kingambit [901]** (+30/prize, passive).
      Noted for accuracy: **Luxray [1037]** scales on prizes ***you*** took — opposite
      direction, does **not** pair with Magneton.
  - One correction in the other direction: **Huntail [416]** recovers the **Basic {W}
    Energy cards to hand**, *not* the Knocked Out Pokémon. It limits tempo loss on a KO;
    it cannot replay the attacker. Kept on the list pending a {W} shell.
  - **Data-quality find:** [480] Servine and [481] Serperior ex are the **only 2 cards
    in the entire dataset with untranslated Japanese effect text**. Serperior ex's
    Regal Cheer is "+20 damage to the opponent's Active from your Pokémon's attacks" and
    Command the Grass is "150, then search your deck for up to 3 cards". Flagged because
    `main.py` reads effect text for heuristics, so a build around it needs the simulator
    behaviour verified first.
  - **Selection criterion carried forward from our own measurements:** deck power under
    *our* pilot is not paper power (one agent change moved Mega_Lopunny +6.6 and
    Mega_Latias -8.4 in the round-robin). The useful split of this list is **agent-proof**
    (passive effects that need no sequencing) vs **needs piloting**. The largest single
    cluster the user flagged — unlimited energy-move loops (Azumarill ex, Dewgong, Mega
    Venusaur ex, Mega Gengar ex, Iron Thorns ex) — is precisely what a greedy ladder plus
    1-ply MAIN search handles worst. No decks built yet; this entry is the research
    substrate for them. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Codex deck workspace created — future Codex-built decks isolated**:
  - `Codex_Decks/` — added a dedicated directory for deck lists created by Codex
    from this point onward. **Reason for the implementation:** keep exploratory
    Codex-built decks separate from existing `Decs/`, active submission files, and
    user/Claude deck work so future deck experiments are easier to compare without
    muddying the current project structure.
  - No deck files, `main.py`, or active `deck.csv` were changed. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Flagged-section import/export added — portable CSV and readable TXT**:
  - Added separate Import / TXT / CSV controls beside the flagged catalog section
    tabs in `deck_builder/index.html`, with transfer logic in `app.js` and compact
    responsive styling in `styles.css`. **Reason for the implementation:** make the
    Ability, Attack, and Both research collections portable between browser
    sessions/machines and shareable independently of the active 60-card deck.
  - CSV export writes a deterministic `card_id,flag` file containing all flagged
    cards. TXT export writes a readable grouped list under `[Ability]`, `[Attack]`,
    and `[Both]` headings with competition Card ID and card name. Files use the
    current deck name plus `_flags` so they remain distinguishable from deck CSV/
    TXT exports.
  - Added a dedicated flag-import dialog that accepts `.csv` and `.txt` files or
    pasted content. Import validates IDs against the 1,267-card local dataset,
    ignores unrecognized lines, reports skipped unknown IDs, and offers an explicit
    option to merge with current flags or replace all existing flags first. The
    imported state is persisted through the existing local-storage mechanism and
    immediately refreshes section totals and card results.
  - Deck import/export remains separate and unchanged. `main.py` and active
    `deck.csv` were not changed. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Flag interaction revised — direct buttons in expanded view only**:
  - Removed the flag dropdown from every catalog tile and replaced the expanded
    card's dropdown with three direct `Ability`, `Attack`, and `Both` buttons.
    **Reason for the implementation:** flagging is an intentional evaluation made
    while inspecting a card closely, so exposing a dropdown on every library tile
    added unnecessary visual density and did not match the requested workflow.
  - The current flag is shown as the active button. Clicking another button moves
    the card to that flag section; clicking the already-active button clears the
    flag. Catalog cards retain only a small read-only criterion badge and colored
    edge so previously flagged cards remain recognizable without presenting an
    editing control outside expanded view.
  - Persistent storage and the Card Library / Ability / Attack / Both sections are
    unchanged. Validation passed with `node --check deck_builder\app.js`, and a
    source scan confirmed the old tile and expanded-view dropdown controls were
    removed. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Persistent card flagging added — Ability, Attack, and Both catalog sections**:
  - Added independent card flags to `deck_builder/app.js` with four possible
    states: unflagged, `Ability`, `Attack`, or `Both`. Flags are stored alongside
    the existing deck state in browser local storage and restored when the deck
    builder is reopened. **Reason for the implementation:** support research and
    deck exploration before committing cards to a 60-card list, allowing useful
    cards to be collected according to whether their Ability, Attack, or complete
    card design is the reason they are being considered.
  - Added Card Library / Ability / Attack / Both section tabs above the catalog.
    Each section displays live card totals and reuses the complete existing card
    experience: artwork grid, search, card-kind/type/expansion/stage filters,
    sorting, keyboard navigation, focused-card inspection, and deck add/remove
    controls. The three flag sections are exclusive, so a card appears in the one
    section matching its current criterion.
  - Added a flag selector to every catalog card and to the expanded-card header.
    Flagged cards receive a subtle criterion-colored edge in the library. Changing
    or removing a flag immediately updates the section counts and visible results;
    if the expanded card no longer belongs to the active flagged section, the
    inspector closes back to that section cleanly.
  - Flag state remains separate from deck membership: flagging does not alter the
    60-card count, and cards can still be added or removed normally from every
    flagged section. Existing deck autosave, validation, import, and CSV/TXT export
    behavior is preserved. Validation passed with `node --check
    deck_builder\app.js`, and the updated markup contains no duplicate element IDs.
    `main.py` and active `deck.csv` were not changed. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-08-09

- **Focused-card opening stabilized — original catalog remains as the backdrop**:
  - Removed the separately rendered focus-mode background grid from
    `deck_builder/index.html`, `app.js`, and `styles.css`. The focused inspector
    now overlays the existing Card Catalog directly and applies a brief
    semi-transparent dimming fade plus a small card-entry transition.
    **Reason for the implementation:** replacing the visible catalog with a newly
    generated dark card grid caused an abrupt background change when opening an
    individual card, breaking the user's spatial context. Preserving the exact
    catalog underneath makes the transition feel continuous while keeping the
    inspected card and controls prominent.
  - Removed the unused backdrop-rendering JavaScript and added a reduced-motion
    fallback. Navigation, live deck visibility, and keyboard/visible `+` / `-`
    controls are unchanged. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Focused card inspector confined to Card Catalog — live deck remains visible**:
  - Reworked the focused-card interaction in `deck_builder/app.js` and
    `styles.css` so the inspector is mounted inside `.catalogPanel` and covers
    only the center card catalog rather than the entire browser viewport.
    **Reason for the implementation:** the full-screen inspector hid the selected
    deck, making it difficult to know which cards and quantities had already been
    added while browsing. Keeping the filter panel and right-hand deck editor
    visible preserves context and makes each add/remove decision immediately
    observable.
  - The inspector retains its centered card, dimmed neighboring cards, previous/
    next navigation, visible red `-` / `+` controls, keyboard arrow navigation,
    keyboard `+` / `-`, and Escape-to-close. Add/remove still uses the shared deck
    update path, so counts, legality feedback, composition, and selected rows in
    the right panel refresh immediately.
  - Removed the focus-mode body scroll lock and disabled the redundant internal
    deck drawer. The existing right deck panel is now the single visible source of
    truth for selected cards while the inspector is open. Responsive focus-header,
    card, arrow, and control dimensions were tightened for the smaller catalog
    container.
  - Validation: `node --check deck_builder\app.js` passed. `design-qa.md` documents
    the new scoped state and remains blocked because the integrated browser runtime
    again failed during initialization, preventing rendered screenshot comparison
    and console/interaction verification. `main.py` and active `deck.csv` were not
    changed. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Keyboard-focused card browser added — arrow navigation and direct +/- deck editing**:
  - Reworked the visual browsing interaction in `deck_builder/index.html`,
    `styles.css`, and `app.js` around the supplied game-style deck-builder
    references. Selecting card artwork now opens a full-viewport focused browser
    with a large centered card, dimmed surrounding card gallery, previous/next
    controls, a persistent deck count, large red remove/add controls, and an
    optional right-side visual deck drawer. **Reason for the implementation:**
    make rapid card comparison and deck editing practical from the keyboard and
    visually closer to the interaction model the user requested, instead of
    requiring repeated pointer travel between small catalog cards and the deck
    list.
  - Added roving keyboard navigation in the normal card grid: Left/Right move one
    card, Up/Down move approximately one grid row, Enter opens the focused card,
    and `+` / `-` add or remove the focused grid card. Every catalog tile now also
    exposes visible `-`, selected-count, and `+` controls.
  - Focus mode navigates through the complete current filtered result set with
    Left/Right or Up/Down (wrapping at the ends), supports keyboard and visible
    `+` / `-` deck editing, closes with Escape, and can toggle the deck drawer with
    `D`. Closing restores focus to the originating catalog card where available.
  - The focus-mode deck drawer shows live legality status, Pokemon/Trainer/Energy
    tabs and counts, card artwork, and selected quantities. Selecting a drawer
    card moves the centered inspector to that card without closing the drawer.
    Existing filtering, autosave, validation, import, and CSV/TXT export behavior
    remains intact; `main.py` and the active `deck.csv` were not changed.
  - Validation: `node --check deck_builder\app.js` passed and a static UI-ID check
    found no missing referenced elements. `design-qa.md` records the visual QA as
    blocked because the integrated browser runtime failed to initialize, so a
    browser-rendered screenshot comparison and interaction/console pass could not
    be completed in this environment. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Deck builder rebuilt — self-contained visual card library and interactive 60-card workspace**:
  - Replaced the first `deck_builder/index.html`, `styles.css`, and `app.js`
    implementation with an image-first deck-building workspace inspired by the
    structure of Limitless: compact filters on the left, a scrollable visual card
    catalog in the center, and a persistent grouped deck editor on the right.
    **Reason for the implementation:** the first version reported mapped images
    but referenced them through absolute `file:///C:/...` URLs outside the
    project, leaving the visible catalog blank in the browser and making the
    builder fragile whenever the external folder path or browser file policy
    changed.
  - Updated `deck_builder/generate_card_data.py` to create optimized WebP card
    previews inside `deck_builder/assets/cards/` and write relative image paths
    into `card-data.js`. All 1,267 supplied JPG card images are now packaged as
    1,267 local previews (about 38.1 MB instead of copying the 219.1 MB originals),
    so `index.html` no longer depends on external absolute image URLs.
  - The catalog now displays actual card artwork, selection-count badges, card
    names/set numbers/competition IDs, incremental result loading, search across
    names/attacks/effects, Pokemon/Trainer/Energy segmented filtering, Energy
    type, expansion, stage/trainer type, Mega, Ability, and sort controls. Clicking
    artwork opens a full preview with HP, evolution, attacks, effects, Weakness,
    Resistance, Retreat, and add/remove controls.
  - The deck workspace now has a live circular 60-card counter, Pokemon/Trainer/
    Energy composition, grouped rows with thumbnails and steppers, same-name
    four-copy enforcement across different printings, Basic Energy exceptions,
    ACE SPEC and Basic Pokemon checks, local browser autosave, deck naming, clear
    confirmation, and responsive desktop/mobile layouts.
  - Import now accepts both one-ID-per-line CSV content and grouped readable TXT
    lines. Export writes the chosen deck name to `.csv` in the one-ID-per-line
    competition format and `.txt` in the same grouped structure as
    `Decs/Hydrapple.txt`. The active submission `main.py` and `deck.csv` were not
    changed.
  - Validation: `node --check deck_builder\app.js` and
    `python -m py_compile deck_builder\generate_card_data.py` passed; regeneration
    reported 1,267 cards and 1,267 previews; an independent manifest/filesystem
    check found zero missing image paths; and a representative generated WebP was
    visually inspected and readable. The integrated browser preview could not be
    started because its connection failed during initialization, so final
    in-browser interaction remains a manual check by opening `index.html`. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Local deck builder added — interactive dataset-only deck construction/export**:
  - `deck_builder/index.html`, `styles.css`, and `app.js` — added a standalone
    browser deck builder for the cards available in this project dataset. It
    presents filters on the left, a searchable card catalog in the center, and the
    selected deck on the right. Filters include card kind, Energy/type, expansion,
    stage/trainer type, Mega-only, ability-text, and image availability.
    **Reason for the implementation:** make deck exploration faster and less error
    prone than editing ID lists by hand, while keeping the active submission
    `main.py` and `deck.csv` untouched.
  - `deck_builder/generate_card_data.py` — added a generator that groups
    `dataset/EN_Card_Data.csv` by competition `Card ID`, preserves attack/effect
    text, classifies cards as Pokemon/Trainer/Energy, and maps every card to the
    image folder at `C:\Users\novan\Desktop\Pokemon_Dataset` using expansion +
    collection number. Generated `deck_builder/card-data.js` contains 1,267 cards
    and 1,267 mapped image URLs.
  - Export support writes `deck.csv` as one card ID per line, matching
    `Decs/Hydrapple.csv`, and `deck.txt` in the grouped readable format used by
    `Decs/Hydrapple.txt`. The UI also supports pasting/importing an existing card
    ID list, live 60-card validation, non-Basic 4-copy enforcement, Basic Energy
    exceptions, ACE SPEC warnings, and Pokemon/Trainer/Energy count breakdowns.
  - Verified live: `python deck_builder\generate_card_data.py` regenerated the
    static card data; `python -m py_compile deck_builder\generate_card_data.py`
    passed; `node --check deck_builder\app.js` passed; a metadata sanity check
    confirmed 1,267 card records and 1,267 image mappings. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Mega Gardevoir ex challenger built — stable Psychic engine explored, not adopted**:
  - `Decs/Codex_MegaGardevoir.txt` / `.csv` — added a separate 60-card deck built
    around Mega Gardevoir ex, leaving the active submission `deck.csv` unchanged.
    **Reason for the implementation:** test whether Gardevoir's one-Energy
    `Overflowing Wishes` setup attack and board-wide `Mega Symphonia` scaling can
    form a stable alternative submission archetype rather than continuing to tune
    only Hydrapple and its direct counters.
  - Final composition is 16 Pokemon / 31 Trainers / 13 Energy. The 4 Ralts / 2
    Kirlia / 3 Mega Gardevoir ex core has both natural-evolution and Rare Candy
    routes. Xerneas, Smoochum, Telepathic Psychic Energy, and the Precious Trolley
    ACE SPEC provide four overlapping ways to fill or energize the Bench; Hilda,
    Mega Signal, Ultra Ball, and Buddy-Buddy Poffin provide redundant search.
    Latias ex removes Basic retreat costs, Fezandipiti ex supplies post-KO draw,
    Lillie's Clefairy ex adds Dragon coverage, Air Balloon is the Mega's retreat
    tool, and Mystery Garden converts spare Energy into draw.
  - Legal/count validation passed: exactly 60 IDs, no non-Basic card above four
    copies, and exactly one ACE SPEC. The list contains 10 Basic Psychic Energy and
    3 Telepathic Psychic Energy, leaving enough Basic Energy targets for
    `Overflowing Wishes` while making early Bench development more reliable.
  - Final stability screen: 38/40 = **95.0% versus random**, with zero draws or
    timeouts. The harder Hydrapple screen was only **7/40 = 17.5% [95% CI
    8.7-32.0%]**, so consistency against a blind opponent does not translate into
    competitive tempo against the current strong deck.
  - Several alternatives were tested and rejected: a three-Latias tempo package
    scored 4/40 versus Hydrapple; a Mega Diancie package scored 6/40; a
    single-multi-prize focused shell scored 4/40; and a denser Scream Tail hybrid
    scored 5/40. An independently created `Claude_Mega_Gardevoir` list was tied in
    direct play (Codex 18/40, 45.0%, CI spans 50%) and itself scored only 8/40 into
    Hydrapple. These small screens are not precise rankings, but every tested
    Gardevoir branch showed the same Stage-2 tempo ceiling.
  - Decision: **keep as an exploratory challenger; do not adopt**. The deck is legal,
    coherent, and functional, but current evidence says Hydrapple and the Fire
    anti-Hydrapple candidate are materially stronger under the present `main.py`.
    Improving Gardevoir further likely requires deck-specific planning in the agent
    (setup-attack timing and promotion discipline), not more blind list swaps. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **How much of a bad deck result is the DECK vs the AGENT? Measured on
  Claude_Mega_Gardevoir — a deck-aware agent nearly DOUBLES it, and still loses**:
  - Question raised: every deck above was piloted by an agent tuned on Hydrapple.
    So how much of Gardevoir's 20% was the deck being bad vs the agent being wrong
    for it? Built a Gardevoir-aware agent as a wrapper over `main.py` (no files
    modified) and ran 4 arms x 100 seat-balanced games vs Hydrapple, with Hydrapple
    always piloted by the STOCK agent:

    | arm | change | result vs Hydrapple |
    |---|---|---|
    | stock | unmodified `main.agent` | 21.0% [14.2-30.0] |
    | dmg | Mega Symphonia damage estimated **dynamically** each call as 50 x (all {P} Energy in play) | 34.0% [25.5-43.7] |
    | bench | dmg + attach Energy to the **Bench** instead of the Active | **40.0% [30.9-49.8]** |
    | full | bench + crude "force Gardevoir into the Active slot" | 38.0% [29.1-47.8] |

  - **+19 points, ~2x the win rate, from agent changes alone with the deck untouched.**
    So a meaningful share of a deck's measured score here is agent fit, not deck
    quality — deck head-to-heads under one fixed agent systematically understate any
    deck the agent cannot read.
  - Of the two changes that mattered, they are NOT the same kind of thing:
    - The variable-damage estimate is a **general** agent fix. 381 of 1556 engine
      attacks report `damage = 0`; any deck built on a scaling attacker is currently
      mis-valued. This belongs in `main.py` regardless of which deck we submit.
    - Bench-first Energy attachment is **deck-specific** and probably WRONG for
      Hydrapple (which wants its Active powered). This is genuine agent/deck
      co-tuning, and the competition submits exactly one `main.py` + one `deck.csv`,
      so co-tuning is the correct strategy rather than a compromise.
  - Forcing Gardevoir into the Active slot did NOT help (38% vs 40%, overlapping CIs).
    The gain came from the agent *evaluating* the card correctly, not from steering it.
  - Not chased further: the agent still never uses **Overflowing Wishes** (0 printed
    damage), which is the deck's actual ramp engine (+1 {P} Energy per Benched Pokémon).
    A fuller deck-aware agent would ramp with it on a wide bench, then swing. Untested.
  - Conclusion: even with a dedicated agent, Gardevoir sits at 40% vs Hydrapple while
    `Codex_FireCamerupt` reaches 66% under the *stock* agent. Gardevoir is not worth
    further investment; the variable-damage fix is, independently of deck choice.
    — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Two Claude challenger decks built and MEASURED — both LOSE; the useful output is
  a agent blind spot, not the decks (neither adopted)**:
  - `Decs/Claude_Zygarde_Ramp.txt` / `.csv` — 60-card Fighting deck, all attackers
    **Basic** (4 Mega Zygarde ex / 4 Cornerstone Mask Ogerpon ex / 4 Cornerstone Mask
    Ogerpon / 2 Regirock ex, 31 Trainers, 15 Basic {F} Energy). Thesis came from the
    2026-08-08 ladder analysis (wins avg 6.0 turns, losses avg 17.8, one loss with
    ZERO attacks in 13 turns): if we lose by never coming online, remove every
    evolution step. Two rules facts drove the picks — **Basic Megas exist**
    (`prev-stage = n/a`), so they skip the "evolving into a Mega ends your turn" cost
    (POKEMON_RULES.md sec.12); and `_best_attack_index` ranks by printed damage only,
    so drawback text is invisible. Rejected on that basis: Mega Mawile ex (260 dmg
    but base drops to **30** once the target has damage counters — the bot would spam
    30s), Gouging Fire ex, Koraidon/Latias/Yveltal/Zacian ex (next-turn lockouts),
    Pikachu ex / Black Kyurem ex (self-damage), Iron Boulder (does nothing unless hand
    sizes match).
  - Measured: `deck_head2head.py Claude_Zygarde_Ramp Hydrapple 50` → **37/100 = 37.0%
    [95% CI 28.2-46.8%]**, avg 135 steps. Hydrapple better; CI upper bound below 50%.
  - **Two hypotheses tested and BOTH refuted**, which is the point of the entry:
    1. *"`_prize_value` returns 3 for megaEx but POKEMON_RULES.md sec.12 says Mega = 2,
       so the agent over-penalizes its own Mega."* Monkeypatched to 2, re-ran:
       **23/100 = 23.0%** — WORSE. Making the agent more willing to lead with Zygarde
       made it lose harder, i.e. Zygarde in the Active slot was feeding Prizes.
    2. *"Basic attackers fix the ladder losses."* Tempo probe (12 mirror games/deck):
       Claude_Zygarde_Ramp first attack turn **3.7**, 6.9 attacks/game, **627** printed
       dmg/game; Hydrapple turn 4.0, 4.8 attacks/game, **142** dmg/game. The deck
       attacks earlier, more often, for 4.4x more damage — **and still loses**. So
       "comes online slowly" was NOT the binding constraint, and the ladder diagnosis
       does not translate into "more damage sooner => more wins". Treat the earlier
       energy-acceleration recommendation as unproven.
    - Best remaining explanation: **prize economy**. 10 of 14 Pokémon were Rule Box
      (2 Prizes per KO), so the opponent needed only ~3 KOs; Hydrapple has 13
      single-Prize bodies to absorb trades. Self-inflicted secondary bug: Cornerstone
      Mask Ogerpon's Rock Kagura is a **0-damage** attack included as a ramp trick, but
      the agent picks max damage among *legal* attacks, so on 1 Energy it attacked for
      literally 0 (avg damage/attack 91, vs Gaia Wave's 200).
  - `Decs/Claude_Mega_Gardevoir.txt` / `.csv` — 60-card Psychic deck built on request
    around **Mega Gardevoir ex** (4 Mega Gardevoir ex / 4 Ralts / 2 Kirlia / 4 Scream
    Tail ex / 2 Smoochum, 27 Trainers, 16 Basic {P} Energy). The combo is real:
    Mega Symphonia costs **1 Energy** and does **50x every {P} Energy attached to ALL
    your Pokémon**, so damage scales off the bench rather than the attacker; Smoochum's
    Delightful Kiss costs **zero** Energy and pulls 2 {P} Energy from deck onto the
    Bench; Rare Candy skips Kirlia; Buddy-Buddy Poffin fetches Ralts/Smoochum (both
    <=70 HP); Gardevoir is 360 HP.
  - Measured: v1 (support-heavy) **19/100 = 19.0% [12.5-27.8%]**; v2 (swapped the
    fragile support bodies for 4 Scream Tail ex) **20/100 = 20.0% [13.3-28.9%]**.
    Composition fix did not move it.
  - **ROOT CAUSE — the agent is blind to variable-damage attacks.** The engine reports
    `Attack.damage = 0` for "50x"-style attacks, and the agent ranks every attacker by
    that field (`_best_attack_index`, `_best_usable_damage`). So it believes Mega
    Gardevoir ex is a zero-damage Pokémon. Probe over 10 games: Gardevoir held the
    Active slot only **55 steps** while Scream Tail ex (printed 120) held **334** — the
    agent kept promoting the weaker card. Proof by experiment: patching ONLY the
    agent's view of Mega Symphonia (0 -> 200), changing no cards, moved the same
    matchup **20.0% -> 37.0%** (+17 points, one line).
  - Scope of the blind spot: **109 cards** in the pool have variable damage in the
    card data; **381 of 1556** engine attacks report `damage = 0`. That whole class of
    cards is currently un-pickable by our heuristics. Fixing it means teaching
    `_best_usable_damage` to estimate scaling attacks (for Mega Symphonia:
    50 x count of {P} Energy in play) — an **agent** change, not a deck change.
  - This is the concrete answer to "would a new deck work on the current main.py?":
    for Mega Gardevoir, **no** — it cannot function until the agent can see variable
    damage. Decision: **do not adopt either deck.** Codex's `Codex_FireCamerupt`
    (66% vs Hydrapple, logged below) is a far stronger challenger than either of
    these; both Claude decks are kept as recorded negative results with their
    measurements written into their `.txt` files. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Codex challenger deck built — Fire/Mega Camerupt anti-Hydrapple candidate
  (not adopted)**:
  - `Decs/Codex_FireCamerupt.txt` / `.csv` — added a separate 60-card challenger
    deck, leaving the active submission `deck.csv` unchanged. The concept is a Fire
    tempo deck aimed at Hydrapple's Grass weakness while staying simple enough for
    our current lookahead agent to pilot: 4 Numel / 3 Mega Camerupt ex as the main
    Mega line, Volcanion ex and Hearthflame Mask Ogerpon ex as Basic Fire attackers,
    Oricorio ex for Fire Energy acceleration once a Fire Mega is in play, and
    Flareon ex as a deck-to-board Energy accelerator. The Trainer package borrows
    the proven high-consistency shell pattern: Lillie's Determination, Ultra Ball,
    Hilda, Mega Signal, Pokégear, Firebreather, Boss's Orders, Air Balloon, and
    Surfer.
  - Legal/count validation passed locally: 60 IDs, no non-basic card above 4 copies,
    exactly 1 ACE SPEC (`Enriching Energy`). The readable `.txt` list classifies it
    as 19 Pokémon / 26 Trainers / 15 Energy.
  - Initial measurement under our current agent: `python deck_head2head.py
    Codex_FireCamerupt Hydrapple 50` finished **66/100 = 66.0%
    [95% CI 56.3-74.5%]**, avg 125 steps, 0 draws/timeouts. This is a promising
    anti-Hydrapple signal, but it is only 100 total games and should not trigger a
    deck swap by itself.
  - Sanity check into the known leaderboard-style archetype was weaker and noisy:
    `python deck_head2head.py Codex_FireCamerupt LiamK_MegaLopunny 20` finished
    **14/40 = 35.0% [95% CI 22.1-50.5%]**, avg 138 steps, 0 draws/timeouts. The CI
    still touches 50%, but the point estimate warns that this may be a targeted
    Hydrapple counter rather than a broadly stronger deck. Larger runs timed out at
    the current command budget, so this remains exploratory.
  - Decision: **do not adopt**. Keep Hydrapple as the active submission deck until a
    challenger pair proves itself across Hydrapple, LiamK-style Mega Lopunny, and the
    existing round-robin field. This deck is useful as a challenger/anti-meta probe,
    not yet as the default submission. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-08-08

- **First Kaggle submissions — two failed, root cause found and fixed (`__file__` under
  `exec()`)**:
  - Submitted to the **Simulation** competition for the first time (entry gate was
    already cleared; `user_has_entered: true`). Submissions `#55335664` and `#55351154`
    both came back `status: ERROR` / "Validation Episode failed."
  - **Root cause** (from the Agent 0 Logs attachment on the Submissions page, which is
    the ONLY place the traceback is exposed — the MCP `get_episode_agent_logs` tool
    returns a content-free stub and no public URL pattern serves it the way
    `episodes/<id>/replay.json` does):
    ```
    File "/kaggle_simulations/agent/main.py", line 55, in read_deck_csv
        local_path = Path(__file__).with_name("deck.csv")
    NameError: name '__file__' is not defined
    ```
    `kaggle_environments/agent.py` runs the submitted `main.py` by `exec()`-ing its
    source into a fresh namespace, so **`__file__` is never defined**. Every local
    execution path (normal import, `python main.py`, `run_local.py`, Docker) defines
    `__file__`, so no amount of local testing could reproduce it. The failure hit the
    very first `agent()` call (the deck-selection request, `select: null`) — visible in
    the replay as `remainingOverageTime` dropping only ~0.08s before `ERROR`.
  - Aggravating factor: the `agent()` safety net added earlier that day swallowed the
    `NameError` and returned `[]`, converting a loud crash into a silent **empty deck**
    — still invalid, but harder to diagnose. Broad `except Exception` around an entry
    point hides exactly the errors worth seeing.
  - `sample_submission/sample_submission/main.py` — `read_deck_csv()` now resolves
    `deck.csv` from `globals().get("__file__")` when present, then
    `/kaggle_simulations/agent/deck.csv`, then CWD. No bare `__file__` reference.
  - `sample_submission/sample_submission/cg/sim.py` — native engine load deferred from
    module import to first attribute access (`_LazyLib`). This was speculative — it was
    NOT the cause (the `.so` loads fine on Linux, verified in a container) — but it does
    mean a native-lib failure can no longer kill `import main` before `agent()` exists.
  - Verified live: replicated Kaggle's execution model in a Linux container
    (`exec(compile(src, "main.py", "exec"), {"__name__": "__main__"})`, no `__file__`)
    and fed it the real server-generated observation JSON pulled from a public ladder
    replay. Fixed code returns all 60 card IDs; the previously-submitted code returns
    `0` under the identical harness (negative control). Full game still completes
    (129 steps) on Linux. Resubmitted as `#55351602`.
  - Note for the Strategy writeup: the deck/agent were never the problem for those two
    submissions — this was purely a submission-harness bug, and cost ~14h of ladder time.
  - Also pulled and analysed the rank-1 opponent's deck (`Majkel1337`, 1277.8) from a
    public replay: 4× Mega Lucario ex + 4× Fighting Gong (energy accel) + 4× Premium
    Power Pro (damage boost) + 4× Judge — a 4-copy consistency build around one attacker,
    vs our 5-line toolbox with no energy-acceleration item. Their observed win rate is
    **79.2% (38-10 over 48 ladder games)**, not 100% — they trade fairly evenly with
    LiamK and flg. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Deck builder committed source-only; its card data held out as Competition Data**:
  - `.gitignore` — added `deck_builder/card-data.js` and `deck_builder/assets/`.
    Caught while staging: `card-data.js` (887 KB) is `dataset/EN_Card_Data.csv`
    repackaged as JSON — all 1,267 cards with HP, attack costs, damage and effect text
    — and `assets/cards/` is the 1,267 card images (~42 MB). Both are **Competition
    Data** under EVALUATION.md §5, and this repo's own ignore rule already says never to
    commit such files "even to a private remote you might later make public". The remote
    is currently private, so nothing leaked, but committing would have written them into
    git history permanently, where flipping the repo public or adding a collaborator
    republishes them and removal needs a history rewrite.
  - `deck_builder/generate_card_data.py` **is** committed, so `card-data.js` rebuilds
    from `dataset/` on any machine — holding the data out costs nothing.
  - Committed as `e0d5526` on `main` and pushed: deck-builder source (`index.html`,
    `app.js`, `styles.css`, the generator), `design-qa.md`, 7 new `Decs/` lists, and the
    PROGRESS entries below. Verified before committing that nothing matching
    `card-data|assets/cards|dataset/|liamk|.webp|.pyc` was staged.
  - Note on the earlier `.gitignore` edit (not mine): the ignore rule was loosened from
    `Decs/` to `Decs/LiamK_*`, so our own authored deck lists are now tracked while the
    replay-reconstructed LiamK lists stay ignored. That split is correct and is kept. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Cleanup shipped, baseline re-frozen — and the attacker-concentration hypothesis is
  FALSIFIED**:
  - `sample_submission/sample_submission/main.py` — deleted
    `_should_retreat_to_better_attacker` (~40 lines, magic thresholds 30/60/90/120 and
    a prize-exposure branch) after the ablation measured its contribution at exactly
    zero. Retreat reverted to the simple pre-2026-08-08 rule at step 7 (below "attack
    anyway", `hp <= 30% maxHp` and a healthier Bench option). Left a `ponytail:` comment
    naming the ablation result in-code so the gate is not rebuilt blind later.
    **`_live_attacker_score` was deliberately KEPT** — it is now load-bearing for
    `_choose_card`, which is where the measured gain actually lives.
  - `sample_submission/sample_submission/attacker_share.py` — new. The attacker-share
    metric had been quoted in three separate entries with no committed tool behind it
    (the 08-07 numbers came from an ad-hoc replay decode). This harness wraps the agent,
    records the Active card on every selected ATTACK option, and prints the full
    per-card ranking plus top-2 concentration. It does **not** hardcode a "real vs weak
    attacker" card list — the split is left visible in the ranking so the reader
    classifies, not the tool.
  - `sample_submission/sample_submission/retreat_ablation.py` — guarded its monkeypatch
    with `getattr`, so the harness degrades to no-op arms instead of crashing now that
    the gate it ablated no longer exists.
  - **Re-test of the cleaned agent** (vs the old frozen 07-18 baseline, so directly
    comparable to everything above):

    | test | result | reads against |
    |---|---|---|
    | `self_play_benchmark.py 500` | **71.6% [67.5-75.4]** (358/142/0), 121.6 steps | fix #2 control 72.8%, Codex's 71.2% — a **tie**, so removing the retreat gate cost nothing, exactly as the ablation predicted |
    | `benchmark.py 200` vs random | 97.0% (194/200) | 96.0% previously — healthy, no legality/crash regression |
    | `attacker_share.py 40` | **top-2 = 60.9%** | 66.3% on 2026-08-07 |

  - **The headline is the attacker-share null.** Win rate rose ~10pts while attacker
    concentration **fell** (66.3% -> 60.9%), and the weak/support share is unchanged at
    **35.6%** (Celebi 10.3%, Tapu Bulu 9.2%, Regigigas 6.3%, Applin 2.9%, Chikorita
    2.9%, Bayleef 2.9%, Dipplin 1.1%) — the same ~34-40% band logged since 08-04.
    So **attacker concentration does not drive our win rate**, and the "close the ~22pt
    concentration gap vs LiamK" target set on 2026-08-07 was aimed at a metric that does
    not convert. It should stop driving work.
  - What *did* move is the composition **within** the attackers: Teal Mask Ogerpon ex
    54.7% -> 39.7%, **Hydrapple ex 11.6% -> 21.3%**. The promotion fix routes swings to
    the deck's heavier hitter rather than concentrating them into fewer cards. The gain
    is attacker **quality per swing**, not concentration.
  - Instrument caveat, stated so the numbers are not over-read: this harness decodes
    MAIN-phase ATTACK selections on **one seat**, while the 08-07 figures came from a
    both-seats replay decode. Attacks/game are therefore **not comparable** (4.3 here vs
    14.4 there). Shares are comparable in kind; the honest claim is "concentration did
    not improve", not a precise -5.4pt delta.
  - `sample_submission/sample_submission/previous_agent.py` — **re-frozen** to the
    cleaned agent (was the 2026-07-18 pre-lookahead greedy, preserved in git at
    `7f732ba`). Reason: the old baseline had stopped discriminating — every change since
    lookahead scored 60-72% against it, so a mediocre change and a good one looked
    similar. All future deltas measure against the *current shipped* policy, which is
    also much closer to what the ladder actually pits us against. Verified the freeze:
    module imports independently of `main`, `SEARCH_MAIN=True`, retreat gate absent, and
    `self_play_benchmark.py 60` of the agent against its own frozen copy returns 45.0%
    [33.1-57.5] — a CI spanning 50%, as identical policies must.
  - Consequence for reading this log: **every win-rate number logged before this entry
    is "vs the 07-18 greedy" and every number after it is "vs the 08-08 cleaned agent".
    They are not on the same scale.** — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Fix #2 ablated — the entire gain is the CARD/promotion change; the retreat gate
  contributes nothing**:
  - `sample_submission/sample_submission/retreat_ablation.py` — new harness. Fix #2
    shipped **two** mechanisms in one measurement, so its +6.6pts could not be credited
    to either: (a) the tactical retreat gate ordered above "attack anyway", and (b)
    own-board `CARD` selection ranked by `_live_attacker_score` instead of static
    `_option_card_power`. Arm (b) fires on **every forced promotion after a KO** — far
    more often than RETREAT, which was only 3.9% of MAIN decisions (2026-08-07 table).
    The harness monkeypatches each arm off independently (same pattern as
    `eval_ablation.py`) and runs all four combinations against the same frozen
    `previous_agent`.
  - **Also added a two-proportion z-test** (`two_prop_z`) and switched attribution
    calls to it. Method note: comparing two Wilson CIs by eye is **over-conservative** —
    non-overlap implies significance, but *overlap does not imply a non-significant
    difference*. Fix #2's own headline is the example: 71.2% [67.1-75.0] vs the 64.6%
    [60.3-68.7] reference overlaps by 1.6pts, yet the correct test gives z=2.24,
    **p=0.025** — genuinely significant. The standing "refuse to act on overlapping
    CIs" rule should be read as "refuse to act without a test", not "overlap = tie".
  - **Results (500 games/arm, 2,000 games, vs frozen `previous_agent`):**

    | arm | wins | win rate | delta vs control | z | p |
    |---|---|---|---|---|---|
    | both (control) | 364/500 | **72.8%** [68.7-76.5] | — | — | — |
    | retreat_off | 352/500 | 70.4% [66.3-74.2] | -2.4 | -0.84 | 0.400 **tie** |
    | card_off | 312/500 | 62.4% [58.1-66.5] | -10.4 | -3.51 | 0.0004 **sig** |
    | neither | 314/500 | 62.8% [58.5-66.9] | -10.0 | -3.38 | 0.0007 **sig** |

  - The control also **replicates** fix #2's headline independently (72.8% here vs
    71.2% as logged), so the effect is real and not a single-run fluke.
  - **Attribution is unambiguous: `card_off` (62.4%) and `neither` (62.8%) are the
    same number.** Turning the retreat gate off costs nothing whether the CARD change
    is present or absent, i.e. the retreat mechanism is **inert**. All ~10pts belong to
    the live-attacker promotion ranking.
  - **Interpretation — the attacker-discipline hypothesis survives, but the lever was
    wrong.** Attacker choice is not decided by voluntarily retreating; it is decided at
    **forced promotion after a KO**, which happens every time something dies and was
    previously resolved by static printed card power (biggest HP + printed damage), not
    by who can actually attack right now. That is the mechanism behind the "attacks with
    whatever is already Active" flaw: the agent kept *promoting* the wrong Pokemon.
    Retreat was always the rarer and more expensive way to fix the same problem.
  - Consequence for `main.py`: `_should_retreat_to_better_attacker` (~40 lines, magic
    thresholds 30/60/90/120 and a prize-exposure branch) is now **measured dead weight**
    — unproven complexity of exactly the kind the 08-04 KO-risk term was flagged for.
    Recommend reverting the retreat portion to the pre-fix #1 rule and keeping only the
    CARD change; not done in this entry, pending decision. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Attacker-discipline retreat fix #2 — conservative tactical retreat gate (kept
  pending future challenger tests)**:
  - `sample_submission/sample_submission/main.py` — replaced the broad attempt #1
    rule ("retreat if any Benched Pokemon has higher usable damage") with a
    conservative tactical gate. Retreat still sits above "attack anyway", but now
    only fires when it turns a non-lethal line into an immediate KO or when the
    Benched attacker offers a meaningful immediate damage gain. The gate also avoids
    exposing a higher-prize attacker to an immediate KO for only a modest damage
    upgrade.
  - Added `_live_attacker_score()` and `_should_retreat_to_better_attacker()` so the
    rule is explicit and easier to tune. Also updated own-board `CARD` selections to
    prefer live in-play attackers by usable damage/HP/energy rather than static
    printed card power, so after choosing RETREAT the follow-up promoted Pokemon is
    more likely to be the actual attacker instead of merely the strongest printed
    card.
  - Reasoning: attempt #1 found the real structural issue (retreat was unreachable in
    greedy rollout whenever any attack was legal), but its fix was too blunt and
    measured as a tie with a lower point estimate. This pass keeps the valid ordering
    insight while requiring a concrete tactical payoff before giving up the current
    attack.
  - Verified live: `python -m py_compile` passed for `main.py`, `self_play_benchmark.py`,
    and `benchmark.py`; `python benchmark.py 40` finished 40/40 wins vs random;
    `python self_play_benchmark.py 200` finished current 138 / previous 62 / draw 0
    = **69.0% [95% CI 62.3-75.0%]**; `python self_play_benchmark.py 500` finished
    current 356 / previous 143 / draw 1 = **71.2% [95% CI 67.1-75.0%]**, avg 123.0
    steps. Compared with the shipped lookahead reference 64.6% [60.3-68.7%], this is
    a materially higher point estimate with only slight CI overlap, so it is kept as
    the current working version rather than rejected like attempt #1. Next useful
    check: measure attacker-share directly to confirm the win-rate gain actually
    came from fewer weak/support attacks. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Attacker-discipline attempt #1 — retreat promoted above "attack anyway" (measured
  a TIE, not shipped on evidence)**:
  - `sample_submission/sample_submission/main.py` — reordered the greedy MAIN ladder:
    the retreat rule moved from step 7 to step 6, i.e. **above** "attack anyway with
    the strongest available attack", and its gate changed from
    `active.hp <= 30% maxHp and any bench.hp > active.hp` (HP-based) to
    `any(_best_usable_damage(b) > _best_usable_damage(active))` (damage-based).
    Lethal attack remains step 1, so lethal still preempts retreat.
  - **Reasoning / mechanism found.** First hypothesis logged in discussion — "search
    never gets to consider retreat" — was **wrong**, and is corrected here:
    `_search_choose_main` enumerates *every* option index (`for i in
    range(len(sel.option))`), so RETREAT was always a legal top-level search candidate.
    The real blocker was ladder **ordering**: old step 6 returned an attack whenever
    any attack was legal, so old step 7 (retreat) was unreachable while the Active
    could swing at all. Because `_choose_main` is *also* the rollout policy inside
    lookahead (`_greedy_select` at the `search_step` tail), every rollout continuation
    also swung with whatever was Active. That explains why the 08-07 eval-term work
    (Active-quality / KO-risk) could not move the weak-attacker share (40% -> 39.2%):
    the terms were scoring lines the policy could never generate.
  - **Result: no measured gain.** `self_play_benchmark.py 500` vs the frozen
    `previous_agent` = **61.0% [95% CI 56.7-65.2%]** (305/195/0 draws), avg 123.2
    steps. The shipped lookahead config on the identical harness is **64.6%
    [60.3-68.7]**. The CIs overlap across most of their range, so this is a
    **statistical tie with a 3.6pt lower point estimate** — i.e. no evidence of
    improvement, and a hint of regression that is itself not significant.
  - Per the standing rule (do not ship on overlapping CIs; do not act on noise), this
    is **not** treated as an improvement. Left in the tree pending one follow-up
    measurement of the attacker-share metric, because a *moved share with flat win
    rate* would be a genuine finding — it would mean attacker concentration does not
    convert to wins on Hydrapple, and that imitating LiamK's 88.7% figure is chasing
    a metric with no payoff. If the share is unmoved, the change is simply reverted
    as rejected fix #4. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Discussion with Codex and me — clarified what we are actually optimizing**:
  - We clarified that the final Kaggle submission should be treated as a paired
    product: **`main.py + deck.csv`**. The goal is not to build a universally perfect
    Pokemon TCG agent in isolation, and it is not to pick a strong-looking deck in
    isolation. The goal is to submit the strongest measured pairing: an agent that
    pilots the submitted deck as well as possible against other teams' own
    `main.py + deck.csv` combinations.
  - Current stable baseline remains **Hydrapple + lookahead `main.py`**. Hydrapple is
    not assumed to be the final answer forever, but it is the safest current
    submission candidate because it has already been validated under our own agent.
    Copying LiamK's Mega Lopunny / Mega Froslass deck did not create a measurable
    gain under our pilot: LiamK deck vs Hydrapple was a statistical tie. Therefore
    LiamK's leaderboard strength should be read as a **deck + agent execution**
    result, not as proof that the deck alone is superior for us.
  - The useful lesson from LiamK is behavioral, not just deck-list based. Their agent
    appears to spend much more compute, takes more useful actions per turn, attaches
    or accelerates Energy more often, and concentrates attacks through real attackers.
    Our known gap is still that Hydrapple sometimes attacks with weak or support
    Pokemon instead of converting through Teal Mask Ogerpon ex / Hydrapple ex /
    Meganium-style attackers. The next `main.py` work should focus on attacker
    discipline, tempo, attachment/acceleration sequencing, retreat/promotion choices,
    and using more of the available search budget.
  - We also agreed that exploring another strong or anti-meta deck in parallel is
    reasonable. Hydrapple progress should not be halted or discarded, but a challenger
    deck can be developed separately. The rule is: **do not replace Hydrapple unless
    `new deck + adapted main.py` clearly beats `Hydrapple + current/improved main.py`
    under enough games**. Paper strength, type coverage, or leaderboard imitation is
    not enough; the candidate must be strong under our actual agent logic.
  - Working principle going forward:

    ```text
    final strength = deck potential * agent execution
    ```

    A strong deck with mismatched agent logic can underperform, and a good agent with
    a low-ceiling deck is limited. The winning target is the strongest measured pair.
    Immediate priorities are: keep improving Hydrapple execution as the stable path,
    add/track attacker-discipline and tempo metrics, widen/deepen search where useful,
    and test any challenger deck against Hydrapple and LiamK-style baselines before
    considering a switch. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-08-07

- **Behavioral comparison vs the #1 agent — two concrete gaps found**:
  - Replays carry the **full observation**, including `select.option` for every
    decision and `remainingOverageTime`. So the #1 agent's actual *choices* can be
    decoded (map each chosen action index back to its `OptionType`), and its compute
    consumption read directly. Extracted 40 of LiamK's episodes and measured our own
    agent on the identical metrics (40 Hydrapple mirror games).

    | metric | LiamK (#1, 1202) | ours (lookahead) |
    |---|---|---|
    | avg steps / turns per game | 158 / **13.3** | 139 / **16.1** |
    | MAIN decisions per game | **48.5** | 40.8 |
    | PLAY | 36.9% | 42.1% |
    | **ATTACH** | **25.4%** | **13.1%** |
    | ATTACK | 12.6% | 11.6% |
    | ABILITY | 10.9% | 13.4% |
    | END | 8.0% | 9.3% |
    | EVOLVE | 3.8% | 6.6% |
    | RETREAT | 2.4% | 3.9% |
    | **think time per game** | **15.51s** | **~0.5s** |

  - **GAP 1 — compute. They spend ~30x more time per decision than we do.** LiamK
    burns 15.51s of the 600s per-game overage bank; our lookahead uses roughly 0.5s.
    Both are far under the cap (they use 2.6% of it, we use ~0.08%), so **the budget
    is nowhere near binding for either of us** — consistent with the earlier timing
    probe (1.8ms per one-turn rollout, ~2,200 rollouts/decision affordable). Our
    1-ply/one-candidate-per-option search is simply far shallower than theirs. This
    is the clearest headroom we have: deeper or wider search is affordable *today*.
  - **GAP 2 — attacker discipline.** LiamK's attacks are overwhelmingly by their two
    real attackers: **Mega Lopunny ex 55.9% + Mega Froslass ex 32.8% = 88.7%**, with
    only ~11% by utility Pokémon (Fan Rotom, Buneary, Dunsparce). Ours: Teal Mask
    Ogerpon ex 54.7% + Hydrapple ex 11.6% = **66.3%**, leaving **~34% of attacks made
    by weak/support Pokémon** (Celebi, Chikorita, Applin, Bayleef, Regigigas, Dipplin,
    Tapu Bulu). This independently confirms the "attacks with whatever is already
    Active" flaw logged earlier — and quantifies the target: close a ~22pt gap in
    attacker concentration.
  - **Tempo signature:** they take *more* actions per turn (48.5 MAIN decisions over
    13.3 turns) yet finish in **~17% fewer turns** than us (16.1). Their much higher
    ATTACH rate (25.4% vs 13.1%) is the mechanism — they build a board faster and
    convert sooner, rather than spending turns cycling cards. Note only one *manual*
    energy attach is legal per turn, so their surplus ATTACHes come from card/ability
    effects: their Trainer-heavy (36) build is doing real work.
  - Caveats recorded so these are not over-read: LiamK's 60% win rate is **vs the
    live ladder field**, while our 55% is a **mirror self-match** (same agent and deck
    both seats) — those two numbers are *not* comparable and no conclusion is drawn
    from them. Their think time is engine-measured overage; ours is local wall clock —
    different instruments, but the ~30x order-of-magnitude gap is well outside
    measurement error.
  - `.gitignore` — added `liamk_behavior.json` (another team's replay-derived data;
    Competition Data, not redistributable). — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Leaderboard #1 (LiamK) deck extracted and tested — no deck change**:
  - Method (all public, and explicitly sanctioned by the competition Data page, which
    says replays from other teams are downloadable from the Leaderboard): the
    leaderboard replay viewer calls **`GET /competitions/episodes/{id}/replay.json`**,
    which needs no auth, and `POST /api/i/competitions.EpisodeService/ListEpisodes`
    with `{submissionId}` lists a submission's episodes. In a replay, an agent's
    **deck is simply its `steps[1]` action** (the 60 card IDs returned during the
    deck-selection phase), and `info.TeamNames` identifies which seat is whose. Found
    the endpoint by clicking the replay button and reading the network log after
    guessing endpoint names failed.
  - Sampled **60 of LiamK's 241 episodes** (submission 55248965, rating 1202.1).
    **Every game used one identical 60-card list** — no deck variation at all.
    Sample record 42W-18L (70%). Saved as `Decs/LiamK_MegaLopunny.txt` / `.csv`.
  - **The deck is a Mega Lopunny ex / Mega Froslass ex dual-Mega build**: 16 Pokémon
    (4 Dunsparce, 3 Dudunsparce, 2 Buneary, 2 Mega Lopunny ex, 2 Snorunt, 2 Mega
    Froslass ex, 1 Fan Rotom), 36 Trainers (4 each Buddy-Buddy Poffin / Lillie's
    Determination / Poké Pad / Ultra Ball / Wally's Compassion, 3 each Air Balloon /
    Battle Cage / Hand Trimmer / Hilda, 2 each Boss's Orders / Pokégear 3.0), 8 Energy
    (4 Mist, 3 Basic {W}, 1 Enriching). Notably thin on Pokémon and Energy, very
    Trainer-heavy — a consistency-first build.
  - **Independent corroboration of our own measurement:** this is the same archetype as
    our `Decs/Mega_Lopunny_ex`, which our lookahead round-robin had already ranked
    statistically tied for #1 (70.9% vs Hydrapple 71.0%). Two independent methods —
    our simulation and the actual leaderboard — converged on the same archetype.
    Theirs is a refinement of ours: adds the Snorunt/Mega Froslass ex line (+3 Basic
    Water Energy to power it) and 3 Hand Trimmer; cuts Psyduck, Abra, Dudunsparce ex,
    Spiky Energy; trims Boss's Orders 4->2 and Pokégear 4->2.
  - `sample_submission/sample_submission/deck_head2head.py` — new seat-balanced
    two-deck comparison harness (Wilson CI, avg game length, explicit timeout count so
    long games are reported rather than silently dropped).
  - **Decisive test: LiamK's deck vs Hydrapple, piloted by OUR agent = 49.2%
    [43.1-55.4%] over 250 games, 0 timeouts — a TIE. No deck change.** The important
    read is that **their #1 rating is driven by their agent, not by a copyable deck**:
    under our pilot their list is worth nothing extra over what we already run. This
    is more evidence for the deck<->agent coupling already logged — their build almost
    certainly needs sequencing our generic agent does not execute (Mega evolution
    timing, Froslass ability use, Hand Trimmer loops).
  - `.gitignore` — added `liamk_decks.json` and `.playwright-mcp/`. Another team's
    downloaded replay data is Competition Data and must not be redistributed. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Round-robin re-run WITH lookahead; submission deck re-validated (kept)**:
  - `sample_submission/sample_submission/round_robin.py` — **fixed a result-invalidating
    bug found before launching.** The harness passed each deck to the *engine*, but the
    lookahead builds its hidden-info predictions from `_MY_DECK`, which defaults to the
    submission `deck.csv`. So every seat would have predicted **Hydrapple's** cards while
    piloting a different list — systematically biasing the comparison toward the exact
    deck under test. Added `seat_agent(deck_ids)` to bind the right deck per seat. Also
    hit a Python shadowing trap: the module-level `def main():` rebound the name over
    `import main`, so `main._MY_DECK = ...` would have set an attribute on the *function*
    and then crashed on `main.agent`; renamed to `import main as agent_mod`. Added an
    optional output-filename argument.
  - **Deck ranking with lookahead** (50 games/ordered pair, 3,200 games, seat-averaged),
    vs the earlier greedy-pilot ranking:

    | Deck | greedy | lookahead | delta |
    |---|---|---|---|
    | Hydrapple | 74.7% | 71.0% | -3.7 |
    | Mega_Lopunny_ex | 64.3% | **70.9%** | **+6.6** |
    | Marnie's_Grimmsnarl_ex | 57.0% | 61.0% | +4.0 |
    | Team_Rockets_Honchkrow | 48.7% | 51.6% | +2.9 |
    | Mega_Kangaskhan_ex | 42.9% | 46.4% | +3.5 |
    | Mega_Absol_ex | 40.0% | 42.4% | +2.4 |
    | Mega_Latias | 49.4% | **41.0%** | **-8.4** |
    | Hide_n_Sneak | 23.0% | 15.7% | -7.3 |

  - Finding: **the pilot changes the deck landscape.** Mega_Lopunny_ex gained most from
    lookahead (+6.6) and Mega_Latias lost most (-8.4), collapsing the previously clear
    Hydrapple lead into a dead heat (71.0 vs 70.9 — noise at n=50/cell).
  - **Decisive head-to-head to settle the submission deck:** Hydrapple vs
    Mega_Lopunny_ex, 500 seat-balanced games = **47.4% [95% CI 43.1-51.8%]** — CI spans
    50%, i.e. a statistical **tie** (Hydrapple 50.0% as P0, 44.8% as P1).
  - **Decision: keep Hydrapple as the submission deck.** There is no significant
    advantage either way, so switching would be chasing noise — the same mistake the
    earlier 100-game 60/40 result caused. Documented rather than churned. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Lookahead SHIPPED ON: +15.6pts, with a corrected attribution**:
  - `sample_submission/sample_submission/main.py` — extended `_eval_state` (v2) with
    `_can_pay` (typed/Colorless attack-cost check, RAINBOW as wild),
    `_best_usable_damage` (highest damage a Pokémon can actually afford right now),
    and `_prize_value`; the eval now adds an **Active-attacker quality** term
    (`best_usable_damage*2 + energies*5`) and an **opponent-KO-back risk** penalty
    (`-300 * prize_value` if their Active can KO mine next turn). Set
    `SEARCH_MAIN = True`.
  - `sample_submission/sample_submission/eval_ablation.py` — new harness that
    monkeypatches `_eval_state` variants (full / no_ko / no_quality / base-v1) and
    runs each against the frozen `previous_agent`, so gains are attributed to a
    specific term instead of a bundle (a repeat criticism of earlier passes).
  - **Headline result — lookahead is a large, real win.** Same Hydrapple deck on
    both seats, vs frozen greedy: **control greedy-without-lookahead 49.0%
    [43.4-54.6] (n=300)** vs **lookahead 64.6% [60.3-68.7] (n=500)** — **+15.6pts**,
    CIs cleanly separated. Average game length also fell 131.9 -> 121.6 steps
    (faster, more decisive wins). `benchmark.py 200` = 192/200 (96.0%) vs random.
  - **Correction to the 2026-07-20 diagnosis.** That entry concluded 1-ply lookahead
    failed (45%) because "the eval is myopic". That was **wrong**. The ablation shows
    the *unchanged v1 naive eval* now scores **61.5% [54.6-68.0]** — the only thing
    that changed in between is the submission deck (auto-built Water -> Hydrapple).
    Lookahead's value is **deck-dependent**: it exploits Hydrapple's ability-driven
    energy engine and had little to work with in the clunky Water list.
  - **My v2 eval terms are within noise.** Ablation (n=200 each): full 63.5%
    [56.6-69.9], no_ko 64.0% [57.1-70.3], no_quality 56.0% [49.1-62.7], base-v1
    61.5% [54.6-68.0] — all CIs overlap, and dropping the KO-back term changes
    nothing (64.0 vs 63.5). The shipped config is the full eval because it carries
    the largest sample (n=500), but the KO-risk term is **unproven complexity on
    probation**, not a demonstrated improvement.
  - The Active-quality term also failed at its stated purpose: the weak-attacker
    share (Applin/Chikorita/Bayleef/Dipplin/Celebi/Regigigas/Tapu Bulu) is
    **39.2%** of attacks, essentially unchanged from the ~40% baseline. Attack
    composition did concentrate on the main attacker though (Teal Mask Ogerpon ex
    28.8% -> 43.6% of attacks) and total attacks per 40 games fell 785 -> 574, i.e.
    fewer, more decisive swings. Net: the win comes from lookahead selecting better
    *lines*, not from the specific eval terms designed for attacker choice. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Hydrapple deck-execution audit (verification of the deck swap)**:
  - Independently verified Codex's deck swap: `deck.csv` is byte-identical to
    `Decs/Hydrapple.csv` (60 lines) and `benchmark.py 60` reproduced 57/60 = 95.0%
    vs random. Swap confirmed correct and kept.
  - Ran `watch_game.py` on the new deck to check whether the agent actually executes
    Hydrapple's game plan (the Deck-Score question: are key cards *utilized*, not
    just present). **First single game was misleading** — it showed zero Hydrapple ex
    deployment and 13/13 attacks by Teal Mask Ogerpon ex, suggesting the deck's
    namesake line was dead weight. A 40-game instrumented re-run **corrected that**:
    Hydrapple ex evolves 89 times (~2.2/game) and attacks 85 times, so the engine
    does work. Noting the correction explicitly because the n=1 conclusion was wrong
    and nearly drove a deck rebuild.
  - **Real finding from the 40-game attacker distribution** (total attacks by card):
    Teal Mask Ogerpon ex 226, Meganium 85, Hydrapple ex 85, Celebi 84, **Applin 80**,
    Fezandipiti ex 53, Regigigas 48, **Chikorita 42, Bayleef 33, Dipplin 26**, Tapu
    Bulu 13, Meowth ex 10. Roughly **40% of attacks come from weak basics/unevolved
    intermediates** (Applin 40HP, Chikorita, Bayleef, Dipplin) rather than the deck's
    real attackers. The agent attacks with whatever is already Active instead of
    promoting the right attacker — the known tempo/misallocation flaw in a new form,
    consistent with the deliberately conservative retreat rule (only retreat at
    <=30% HP). Confirms the Ogerpon energy engine IS used (Teal Dance ability fires
    for energy accel + draw), so the deck/agent pairing is sound; the gap is
    attacker selection, not deck construction. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

## 2026-08-04

- **Submission deck swapped to Hydrapple**:
  - `sample_submission/sample_submission/deck.csv` — replaced the auto-built Water
    Stage-2 deck with the measured Hydrapple deck from `Decs/Hydrapple.csv`.
    Reasoning: the full 8-deck round robin already showed Hydrapple as the strongest
    deck under the current generic heuristic pilot (74.7% mean seat-neutral win rate
    vs the field), so leaving the weaker Water deck as the actual submission deck was
    unused measured value. This is the lowest-risk, highest-ROI deck-score/model-score
    improvement before further agent work.
  - `PLAN.html` — updated the completion board to mark Hydrapple as the active
    submission deck, reject the auto-built Water list for final submission, and mark
    deck-vs-deck measurement as done via the round-robin harness. Reasoning: the plan
    should reflect the current decision frontier: deck selection is now measured and
    cashed in; the remaining high-ceiling work is agent eval/lookahead.
  - Verified live: `Decs/Hydrapple.csv` and the copied submission `deck.csv` are both
    60 lines; `python -m py_compile` passed for runtime Python files; `python
    benchmark.py 200` with Hydrapple finished 190/200 wins (95.0%) against random;
    `python run_local.py` completed one local match and wrote `result.txt`. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

- **Hackathon completion board**:
  - `PLAN.html` — added a static browser-openable planning board with tracks for
    submission correctness, measurement, agent strategy, deck strategy, report
    evidence, and final polish. Reasoning: the project now needs a controlled
    finish path rather than reactive heuristic tuning; an HTML board is easier to
    scan during the remaining hackathon days than a long markdown checklist.
  - The plan records current measured state (self-play neutrality over 500 games,
    random-smoke strength, and remaining tempo/stall debt), explicitly keeps the
    rejected one-rule tempo fixes rejected, and separates agent-quality work from
    deck-quality measurement so future changes are not mixed together. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-07-20

- **MAIN-phase 1-ply lookahead (built, measured, shipped OFF)**:
  - `sample_submission/sample_submission/main.py` — added a 1-ply lookahead for MAIN
    decisions behind a `SEARCH_MAIN` flag. Refactored the greedy dispatch into
    `_greedy_select(obs)` (reused as both the default policy and the rollout policy).
    New pieces: `_eval_state` (prizes×1000 + board-HP diff + Active energy, from a
    fixed my-index perspective, terminal win/loss = ±1e9), `_predictions` (mirror
    hidden-info fill for `search_begin`), `_rollout_score` (fork via `search_begin`,
    apply a candidate first action, greedily play out the rest of my turn via
    `search_step`, eval the end-of-turn board), and `_search_choose_main` (score
    every MAIN option's greedy continuation, pick the best; return None → greedy
    fallback on any failure).
  - **Measured WORSE than greedy and shipped OFF.** Verified search actually engages
    (33/33 P0 MAIN decisions, 0 errors — not a silent fallback). `self_play_benchmark
    200` (current lookahead vs frozen 07-18 greedy) = **45.0% [95% CI 38.3-51.9%]**,
    vs ~49% for greedy-without-lookahead — i.e. ~4pts worse, at the edge of
    significance. Set `SEARCH_MAIN = False` so the stronger greedy policy ships; all
    lookahead code kept behind the flag for iteration.
  - Diagnosis of why 1-ply didn't pay off: (1) the greedy rollout tail masks the
    first action — most candidates converge to similar end boards, so search
    differentiates on HP/energy noise and loses to greedy's clean lethal-first
    priority; (2) the eval is myopic (end-of-MY-turn only, ignores the opponent's
    KO-back on their turn — greedy's tuned retreat/priority implicitly handles some
    of that); (3) mirror-fill pollutes rollouts — draw/search cards in the sandbox
    pull from the predicted deck, not real draw order. Next-iteration levers:
    richer eval (opponent lethal-next-turn / Active survivability / prize race),
    or restrict search to specific decisions (attack timing) instead of all MAIN
    options. Paused for design discussion before iterating. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Search-API timing probe (lookahead feasibility)**:
  - `sample_submission/sample_submission/time_probe.py` — at 25 real MAIN decision
    points in a live game, times the cabt search API (`search_begin` /
    `search_step` / `search_end`) to size a future lookahead. Builds the hidden-info
    args `search_begin` requires (my deck/prize, opponent deck/prize/hand at exact
    counts; identities are valid-but-arbitrary for a pure speed test), rolls forward
    one turn, and reports rollouts-per-budget. Also read the env budget from
    `cabt.json`: `actTimeout=0`, `runTimeout=2000`, `remainingOverageTime=600` (a
    ~600s per-game bank).
  - **Results (Hydrapple mirror, 25 points, 0 failures):** `search_begin` median
    0.26ms, `search_step` median 0.17ms, one full one-turn rollout (begin + ~8
    steps) median **1.8ms** (max 3.9ms). A ~150-decision game averages ~4000ms per
    decision, i.e. **~2,200 rollouts/decision** available; even a conservative 200ms
    gives ~110.
  - **Conclusion: time does not constrain the lookahead design.** 1-ply search over
    a handful of candidate lines is trivially affordable; multi-ply / hundreds of
    rollouts also fit. The real constraints are (1) state-eval quality — with speed
    free, lookahead quality rides entirely on the board-scoring function — and (2)
    hidden-info prediction: the probe fed *true* decks, but a real agent must guess
    the opponent's deck/hand, which affects rollout realism (decision quality), not
    speed. Next: discuss eval design + opponent modeling before building 1-ply. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Full 8-deck round-robin (seat-bias-cancelled deck ranking)**:
  - `sample_submission/sample_submission/round_robin.py` — plays every ordered deck
    pair (A as P0 vs B as P1) for 50 games, heuristic agent both seats (3,200 games
    total), then seat-averages each pairing —
    `winrate(A vs B) = mean(P0win(A,B), 1 - P0win(B,A))` — to cancel the engine's
    first/second-seat bias. Writes `round_robin_results.md` (ranking + seat-averaged
    matrix + raw matrix + mirror seat-bias check).
  - **Deck strength ranking (mean seat-neutral win% vs field):**
    1. Hydrapple — 74.7%  2. Mega_Lopunny_ex — 64.3%  3. Marnie's_Grimmsnarl_ex —
    57.0%  4. Mega_Latias — 49.4%  5. Team_Rockets_Honchkrow — 48.7%
    6. Mega_Kangaskhan_ex — 42.9%  7. Mega_Absol_ex — 40.0%  8. Hide_n_Sneak — 23.0%.
  - Findings: **Hydrapple is dominant** (beats every deck 52-96%, only near-even vs
    Mega_Lopunny), **Hide_n_Sneak is clear last** (loses to all, 4% vs Hydrapple).
    The mirror seat-bias check varied by deck (raw P0% 42-60%), so seat advantage is
    noisier/less uniform than the single ~58/42 inferred from the earlier
    Hide_n_Sneak-only run; the seat-averaging cancels it either way. Caveat: this is
    deck power **under the generic heuristic pilot** — decks whose plan survives naive
    play (Hydrapple's Ogerpon energy accel) are favored over combo-reliant decks
    (Hide_n_Sneak). Actionable: with the current agent, **Hydrapple is the strongest
    deck to submit**, clearly better than the auto-built Water `deck.csv`. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Competitive deck ingestion pipeline + first cross-deck matchup results**:
  - `scripts/check_decks.py` — cross-references every `Decs/*.txt` deck list against
    the dataset by normalized name (apostrophe-safe, basic-energy aliasing), reports
    per-card Card ID matches and buildability. Fixed a real dataset typo it surfaced:
    card id 19 was `Telepath Psychic Energy` -> corrected to `Telepathic Psychic
    Energy` in `dataset/EN_Card_Data.csv`, which unblocked Hide_n_Sneak. `Special Red
    Card` (not in pool) was swapped to `Judge` (id 1213) in the two decks that needed
    it. End state: **all 8 decks build legally (60/60)**.
  - `scripts/annotate_decks.py` — rewrites each `Decs/*.txt` card line to
    `<count> <Card Name> - <Card ID>` using the same matcher; 0 unmatched across all
    decks. Section headers were also flipped to `<N> - <Section>` form per request.
  - Converted every annotated `Decs/*.txt` into a 60-line Card-ID `Decs/*.csv`
    (count-expanded, one ID per line) — drop-in decks for the engine/visualizer.
  - `sample_submission/sample_submission/decks_matchup.py` — runs P0 fixed =
    Hide_n_Sneak vs each of the 8 decks as P1, heuristic agent on both seats, 100
    games each, recording win/loss/draw + avg steps.
  - **Results (P0 = Hide_n_Sneak, heuristic mirror, 100 games each):**

    | P1 opponent | P0 win% | avg steps |
    |---|---|---|
    | Hide_n_Sneak (mirror) | 42.0% | 129.5 |
    | Team_Rockets_Honchkrow | 29.0% | 127.2 |
    | Mega_Absol_ex | 26.0% | 131.3 |
    | Marnie's_Grimmsnarl_ex | 23.0% | 141.3 |
    | Mega_Latias | 22.0% | 125.8 |
    | Mega_Lopunny_ex | 17.0% | 120.6 |
    | Mega_Kangaskhan_ex | 12.0% | 125.2 |
    | Hydrapple | 5.0% | 108.0 |

    Observations: (1) the mirror is **42% for P0**, i.e. a ~58/42 **seat bias
    favoring P1** (second seat) with identical decks — all P0 win rates here are
    depressed ~8pts by that, so read them relatively, not absolutely. (2) Even
    adjusting for seat, **Hide_n_Sneak underperforms every opponent** — worst vs
    Hydrapple (5%) and Mega_Kangaskhan_ex (12%). (3) These are *deck* strength
    signals under a *fixed* agent — the first real measurement of deck quality
    (previously impossible: self-play mirrored the same deck on both sides). The
    agent plays all decks with the same generic heuristic, so weak results partly
    reflect the heuristic not piloting these archetypes' combos, not only raw deck
    power. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Deck availability check + official visual replay renderer**:
  - `scripts/check_decks.py` — parses the user-authored deck lists in `Decs/`
    (standard PTCG export format: `count Name SET Collector`) and cross-references
    every card against `dataset/EN_Card_Data.csv` by normalized name, reporting per
    card whether it exists in the competition pool (with the matched Card ID / set)
    and whether a legal 60-ID cabt deck is buildable. Handles two matching
    footguns found live: (1) basic energies are named `Basic {W} Energy` in the
    dataset but `Water Energy` in the deck lists — added an element alias map; (2)
    the accent-strip step was deleting curly apostrophes (`’`) before they could be
    unified with straight ones, desyncing names like `Boss's Orders` — fixed by
    unifying/removing apostrophes before the ASCII strip.
  - Result: **5 of 8 decks are fully buildable** in the competition pool —
    Marnie's_Grimmsnarl_ex, Mega_Absol_ex, Mega_Kangaskhan_ex, Mega_Lopunny_ex,
    Team_Rockets_Honchkrow. **3 are not** — Chien-Pao_ex (17 cards absent, incl.
    Chien-Pao ex itself), Great_Tusk (14 absent), Hide_n_Sneak (only 3 absent:
    Gwynn, Prism Tower, Telepathic Psychic Energy). Finding: the competition pool
    is a **curated subset** missing many standard-format staples (Nest Ball, Super
    Rod, Counter Catcher, standalone Iono, Artazon, Radiant Greninja, Professor
    Sada's Vitality); it skews toward the newest sets (MEG/DRI/ASC/POR), which is
    why the buildable decks all lean on those.
  - `sample_submission/sample_submission/render_replay.py` — renders a watchable
    interactive HTML replay of one battle using the **official Kaggle visualizer**
    (`env.render(mode="html")`). Unblocked the `kaggle-environments` install that
    failed earlier (it pulls `litellm` → needs Rust) by installing with
    `pip install --no-deps kaggle-environments`; the `cabt` environment (v1.32.2)
    ships its own engine binaries + a Vite-built visualizer, and the core deps
    (numpy/jsonschema/requests) were already present. Script runs any two agents
    (`--p0/--p1 heuristic|random`) with optional custom decks (`--deck0/--deck1`)
    and writes `replay.html` (a self-contained interactive player — step/scrub
    through the match visually), `--open` launches the browser.
  - Note for runners: `render_replay.py` needs the WindowsApps Python 3.11 (the
    same interpreter that already runs the `cg` scripts), invoked as `python3`
    here — `kaggle-environments` is installed there, not in every Python on PATH.
  - Verified live: `python scripts/check_decks.py` produced the 5/8-buildable
    report above; `python3 render_replay.py --p1 random` ran a full game
    (heuristic P0 beat random P1 in 97 steps) and wrote a 2.8 MB `replay.html`
    confirmed to contain the interactive renderer/player. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

---

## 2026-07-19

- **Higher-confidence benchmarking + tempo diagnostics**:
  - `sample_submission/sample_submission/self_play_benchmark.py` — changed the
    default run size from 100 to 500 games and added a Wilson 95% confidence
    interval to the current-vs-previous win-rate report. Reasoning: the earlier
    60/40 over 100 games was too weak to treat as conclusive; self-play is the
    right yardstick, but it needs enough samples and uncertainty reporting to be
    useful.
  - `sample_submission/sample_submission/tempo_diagnostics.py` — added a local
    diagnostic harness that runs heuristic-vs-random games and counts MAIN states,
    attack availability, attack selections, no-attack states, PLAY availability,
    PLAY selections, END selections, and big-hand END selections. Reasoning: the
    watched-game evidence showed tempo/stall behavior, but future fixes need
    counters that quantify the symptom instead of relying only on hand-read replay
    transcripts.
  - Re-tested the prior live-targeting/evolve-unification policy with the stronger
    self-play harness. Result: `python self_play_benchmark.py 500` ended current
    246 / previous 254 / draw 0, current win rate 49.2% with 95% CI 44.8%-53.6%,
    average 131.9 steps. Reasoning: the old 100-game 60/40 result was noise; this
    policy should be treated as neutral against the frozen previous baseline, not as
    a proven improvement.
  - Tried two tempo fixes and rejected both after measurement: (1) playing useful
    Trainers only when no attack was available regressed to current 238 / previous
    262 over 500 games; (2) retreating to a Benched Pokémon that already had enough
    Energy to attack regressed to current 227 / previous 273 over 500 games. Neither
    policy change was kept. Reasoning: reducing visible stall counters is not enough
    if self-play gets worse; the benchmark is now doing its job by blocking fragile
    heuristic changes.
  - Final retained diagnostics: `python tempo_diagnostics.py 100` finished P0 97 /
    P1 3 / draw 0, with 4,085 MAIN states, 2,317 attack-available states, 1,768
    no-attack states, 836 MAIN END selections, and 363 big-hand END selections.
    Reasoning: tempo/stall remains real and measurable, but the safe next fix likely
    needs deeper Energy/Trainer sequencing or search-based lookahead rather than a
    one-rule patch.
  - Verified live: `python -m py_compile` passed for all changed Python files;
    `python benchmark.py 200` finished 195/200 wins (97.5%) against random;
    `python run_local.py` completed one match and wrote `result.txt`; `python
    scripts/build_deck.py` regenerated the same legal 60-card deck. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-07-19

- **Step-by-step battle watcher + first behavioral observations**:
  - `sample_submission/sample_submission/watch_game.py` — human-readable
    turn-by-turn replay of one match. Prints a per-turn board summary (both
    players' Active HP/energy, Bench, hand size, prizes left), each decision the
    acting agent makes decoded to English (`ATTACH`, `PLAY`, `EVOLVE`,
    `ATTACK 'Aqua Launcher' (210 dmg)`, `RETREAT`, `END`), and the resulting game
    events decoded from the observation `logs` (draws, plays, attaches,
    evolutions, attacks, HP changes, special conditions, coin flips, KO/win).
    Skips noise events (shuffles, face-down moves, turn-start/end markers). Runs
    `python watch_game.py` (heuristic mirror) or `python watch_game.py random`
    (heuristic P0 vs random P1); redirect to a file for a full transcript.
    Reasoning: `visualize_data()`/`result.txt` is a 1.6 MB per-step JSON dump, not
    something a human can read — the watcher is the tool for actually seeing *why*
    the agent wins or loses, which the benchmarks (win/loss tallies only) cannot
    show. Includes UTF-8 console reconfigure (Windows cp1252 was mojibaking card
    names) and slot-index fallback display for options whose `cardId` is None.
  - **Observations from the first watched games** (heuristic vs random) — logged
    as future Strategy-writeup evidence, not yet acted on:
    - The agent **hoards cards**: reached 15-16 cards in hand by ~turn 45 while
      repeatedly playing `END turn` with a full bench. The greedy ladder only
      attacks when the Active already has enough Energy, so a poorly-energized
      Active just passes the turn — lots of dead turns, games dragging to 45+
      turns. Against a real opponent that tempo loss likely costs games.
    - The **secondary line carried the win**, not the primary: Clawitzer's
      Aqua Launcher (210 dmg) one-shot a 180-HP Mamoswine for the last prize,
      while the "primary" Swinub->Piloswine->Mamoswine line mostly sat on the
      bench. Suggests the deck's line priority (4/3/2 primary vs 3/3 secondary)
      may be backwards for how the agent actually plays.
    - Net: two concrete heuristic weaknesses to target next — (1) press damage /
      attack more aggressively instead of stalling, (2) energy routing that
      actually powers an attacker toward a usable attack. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Delta-sensitive benchmark + live target selection pass**:
  - `sample_submission/sample_submission/previous_agent.py` — added a frozen copy
    of the 2026-07-18 heuristic policy. Reasoning: once the agent already beats
    random play almost every game, future tuning needs a stable previous-policy
    opponent so regressions are visible instead of hidden behind a saturated random
    benchmark.
  - `sample_submission/sample_submission/self_play_benchmark.py` — added current
    `main.agent` vs frozen `previous_agent.agent` self-play with mirrored decks,
    alternating first player, win/loss/draw tallies, and average step count.
    Reasoning: this is now the primary yardstick for heuristic deltas; the random
    benchmark remains useful as a crash/legality smoke test, not as the main quality
    metric.
  - `sample_submission/sample_submission/main.py` — added live-board target lookup
    for Active/Bench options and damage-target scoring that consults current
    `Pokemon.hp`/`maxHp`, damage taken, Active-vs-Bench location, and rule-box Prize
    value. Damage-counter contexts use the known remaining counter budget to prefer
    lethal targets; direct-damage contexts only override static threat for truly
    near-dead targets (<=10 HP). Reasoning: the previous CARD ranking used static
    `CardData` only, so it could not tell a full-HP Pokémon from a 10-HP Pokémon and
    missed obvious prize-finishing choices. A broader first pass regressed self-play,
    so the final rule is intentionally conservative.
  - `sample_submission/sample_submission/main.py` — unified standalone
    `SelectType.EVOLVE` ranking with MAIN-phase evolution by using `_best_card_option`
    instead of a separate HP-only implementation. Reasoning: evolution choices should
    not drift between selection contexts.
  - `scripts/build_deck.py` — changed the stale `NOTES.md` reference to
    `PROGRESS.md` and removed unused `cost_len`, `trainer_cards`, `by_name`, and
    `used_ids` code. Reasoning: these were cleanup items from review; removing them
    lowers maintenance noise without changing deck strategy.
  - Verified live: `python -m py_compile` passed for all changed Python files;
    `python self_play_benchmark.py 100` finished current 60 / previous 40 / draw 0
    with 128.7 average steps; `python benchmark.py 100` finished 98/100 wins
    (98.0%) against random; `python run_local.py` completed one match and wrote
    `result.txt`; `python scripts/build_deck.py` regenerated the 60-card deck; `rg`
    confirmed no remaining `NOTES.md`, `cost_len`, `trainer_cards`, `by_name`, or
    `used_ids` references in the cleaned files. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-07-18

- **Code-quality follow-up on the heuristic baseline**:
  - `sample_submission/sample_submission/main.py` — made `read_deck_csv()` resolve
    `deck.csv` relative to the submitted agent file first, with the Kaggle path as
    fallback and an explicit 60-card length check. Reasoning: local tools should not
    depend on whichever directory launched Python, while submission behavior stays
    compatible with Kaggle's `/kaggle_simulations/agent/` layout.
  - `sample_submission/sample_submission/main.py` — upgraded MAIN-phase ranking
    without changing the greedy baseline shape: lethal attack still comes first,
    evolution now chooses the strongest resulting card instead of option order,
    Energy attachment prefers the Active target and then stronger Bench targets,
    and Basic bench development chooses the strongest Basic available. Reasoning:
    the previous implementation was legal but over-dependent on simulator option
    ordering; the new ranking improves code quality while preserving the proven
    attack-first baseline. A first attempt also ranked all playable Trainers, but a
    20-game smoke benchmark dropped to 80%, so MAIN `PLAY` was intentionally narrowed
    back to Basic board development.
  - `sample_submission/sample_submission/main.py` — made CARD selection more
    context-aware: discard/return contexts prefer low-value cards, opponent damage
    target contexts prefer opponent options when available, and all card ranking now
    uses HP plus best printed attack damage instead of HP alone. Reasoning: one HP
    sort across every selection context was too blunt and could choose poor targets
    even though selections remained legal.
  - `scripts/build_deck.py` — replaced the unused placeholder trainer scorer with a
    deterministic score based on search/draw/evolution/Basic-Pokémon utility,
    explicit boosts for Rare Candy, Ultra Ball, and Buddy-Buddy Poffin, filters for
    dead Tera/Mega/Team-Rocket-specific search targets, and an 8-card Supporter cap.
    Reasoning: the earlier keyword filter produced a legal deck but could fill slots
    from CSV order rather than actual usefulness for this Water Stage-2 list.
  - `sample_submission/sample_submission/run_local.py` and
    `sample_submission/sample_submission/benchmark.py` — wrapped active battles in
    `try/finally` so `battle_finish()` runs even if an agent or simulator selection
    raises. Reasoning: the native simulator should be released reliably during local
    iteration and benchmarking.
  - Verified live: `python -m py_compile` for all changed Python files passed;
    `python scripts/build_deck.py` regenerated a 60-card deck; `python run_local.py`
    completed one local match and wrote `result.txt`; `python benchmark.py 100`
    finished at 99/100 wins (99.0%) against random, matching the prior baseline
    after the MAIN-phase Trainer-play regression was corrected. — <span style="background-color: rgba(91,155,213, 0.31); color:#8fd9fb">codex</span>

## 2026-07-14

- **Heuristic-vs-random benchmark harness**:
  - `sample_submission/sample_submission/benchmark.py` — plays N games between
    `main.agent` (heuristic) and a local `random_agent`, alternating which one is
    player0 each game to cancel out first-move advantage, tallies win/loss/draw.
  - Verified live: 100 games, heuristic won 99/100 (99.0% win rate) against random
    play. This is the baseline number future changes (search/lookahead, ML) get
    measured against. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Synergistic 60-card deck built from card data**:
  - `scripts/build_deck.py` — parses `dataset/EN_Card_Data.csv` (2022 rows, 1267
    unique cards after grouping the multi-row-per-move schema), finds all
    Basic→Stage1→Stage2 evolution chains of a chosen type (Water), filters out
    rule-box (`ex`) Pokémon to avoid conceding extra Prize cards, scores chains by
    `top_attack_damage*2 + HP`, and assembles a full 60-card deck: primary line
    Swinub→Piloswine→Mamoswine (200 dmg finisher), secondary line
    Clauncher→Clawitzer (210 dmg, cheap), plus lone Basics Kyogre/Glastrier (20
    Pokémon total), 14 Basic Water Energy, 26 Trainers auto-selected by
    draw/search/heal keyword match in effect text (Rare Candy, Love Ball, Boxed
    Order, Buddy-Buddy Poffin, etc.), respecting the 1-copy ACE SPEC cap.
  - Bug caught and fixed same-session: the secondary-line search initially let
    `Palafin ex` (rule-box) through because the `rule == "n/a"` filter was only
    applied to the Stage-2 candidate, not Stage-1. Added the missing check so both
    stages of every chain are enforced non-`ex`.
  - Verified all seven chosen Pokémon's attack costs are pure `{W}`/Colorless —
    no off-type energy dependency introduced by the single-type Energy count.
  - Output written to `sample_submission/sample_submission/deck.csv` (60 lines,
    replaces the original sample deck). — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Heuristic (rule-based, no ML) battle agent**:
  - `sample_submission/sample_submission/main.py` — replaced the starter's
    `random.sample(...)` agent with a greedy priority-ladder decision function.
    Caches `all_card_data()`/`all_attack()` lookups once, then dispatches on
    `obs.select.type`/`context`:
    - **MAIN** phase: attack-for-lethal → evolve → attach Energy (once/turn) →
      play Basics to Bench → use Ability → attack anyway (best damage) → retreat
      only if Active is low-HP and a stronger Benched Pokémon exists → end turn.
    - **ATTACK**: highest-damage usable attack.
    - **EVOLVE** / **CARD**: highest-HP preference (lowest-HP first when the
      context is a discard/return-to-deck selection).
    - **YES_NO**: defaults to the beneficial-sounding option.
    - **COUNT**: picks the option with the largest offered number.
    - Unhandled select types (ENERGY, SKILL, SPECIAL_CONDITION, future additions)
      fall back to a minimal safe default instead of crashing.
  - `_clamp()` — enforces `minCount <= len(selection) <= maxCount`, de-dupes, and
    drops out-of-range indices on every return path, so a heuristic mistake can
    never produce an engine-rejected selection.
  - Added `assert sel is not None` / `assert state is not None` guards in each
    helper to fix a batch of Pyright null-safety false-positives (the functions
    are only ever called after the caller already confirmed non-None, but the
    type checker can't see that across the call boundary) and dropped an unused
    `EnergyType` import.
  - Verified live via `run_local.py`: 5 consecutive games, no crashes/exceptions,
    games completing in 14–61 steps (down from the random agent's 99). — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Local test harness (bypassing `kaggle-environments`)**:
  - `sample_submission/sample_submission/run_local.py` — drives
    `cg.game.battle_start` / `battle_select` / `battle_finish` directly to run one
    full match between two agent functions and dump `result.txt` via
    `visualize_data()`. Built after `pip install kaggle-environments` failed (pulls
    in `litellm`, which needs a Rust/Cargo toolchain not present locally) —
    reading `cg/game.py` showed the battle-loop primitives are sufficient on their
    own, so the official runner isn't actually required for local iteration.
  - Verified live: ran the (then still random) starter agent vs itself, game
    completed in 99 steps, `result.txt` produced. — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

- **Rulebook and competition-rules reference docs**:
  - `POKEMON_RULES.md` — full 41-page official TCG rulebook (`par_rulebook_en.pdf`)
    condensed to markdown: win conditions, turn structure, evolution rules, full
    damage-calculation order (base → attacker boosts → Weakness → Resistance →
    defender reductions → counters), all 5 Special Conditions with stacking
    behavior, deck-building limits, a rule-box Prize-penalty table (ex/GX/V/VMAX/
    TAG TEAM/etc.), retreat rules, glossary, and a merged section on the cabt
    simulator's documented deviations from official rules (sim behavior is ground
    truth for this competition per host discussion #708586).
  - `EVALUATION.md` — full competition rules/evaluation reference covering both
    linked Kaggle competitions (Simulation `pokemon-tcg-ai-battle` and Strategy/
    Hackathon `pokemon-tcg-ai-battle-challenge-strategy`, which requires
    Simulation entry first under the same team): skill-rating (Gaussian μ/σ)
    ladder mechanics, the Strategy judging rubric (Model 70% / Deck 20% / Report
    10%), team/submission limits (max team size 5, Strategy = 1 submission
    total), IP/data restrictions (competition data + models trained on it are
    scoped to the competition only, must be deleted afterward, can't be
    commercialized), eligibility thresholds, disqualification conditions, and a
    practical-implications checklist for the build (dev-log as you go, test for
    generalization not just win rate, etc.). — <span style="background-color:rgba(255, 209, 144, 0.31); color:#ffb347">claude</span>

---

## Next up
- Log this session's design/testing notes as they compound (dev log doubles as
  future Strategy-writeup source material).
- Consider search-based lookahead (`search_begin`/`search_step`) for the
  MAIN-phase attack-timing decision, instead of pure greedy same-turn scoring.
- Re-run the 100-game benchmark after any heuristic change to track whether win
  rate actually improves.
