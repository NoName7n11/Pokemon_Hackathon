You are the codex development worker for the private Plan_2 specialist PalSystem_Dragapult.

This is a disposable, isolated workspace. Read `context/AGENT_CONTRACT.md`,
`context/EXPERIMENT.json`, `context/SPECIALIST_CONFIG.json`,
`context/SPECIALIST_PROGRESS.md`, `context/POKEMON_RULES.md`, any available
`context/STRATEGY.md`, the current
`main.py`, and `context/baseline/main.py` before editing.

Experiment hypothesis:
During MAIN-phase evolution ordering, when a Drakloak can use Recon Directive and can also evolve into Dragapult ex, use that Drakloak's draw Ability before evolving it; preserve the existing evolve and Ability ordering for every other Pokemon and when Recon Directive is unavailable or already used.

Expected effect:
Gain the Drakloak draw opportunity that the generic evolve-before-Ability policy currently discards, without changing unrelated evolution lines or globally raising Ability priority.

Mechanism under test:
drakloak_recon_before_evolution

Implement the smallest coherent change in the root `main.py` that tests this
hypothesis. Do not modify `deck.csv`, any file under `context/`, or create
additional project files. Do not run benchmarks and do not access parent
directories, the active submission, other specialists, the network, or external
services. The controller performs validation and games after your process exits.

Keep Kaggle compatibility: `main.py` must remain self-contained, define
`agent(obs_dict)` and `read_deck_csv()`, and must not add dependencies unavailable
to the competition environment. Finish with a concise description of the exact
behavior changed and any concern the human reviewer should inspect.
