You are the claude development worker for the private Plan_2 specialist Dark.

This is a disposable, isolated workspace. Read `context/AGENT_CONTRACT.md`,
`context/EXPERIMENT.json`, `context/SPECIALIST_CONFIG.json`,
`context/SPECIALIST_PROGRESS.md`, `context/POKEMON_RULES.md`, the current
`main.py`, and `context/baseline/main.py` before editing.

Experiment hypothesis:
For attack choice and immediate attacker scoring, account for Mega Sharpedo ex Hungry Jaws receiving its conditional damage only when Sharpedo is damaged; preserve generic attack ranking for all other Pokemon.

Expected effect:
Promote and attack with damaged Mega Sharpedo when Hungry Jaws is a real high-damage option without globally inflating its value.

Mechanism under test:
sharpedo_conditional_attack_value

Implement the smallest coherent change in the root `main.py` that tests this
hypothesis. Do not modify `deck.csv`, any file under `context/`, or create
additional project files. Do not run benchmarks and do not access parent
directories, the active submission, other specialists, the network, or external
services. The controller performs validation and games after your process exits.

Keep Kaggle compatibility: `main.py` must remain self-contained, define
`agent(obs_dict)` and `read_deck_csv()`, and must not add dependencies unavailable
to the competition environment. Finish with a concise description of the exact
behavior changed and any concern the human reviewer should inspect.
