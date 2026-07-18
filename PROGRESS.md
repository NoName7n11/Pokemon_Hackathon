# Pokémon Hackathon — Progress Log

Local change log for this repo. Every implementation gets recorded here, newest first,
signed with the implementer's name at the end of the entry.

**APPEND-ONLY.** Never edit or delete an existing entry — only add new ones. This log is
a permanent record; past entries stay exactly as written, even if later reverted (note
the reversal as a new entry instead).

---

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
