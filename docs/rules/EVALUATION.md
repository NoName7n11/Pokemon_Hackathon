# Evaluation & Competition Rules Reference

> Covers both linked competitions: **Simulation** (`pokemon-tcg-ai-battle`) and **Strategy/Hackathon**
> (`pokemon-tcg-ai-battle-challenge-strategy`). Participation in Simulation is **required** to enter
> Strategy. Same team must compete in both.

---

## 1. Two Competitions, One Entry

| | Simulation | Strategy (Hackathon) |
|---|---|---|
| Submission | `main.py` + `deck.csv` (.tar.gz) | Kaggle Writeup (≤2000 words) |
| Submissions allowed | Up to 5/day, latest 2 active | **1 total** |
| Scored by | Skill rating (win rate ladder) | Judges, rubric-based |
| Prize money | None directly | **$240,000** total |
| Entry deadline | Aug 9, 2026 | Sept 6, 2026 |
| Final submission | Aug 16, 2026 | Sept 13, 2026 |
| Result window | ~Aug 17–31, 2026 (convergence) | Judging: Sept 14–Oct 11, 2026 |

**Team requirement:** must be the **same team** registered in the Simulation division to be prize-eligible
in Strategy. Cross-division membership must match exactly.

---

## 2. Simulation — Skill Rating System (how leaderboard rank works)

- Each submission modeled as Gaussian **N(μ, σ²)** — μ = estimated skill, σ = uncertainty (shrinks with
  more games).
- New submission starts at **μ₀ = 600**, enters the pool after a self-play **validation episode** passes.
- Engine matches submissions of **similar current rating** (not random pairing).
- After each Episode: win → your μ up, opponent's μ down (reverse for loss; draw = both move toward mean).
  **Magnitude scales with surprise** (upsets move μ more) and with σ (newer/uncertain submissions swing
  faster).
- **Only win/loss/draw matters — margin of victory does not.**
- Up to **5 submissions/day**, but only the **latest 2** stay active in matchmaking; older ones stop
  playing. Leaderboard shows your **best-scoring submission** only.
- **Final Evaluation**: submissions lock Aug 16, 2026; engine keeps running games ~2 more weeks to let
  ratings converge before the leaderboard is declared final.

**What actually raises rank:**
1. Win rate vs. similarly-rated opponents (beating weak bots barely moves you once ahead of them).
2. Consistency — σ shrinks with games played, so steady winners converge to a *trusted* high μ; lucky
   streaks against weak matchmaking don't hold.
3. Generalization — as your rating climbs you face tougher/more varied opponents; a one-trick deck/agent
   plateaus.
4. Submitting early — more games played = faster convergence before the deadline lock.

---

## 3. Strategy — Judging Rubric

| Category | Weight | Judged on |
|---|---|---|
| **Model Score** | 70% | Clarity/soundness of approach explanation; originality/technical soundness; consistency across repeated matches; avoids over-reliance on specific initial states/matchups/situational advantages; leaderboard performance (one factor among several, not the whole score) |
| **Deck Score** | 20% | Clarity of deck concept + alignment with strategy; effective key-card selection/utilization |
| **Report Score** | 10% | Logical structure/writing clarity; effective use of figures/charts/tables |

**Explicit callout from the comp:** *"High leaderboard ranking may provide an advantage in performance
scoring, but it does not guarantee a strong result in the Strategy Category. Participants in middle or
lower tiers of the competition can still achieve high overall scores through deep analysis, originality,
and well-structured reporting."*

### Submission requirements
- **Kaggle Writeup**: title, subtitle, detailed analysis. **≤2000 words** (overage may be penalized).
  Must select a Track (only "Main Track" confirmed; page didn't reveal sub-tracks beyond the
  Simulation/Strategy division split).
- **Media Gallery** (optional): images/video, must respect the Pokémon-asset license — violating images =
  disqualification.
- Optional attachments: code repos, Kaggle notebooks, external links.
- Draft/unsubmitted Writeups by deadline are **not** considered.
- If a private Kaggle Resource is attached to a public Writeup, it **auto-becomes public** after the
  deadline.

### Prizes
- **Main Track · $240,000** — 8 Finalists × $30,000 each.
- Finalists may be invited to an in-person tournament hosted by The Pokémon Company in Tokyo (TBD).
- Judges: shige, choya (Matsuo Institute data scientists) + 3 Pokémon Company reps.

---

## 4. Team & Submission Rules

- **Max team size: 5.**
- Team mergers allowed (team leader only); combined submission count must stay ≤ the per-team daily cap
  × days-competition-has-run, as of the merger deadline.
- **One Kaggle account per person** — multi-accounting = disqualification.
- **No private sharing outside your team.** Sharing code/strategy must be public (competition forums) to
  be permitted; private cross-team sharing (without merging) risks disqualification.
- Hackathon (Strategy): **1 submission per team, total** — no daily resubmission like Simulation.

---

## 5. IP & Data Rules (read before training anything)

### "Pokémon Elements" — broadly defined, stays Pokémon's property always
Covers: character data (names/types/stats/moves), world/lore elements, game/card/simulator logic (damage
formulas, UI, card/deck data, type matchups), brand/trade-dress, **and**:

> **"All derivative works, derivatives, and outputs newly created by using, inputting, extracting,
> analyzing, reproducing, adapting, or modifying any of the foregoing Pokémon Elements... including all
> illustrations, images, text, audio, video, and 3D models generated, synthesized, or output through the
> use of artificial intelligence or machine learning tools."**

### What you keep vs. what's restricted
- Participants **do** retain rights to the ML models/algorithms/code/weights/embeddings they build.
- **But**: *"Participants may not use any models trained on Pokémon Elements, or the Pokémon Elements
  themselves, for any purpose outside of participating in the Competition."*
- **And**: *"Participants may not use the Pokémon Elements or models derived from them for commercial
  purposes or to create products that compete with the Sponsor."*
- Using a trained model to regenerate/extract Pokémon Elements outside the competition = IP infringement.
- **Must delete Competition Data** (card CSVs/PDFs, engine binaries, replay files) after the competition
  ends — license to use it is "solely for use during the period of the Competition."

### Winner-specific obligations (only if you place)
- Winning submission's **source code must be open-sourced** under an OSI-approved license that never
  restricts commercial use — except any Kaggle/Pokémon-provided data/model, which stays excluded from the
  open-source release.
- Must provide a **reproducible methodology write-up** (architecture, preprocessing, loss function,
  training details, hyperparameters) per Kaggle's Winning Model Documentation Guidelines + a working code
  repo link.
- Winning submissions containing Pokémon Elements can't be relicensed/used commercially in any way that
  "competes with or diminishes the value of" Pokémon's products, without prior permission.
- Must return signed prize-acceptance docs (eligibility cert, license/release, tax forms — W-9 US / W-8BEN
  foreign) within **2 weeks** of notification, or forfeit. Paid ~30 days after docs received.

### External data / tools — what's allowed
- **External data allowed** if publicly available + equally accessible to all participants at no cost, OR
  passes a "Reasonableness Standard" (e.g., a paid LLM API tier is fine; an exclusive dataset priced above
  the prize pool is not).
- **Pretrained models & LLMs are allowed** unless the Host specifically prohibits them.
- **AutoML tools explicitly permitted** (Google AutoML, H2O Driverless AI, etc.) — submissions built with
  them remain prize-eligible.
- Open-source libraries used in the model must be OSI-licensed with no commercial-use restriction (only
  enforced if you win).

---

## 6. Eligibility (verbatim thresholds)

To enter, you must be:
- A registered Kaggle.com account holder.
- At least 18, or age of majority in your jurisdiction (or have Host-approved guardian consent).
- **Not** a resident of Crimea, so-called Donetsk People's Republic (DNR), Luhansk People's Republic
  (LNR), Cuba, Iran, or North Korea.
- Not a person/entity under U.S. export controls or sanctions.
- If representing an employer/entity: must have their consent (including to receive a prize), must not
  use employer confidential info, participation must not count as the employer's "job-related invention,"
  and must not violate any non-compete.
- False info (identity, residency, rights ownership) = immediate disqualification.
- **Competition-entity employees/contractors may participate but cannot win prizes** (subject to their
  employer's own policy).

---

## 7. Disqualification Conditions

- Cheating, deception, unfair play, or "undermining legitimate operation" of the competition.
- Threatening/harassing other participants or competition entities.
- Illegible, incomplete, damaged, altered, counterfeit, fraudulently obtained, or late submissions.
- Hand-labeling or human prediction of validation/test data.
- Multi-accounting.
- Private (non-forum) code/strategy sharing outside your team.
- Non-compliant winning submissions get either disqualified or a **1-week remediation window** (fix
  license conflicts, remove violating software) at Host's discretion.

---

## 8. Governing Law

- General claims: California law; Federal/State courts of Santa Clara County, CA.
- Claims involving Pokémon specifically: Japanese law, arbitrated via the Japan Commercial Arbitration
  Association in Tokyo (unless participant's country isn't a NY Convention signatory, in which case
  defendant's domicile court has jurisdiction).

---

## 9. Practical Implications for Our Build

1. **Delete/don't redistribute** `dataset/`, `ptcg_engine/`, `sample_submission/` after the competition —
   license is competition-use-only.
2. **Any trained model is scoped to this competition** — can't reuse, publish, or commercialize it
   afterward if it was trained on card data/game logic (Pokémon Elements).
3. **Keep a dev log from day one** — Model Score (70%) explicitly rewards *explained reasoning*, not just
   win rate; retrofit-writing this in September is harder than logging decisions as we make them.
4. **Test for generalization, not just win rate** — judges explicitly penalize "over-reliance on specific
   initial states, matchups, or situational advantages." Multi-deck / multi-seed testing matters for the
   Strategy score, not just Simulation ranking.
5. **One shot on the Strategy submission** — unlike Simulation's daily resubmits, get the Writeup right
   before submitting once.
6. Pretrained models / external ML libraries / LLM APIs are fair game — no need to build everything from
   scratch.
