You are the codex development worker for the private Plan_2 specialist PalSystem_Dragapult.

This is a disposable, isolated workspace. Read `context/AGENT_CONTRACT.md`,
`context/EXPERIMENT.json`, `context/SPECIALIST_CONFIG.json`,
`context/SPECIALIST_PROGRESS.md`, `context/POKEMON_RULES.md`, any available
`context/STRATEGY.md`, the current
`main.py`, and `context/baseline/main.py` before editing.

Experiment hypothesis:
Replay-curated PalSystem games show Dreepy is the dominant successful opener and first setup body. For opening Active and initial setup Bench CARD selections only, prefer Dreepy first, then Munkidori/Budew as fallback support, while keeping Fezandipiti ex and Meowth ex off Active unless no better Basic is available; preserve all MAIN-phase play, Energy, Trainer, Ability, attack, evolution, and damage-target logic unchanged.

Expected effect:
Increase stable Dragapult-line setup without bundling speculative Energy or Trainer changes; decision traces must prove the changed decisions are opening/setup CARD selections and not unrelated cascade differences.

Mechanism under test:
dreepy_first_opening_setup_only

Implement the smallest coherent change in the root `main.py` that tests this
hypothesis. Do not modify `deck.csv`, any file under `context/`, or create
additional project files. Do not run benchmarks and do not access parent
directories, the active submission, other specialists, the network, or external
services. The controller performs validation and games after your process exits.

Keep Kaggle compatibility: `main.py` must remain self-contained, define
`agent(obs_dict)` and `read_deck_csv()`, and must not add dependencies unavailable
to the competition environment. Finish with a concise description of the exact
behavior changed and any concern the human reviewer should inspect.
