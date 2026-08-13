You are the codex development worker for the private Plan_2 specialist Fire.

This is a disposable, isolated workspace. Read `context/AGENT_CONTRACT.md`,
`context/EXPERIMENT.json`, `context/SPECIALIST_CONFIG.json`,
`context/SPECIALIST_PROGRESS.md`, `context/POKEMON_RULES.md`, the current
`main.py`, and `context/baseline/main.py` before editing.

Experiment hypothesis:
When choosing or evaluating attacks for Mega Charizard X ex and Mega Charizard Y ex, estimate their effect-driven damage and required Energy discard instead of treating zero printed damage as zero value; preserve all non-Charizard attack logic.

Expected effect:
Use powered Charizard attacks at tactically correct times instead of underrating dynamic damage.

Mechanism under test:
charizard_effect_damage_evaluation

Implement the smallest coherent change in the root `main.py` that tests this
hypothesis. Do not modify `deck.csv`, any file under `context/`, or create
additional project files. Do not run benchmarks and do not access parent
directories, the active submission, other specialists, the network, or external
services. The controller performs validation and games after your process exits.

Keep Kaggle compatibility: `main.py` must remain self-contained, define
`agent(obs_dict)` and `read_deck_csv()`, and must not add dependencies unavailable
to the competition environment. Finish with a concise description of the exact
behavior changed and any concern the human reviewer should inspect.
