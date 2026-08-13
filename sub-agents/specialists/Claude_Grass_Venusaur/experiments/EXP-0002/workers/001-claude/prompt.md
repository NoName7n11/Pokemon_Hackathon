You are the claude development worker for the private Plan_2 specialist Claude_Grass_Venusaur.

This is a disposable, isolated workspace. Read `context/AGENT_CONTRACT.md`,
`context/EXPERIMENT.json`, `context/SPECIALIST_CONFIG.json`,
`context/SPECIALIST_PROGRESS.md`, `context/POKEMON_RULES.md`, the current
`main.py`, and `context/baseline/main.py` before editing.

Experiment hypothesis:
For forced promotion and own-board CARD choices after a knockout, prefer an attack-ready Mega Venusaur ex, Hydrapple ex, or Teal Mask Ogerpon ex over support Pokemon when it can immediately deal more usable damage; preserve generic live-attacker scoring outside that narrow choice.

Expected effect:
Increase attacks made by the deck's primary attackers and reduce turns lost after a knockout without changing global evaluation or ability handling.

Mechanism under test:
venusaur_attacker_concentration

Implement the smallest coherent change in the root `main.py` that tests this
hypothesis. Do not modify `deck.csv`, any file under `context/`, or create
additional project files. Do not run benchmarks and do not access parent
directories, the active submission, other specialists, the network, or external
services. The controller performs validation and games after your process exits.

Keep Kaggle compatibility: `main.py` must remain self-contained, define
`agent(obs_dict)` and `read_deck_csv()`, and must not add dependencies unavailable
to the competition environment. Finish with a concise description of the exact
behavior changed and any concern the human reviewer should inspect.
