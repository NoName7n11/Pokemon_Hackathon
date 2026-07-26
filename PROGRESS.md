# Pokémon Hackathon — Progress Log

Local change log for this repo. Every implementation gets recorded here, newest first,
signed with the implementer's name at the end of the entry.

**APPEND-ONLY.** Never edit or delete an existing entry — only add new ones. This log is
a permanent record; past entries stay exactly as written, even if later reverted (note
the reversal as a new entry instead).

---

## 2026-07-20

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
