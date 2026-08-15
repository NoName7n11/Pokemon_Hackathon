You are the codex development worker for the private Plan_2 specialist PalSystem_Dragapult.

This is a disposable, isolated workspace. Read `context/AGENT_CONTRACT.md`,
`context/EXPERIMENT.json`, `context/SPECIALIST_CONFIG.json`,
`context/SPECIALIST_PROGRESS.md`, `context/POKEMON_RULES.md`, any available
`context/STRATEGY.md`, the current
`main.py`, and `context/baseline/main.py` before editing.

Experiment hypothesis:
For Munkidori Adrena-Brain selections only, move damage counters from the most strategically endangered friendly Pokemon to an opposing Pokemon where the moved damage secures a knockout or creates the strongest live-HP prize setup; do not alter generic Ability choice or unrelated damage-counter selection.

Expected effect:
Turn existing self-damage into prize pressure while improving survival of prepared Dragapult attackers.

Mechanism under test:
munkidori_adrena_brain_damage_transfer

Implement the smallest coherent change in the root `main.py` that tests this
hypothesis. Do not modify `deck.csv`, any file under `context/`, or create
additional project files. Do not run benchmarks and do not access parent
directories, the active submission, other specialists, the network, or external
services. The controller performs validation and games after your process exits.

Keep Kaggle compatibility: `main.py` must remain self-contained, define
`agent(obs_dict)` and `read_deck_csv()`, and must not add dependencies unavailable
to the competition environment. Finish with a concise description of the exact
behavior changed and any concern the human reviewer should inspect.
