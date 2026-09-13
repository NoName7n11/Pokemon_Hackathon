# Pokémon TCG Agent — PTCG AI Battle Challenge Strategy

Heuristic agent for the Pokémon TCG simulation competition: a priority ladder with a
1-ply lookahead, built and measured through a nine-mechanism negative-results program
(one accepted, eight rejected).

- **Interactive companion page** (figures + all 15 experiments, sortable/filterable): https://noname7n11.github.io/Pokemon_Hackathon/
- **Full writeup**: [writeup/WRITEUP.md](writeup/WRITEUP.md)
- **Agent source, full**: [sample_submission/sample_submission/main.py](sample_submission/sample_submission/main.py)

## What's here

- `sample_submission/` — the submitted agent (`main.py`) and deck list
- `sub-agents/` — the experiment harness and per-deck specialist logs (EXP-0001 … EXP-0015)
- `writeup/` — the strategy writeup, figures, and this project's showcase page source
- `decks/`, `deck_builder/` — deck construction tooling and candidate deck lists
- `research/` — the parallel ISMCTS/learned-policy-value track and supporting notebooks
- `docs/` — misc project docs

## Competition Data

This repo excludes all Pokémon-provided Competition Data (card database, card image
sets, deck-recipe files, card ID reference PDFs, the rulebook PDF, and episode replay
dumps), per the competition rules (Data Security / public-sharing restrictions on
Competition Data and Pokémon Elements). Only original code, logs, and the writeup are
public.
