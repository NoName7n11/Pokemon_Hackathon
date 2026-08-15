You are the codex development worker for the private Plan_2 specialist PalSystem_Dragapult.

This is a disposable, isolated workspace. Read `context/AGENT_CONTRACT.md`,
`context/EXPERIMENT.json`, `context/SPECIALIST_CONFIG.json`,
`context/SPECIALIST_PROGRESS.md`, `context/POKEMON_RULES.md`, any available
`context/STRATEGY.md`, the current
`main.py`, and `context/baseline/main.py` before editing.

Experiment hypothesis:
For Crispin and normal Energy attachment choices in this deck only, prioritize a legal Fire-plus-Psychic route that makes the Active or best prepared Dragapult ex able to use Phantom Dive, while reserving Darkness Energy for Munkidori only when Adrena-Brain has live damage-movement value; preserve generic attachment ranking when no deck-specific route improves attack readiness.

Expected effect:
Reach Phantom Dive sooner and reduce off-plan Energy attachments without stranding Munkidori's useful Darkness requirement.

Mechanism under test:
crispin_dragapult_energy_routing

Implement the smallest coherent change in the root `main.py` that tests this
hypothesis. Do not modify `deck.csv`, any file under `context/`, or create
additional project files. Do not run benchmarks and do not access parent
directories, the active submission, other specialists, the network, or external
services. The controller performs validation and games after your process exits.

Keep Kaggle compatibility: `main.py` must remain self-contained, define
`agent(obs_dict)` and `read_deck_csv()`, and must not add dependencies unavailable
to the competition environment. Finish with a concise description of the exact
behavior changed and any concern the human reviewer should inspect.
