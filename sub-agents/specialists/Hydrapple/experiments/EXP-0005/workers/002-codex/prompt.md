You are the codex development worker for the private Plan_2 specialist Hydrapple.

This is a disposable, isolated workspace. Read `context/AGENT_CONTRACT.md`,
`context/EXPERIMENT.json`, `context/SPECIALIST_CONFIG.json`,
`context/SPECIALIST_PROGRESS.md`, `context/POKEMON_RULES.md`, the current
`main.py`, and `context/baseline/main.py` before editing.

Experiment hypothesis:
Verify the Codex nested Windows command runner with automatic approval review before retrying a strategic worker edit

Expected effect:
Codex should read the isolated context and make one harmless main.py comment edit

Mechanism under test:
codex_windows_spawn_probe

Implement the smallest coherent change in the root `main.py` that tests this
hypothesis. Do not modify `deck.csv`, any file under `context/`, or create
additional project files. Do not run benchmarks and do not access parent
directories, the active submission, other specialists, the network, or external
services. The controller performs validation and games after your process exits.

Keep Kaggle compatibility: `main.py` must remain self-contained, define
`agent(obs_dict)` and `read_deck_csv()`, and must not add dependencies unavailable
to the competition environment. Finish with a concise description of the exact
behavior changed and any concern the human reviewer should inspect.
