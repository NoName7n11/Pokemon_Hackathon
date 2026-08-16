"""Self-check for the EXP-0005 Energy-source policy.

Pins the one property that matters: the engine's own energy movement must never be
routed to disarm an Active that can currently attack, and idle Bench Energy must be
preferred as the donor.

Run: python sub-agents/specialists/My_Deck_Grass/experiments/EXP-0005/check_energy_source.py
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "sample_submission" / "sample_submission"))

spec = importlib.util.spec_from_file_location("exp0005_main", HERE / "candidate" / "main.py")
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)

from cg.api import AreaType  # noqa: E402  (needs the engine path set above)

GRASS = 1
OGERPON = 96          # Myriad Leaf Shower, cost {G}{G}{G}
VENUSAUR = 652        # Jungle Dump, cost {G}{G}{G}{G}
MEOWTH = 1071         # Tuck Tail, 3 Colorless


class Mon:
    def __init__(self, card_id, n_energy):
        self.id = card_id
        self.energies = [GRASS] * n_energy


class Opt:
    def __init__(self, area, index, energy_index=0, count=1):
        self.area = area
        self.index = index
        self.energyIndex = energy_index
        self.count = count


class Me:
    def __init__(self, active, bench):
        self.active = [active]
        self.bench = list(bench)


# Active Ogerpon is charged and can attack; Bench Venusaur is half-charged and cannot.
me = Me(Mon(OGERPON, 3), [Mon(VENUSAUR, 2), Mon(MEOWTH, 0)])

active_src = main._energy_source_score(Opt(AreaType.ACTIVE, 0), me)
bench_src = main._energy_source_score(Opt(AreaType.BENCH, 0), me)
empty_src = main._energy_source_score(Opt(AreaType.BENCH, 1), me)

# The ready Active must be the worst donor of the three.
assert active_src < bench_src, (active_src, bench_src)
assert active_src < empty_src, (active_src, empty_src)
# An empty Bench Pokemon offers nothing to take, so it must not outrank a real donor.
assert bench_src > empty_src, (bench_src, empty_src)

# A Bench Pokemon that cannot attack even with its Energy is a better donor than one
# that would be disarmed by the move.
me2 = Me(Mon(MEOWTH, 0), [Mon(VENUSAUR, 4), Mon(VENUSAUR, 1)])
ready_bench = main._energy_source_score(Opt(AreaType.BENCH, 0), me2)
idle_bench = main._energy_source_score(Opt(AreaType.BENCH, 1), me2)
assert idle_bench > ready_bench, (idle_bench, ready_bench)

# Wild Growth: opt.count is in Energy UNITS, so a doubled Basic {G} removes 2 units and
# can disarm an attacker a naive 1-unit model would think is safe. Jungle Dump costs 4,
# so 5 units is the case that separates them: -1 still attacks, -2 does not.
me3 = Me(Mon(MEOWTH, 0), [Mon(VENUSAUR, 5)])
one_unit = main._energy_source_score(Opt(AreaType.BENCH, 0, count=1), me3)
two_units = main._energy_source_score(Opt(AreaType.BENCH, 0, count=2), me3)
assert two_units < one_unit, (two_units, one_unit)

# Unresolvable option (area we don't model) must be inert, not a crash.
assert main._energy_source_score(Opt(AreaType.DISCARD, 0), me) == 0

print("EXP-0005 energy-source checks passed")
