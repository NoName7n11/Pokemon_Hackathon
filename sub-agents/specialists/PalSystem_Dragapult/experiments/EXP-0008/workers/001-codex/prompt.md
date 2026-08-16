You are the codex development worker for the private Plan_2 specialist PalSystem_Dragapult.

This is a disposable, isolated workspace. Read `context/AGENT_CONTRACT.md`,
`context/EXPERIMENT.json`, `context/SPECIALIST_CONFIG.json`,
`context/SPECIALIST_PROGRESS.md`, `context/POKEMON_RULES.md`, any available
`context/STRATEGY.md`, the current
`main.py`, and `context/baseline/main.py` before editing.

Experiment hypothesis:
Use the corrected replay-pattern report from palsystem_games/analysis/replay_patterns.md. Implement only PalSystem opening setup CARD selection: when obs.select.type is CARD/select type 1 and context is numeric 1, choose Active by replay priority Dreepy first, then Munkidori, then Budew, then Meowth ex, then Fezandipiti ex. When context is numeric 2, choose setup Bench by replay priority Dreepy first, then Munkidori, then Meowth ex, then Fezandipiti ex, then Budew. Do not change MAIN-phase PLAY, ATTACH, Trainer, Ability, Attack, Evolve, or damage-target logic.

Expected effect:
Correct the previous failed setup attempt by using the raw replay numeric CARD contexts 1 and 2; decision traces must show differences in CARD context 1 or 2, not MAIN cascade differences, before any deep evaluation.

Mechanism under test:
numeric_setup_context_replay_priority

Implement the smallest coherent change in the root `main.py` that tests this
hypothesis. Do not modify `deck.csv`, any file under `context/`, or create
additional project files. Do not run benchmarks and do not access parent
directories, the active submission, other specialists, the network, or external
services. The controller performs validation and games after your process exits.

Keep Kaggle compatibility: `main.py` must remain self-contained, define
`agent(obs_dict)` and `read_deck_csv()`, and must not add dependencies unavailable
to the competition environment. Finish with a concise description of the exact
behavior changed and any concern the human reviewer should inspect.
