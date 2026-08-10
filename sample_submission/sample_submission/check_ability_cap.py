"""Regression check for the 2026-08-11 Ability infinite-loop bug.

Mega Venusaur ex's Solar Transfer ("as often as you like, move a Basic {G}
Energy between your own Pokemon") is legal forever and used to make the old
MAIN ladder loop ENERGY -> CARD -> ABILITY without ever reaching ATTACK/END.
Plays N games with a deck containing that card and asserts none hit the step
cap. See main.py's _take_ability and PROGRESS.md 2026-08-11.

Run from this directory:
    python3 check_ability_cap.py [n_games]    (default 30)
"""
import sys

import main
from cg.api import to_observation_class
from cg.game import battle_finish, battle_select, battle_start

DECK_PATH = "../../Claude_Decks/Claude_Grass_Venusaur.csv"
STEP_CAP = 3000  # matches the diagnostic that found the bug


def load(path):
    with open(path, encoding="utf-8") as f:
        return [int(x) for x in f if x.strip()][:60]


def play(deck, max_steps=STEP_CAP):
    obs, _ = battle_start(deck, deck)
    if obs is None:
        return 0
    steps = 0
    try:
        for _ in range(max_steps):
            o = to_observation_class(obs)
            if o.current is not None and o.current.result != -1:
                return steps
            pi = o.current.yourIndex if o.current else 0
            obs = battle_select(main.agent(obs))
            steps += 1
        return steps
    finally:
        battle_finish()


def main_cli():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    deck = load(DECK_PATH)
    hung = 0
    for i in range(n):
        steps = play(deck)
        if steps >= STEP_CAP:
            hung += 1
        print(f"  game {i}: {steps} steps" + ("  <<< HUNG" if steps >= STEP_CAP else ""))
    print(f"\n{hung}/{n} games hit the step cap")
    assert hung == 0, f"{hung}/{n} games did not terminate -- ability-loop bug is back"
    print("PASS")


if __name__ == "__main__":
    main_cli()
