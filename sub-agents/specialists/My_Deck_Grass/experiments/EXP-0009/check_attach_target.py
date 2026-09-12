"""Self-check for the EXP-0009 attachment-target policy.

Pins that the once-per-turn manual attachment goes where it advances an attack, not to
whatever is Active -- and specifically that it stops feeding the support ex.

Run: python sub-agents/specialists/My_Deck_Grass/experiments/EXP-0009/check_attach_target.py
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "sample_submission" / "sample_submission"))

spec = importlib.util.spec_from_file_location("exp0009_main", HERE / "candidate" / "main.py")
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)

from cg.api import AreaType  # noqa: E402

GRASS = 1
VENUSAUR, OGERPON, MEOWTH, FEZANDIPITI, BULBASAUR = 652, 96, 1071, 140, 650


class Mon:
    def __init__(self, card_id, n=0, hp=100):
        self.id = card_id
        self.energies = [GRASS] * n
        self.hp = hp
        self.maxHp = hp


class Opt:
    def __init__(self, area, index=None):
        self.inPlayArea = area
        self.inPlayIndex = index


class Me:
    def __init__(self, active, bench):
        self.active = [active] if active else []
        self.bench = list(bench)


# The measured waste: Meowth ex Active, a Mega Venusaur ex on the Bench sitting on 3 of
# its 4 Energy. The old rule attached to the Active every time.
me = Me(Mon(MEOWTH), [Mon(VENUSAUR, 3, 380)])
options = [Opt(AreaType.ACTIVE), Opt(AreaType.BENCH, 0)]
assert main._best_attach_index(options, [0, 1], me) == 1, "still feeding the support ex"

# Same shape with Fezandipiti ex Active and an Ogerpon one Energy short of Myriad Leaf Shower.
me = Me(Mon(FEZANDIPITI), [Mon(OGERPON, 2, 210)])
assert main._best_attach_index([Opt(AreaType.ACTIVE), Opt(AreaType.BENCH, 0)], [0, 1], me) == 1

# Unlocking an attack beats topping up one that is already online.
online = main._attach_target_score(Mon(OGERPON, 3, 210), is_active=True)     # can already attack
unlocks = main._attach_target_score(Mon(VENUSAUR, 3, 380), is_active=False)  # 4th Energy unlocks 240
assert unlocks > online, (unlocks, online)

# Unlocking a small attack must NOT outrank charging a big one: Bulbasaur's Bind Down
# is 10 damage, Jungle Dump is 240.
small = main._attach_target_score(Mon(BULBASAUR, 0, 80), is_active=False)
assert small < unlocks, (small, unlocks)

# A Pokemon that cannot attack even WITH the Energy ranks last, whatever its HP:
# Mega Venusaur ex on 0 Energy still cannot pay Jungle Dump's cost of 4 with 1.
dead = main._attach_target_score(Mon(VENUSAUR, 0, 380), is_active=False)
assert dead < online and dead < unlocks and dead < small, (dead, online, unlocks, small)

# All else equal the Active still wins -- Energy there is usable this turn.
act = main._attach_target_score(Mon(OGERPON, 1, 210), is_active=True)
ben = main._attach_target_score(Mon(OGERPON, 1, 210), is_active=False)
assert act > ben, (act, ben)

# A missing target must never be chosen and must not raise.
assert main._attach_target_score(None, is_active=True) < 0

print("EXP-0009 attach-target checks passed")
