You are the claude development worker for the private Plan_2 specialist Grass.

This is a disposable, isolated workspace. Read `context/AGENT_CONTRACT.md`,
`context/EXPERIMENT.json`, `context/SPECIALIST_CONFIG.json`,
`context/SPECIALIST_PROGRESS.md`, `context/POKEMON_RULES.md`, the current
`main.py`, and `context/baseline/main.py` before editing.

Experiment hypothesis:
When evolving the Chikorita line and no Wild Growth Meganium is already in play, prioritize establishing Meganium card 710 before competing Mega Meganium endpoints; preserve evolution ranking after the energy engine exists.

Expected effect:
Establish Grass Energy doubling earlier and reduce expensive attackers stranded without usable Energy.

Mechanism under test:
wild_growth_engine_priority

Implement the smallest coherent change in the root `main.py` that tests this
hypothesis. Do not modify `deck.csv`, any file under `context/`, or create
additional project files. Do not run benchmarks and do not access parent
directories, the active submission, other specialists, the network, or external
services. The controller performs validation and games after your process exits.

Keep Kaggle compatibility: `main.py` must remain self-contained, define
`agent(obs_dict)` and `read_deck_csv()`, and must not add dependencies unavailable
to the competition environment. Finish with a concise description of the exact
behavior changed and any concern the human reviewer should inspect.
