"""Self-check for the EXP-0003 live variable-damage estimator.

Pins the two formulas measured against the engine (see the comment block above
ATK_MYRIAD_LEAF_SHOWER in candidate/main.py) so a later edit that reverts to the
printed Attack.damage fails loudly instead of silently.

Run: python sub-agents/specialists/My_Deck_Grass/experiments/EXP-0003/check_live_damage.py
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "sample_submission" / "sample_submission"))

spec = importlib.util.spec_from_file_location("exp0003_main", HERE / "candidate" / "main.py")
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)


class FakeAttack:
    def __init__(self, attack_id, damage, energies=()):
        self.attackId = attack_id
        self.damage = damage
        self.energies = list(energies)


class FakeMon:
    def __init__(self, energies):
        self.energies = list(energies)


GRASS = 1
myriad = FakeAttack(main.ATK_MYRIAD_LEAF_SHOWER, 30, [GRASS] * 3)
cruel = FakeAttack(main.ATK_CRUEL_ARROW, 0, [0, 0, 0])
jungle_dump = FakeAttack(941, 240, [GRASS] * 4)

# The three engine-measured Myriad Leaf Shower samples, mine/theirs in PROVIDED energy.
assert main._live_attack_damage(myriad, FakeMon([GRASS] * 3), FakeMon([GRASS])) == 150
assert main._live_attack_damage(myriad, FakeMon([GRASS] * 3), FakeMon([GRASS] * 2)) == 180
assert main._live_attack_damage(myriad, FakeMon([GRASS] * 3), FakeMon([])) == 120
# The discriminating sample: opponent had 2 provided from 1 card via their own
# Wild Growth. Counting attached cards would give 150; the engine dealt 180.
assert main._live_attack_damage(myriad, FakeMon([GRASS] * 3), FakeMon([GRASS] * 2)) == 180
# No opponent Active (e.g. ranking a Bench promotion) must not crash.
assert main._live_attack_damage(myriad, FakeMon([GRASS] * 3), None) == 120

# Cruel Arrow's printed damage is 0; it deals a flat 100.
assert main._live_attack_damage(cruel, FakeMon([]), FakeMon([GRASS])) == 100

# Every other attack keeps its printed value, and None is 0 damage.
assert main._live_attack_damage(jungle_dump, FakeMon([GRASS] * 4), FakeMon([GRASS])) == 240
assert main._live_attack_damage(None, FakeMon([]), None) == 0

# _best_attack_index must now rank a charged Myriad Leaf Shower above Jungle Dump's
# printed 240 when the board actually supports it -- that inversion is the point.


class FakeOption:
    def __init__(self, attack_id):
        self.attackId = attack_id


main._ATTACK_DATA = {myriad.attackId: myriad, jungle_dump.attackId: jungle_dump}
idx, dmg = main._best_attack_index(
    [FakeOption(jungle_dump.attackId), FakeOption(myriad.attackId)],
    [0, 1],
    FakeMon([GRASS] * 6),
    FakeMon([GRASS] * 3),
)
assert (idx, dmg) == (1, 300), (idx, dmg)

print("EXP-0003 live-damage checks passed")
