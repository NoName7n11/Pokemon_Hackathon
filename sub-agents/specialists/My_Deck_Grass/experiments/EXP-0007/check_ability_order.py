"""Self-check for the EXP-0007 ability ordering.

Pins the ordering that matters under ABILITY_CAP_PER_TURN: resource-ADDING once-per-turn
abilities before the unlimited Energy router, and engine order preserved on ties.

Run: python sub-agents/specialists/My_Deck_Grass/experiments/EXP-0007/check_ability_order.py
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "sample_submission" / "sample_submission"))

spec = importlib.util.spec_from_file_location("exp0007_main", HERE / "candidate" / "main.py")
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)

from cg.api import AreaType  # noqa: E402

VENUSAUR, OGERPON, FEZANDIPITI, MEOWTH = 652, 96, 140, 1071


class Mon:
    def __init__(self, card_id):
        self.id = card_id


class Opt:
    def __init__(self, area, index):
        self.area = area
        self.index = index
        self.cardId = None


class Me:
    def __init__(self, active, bench):
        self.active = [active] if active else []
        self.bench = list(bench)
        self.hand = []


# The measured menu: Mega Venusaur ex (Solar Transfer) listed FIRST, Ogerpon (Teal Dance)
# second. The old rule took index 0 every time; Teal Dance must now win.
me = Me(Mon(VENUSAUR), [Mon(OGERPON)])
options = [Opt(AreaType.ACTIVE, 0), Opt(AreaType.BENCH, 0)]
assert main._best_ability_index(options, [0, 1], me) == 1, "Solar Transfer still beating Teal Dance"

# Flip the Script outranks everything -- drawing 3 first informs every later decision.
me = Me(Mon(VENUSAUR), [Mon(OGERPON), Mon(FEZANDIPITI)])
options = [Opt(AreaType.ACTIVE, 0), Opt(AreaType.BENCH, 0), Opt(AreaType.BENCH, 1)]
assert main._best_ability_index(options, [0, 1, 2], me) == 2

# Last-Ditch Catch sits between Flip the Script and Teal Dance.
me = Me(Mon(VENUSAUR), [Mon(OGERPON), Mon(MEOWTH)])
options = [Opt(AreaType.ACTIVE, 0), Opt(AreaType.BENCH, 0), Opt(AreaType.BENCH, 1)]
assert main._best_ability_index(options, [0, 1, 2], me) == 2

# Two copies of the same ability: engine order is preserved, no churn.
me = Me(Mon(OGERPON), [Mon(OGERPON)])
options = [Opt(AreaType.ACTIVE, 0), Opt(AreaType.BENCH, 0)]
assert main._best_ability_index(options, [0, 1], me) == 0

# Solar Transfer alone is still used -- this reorders, it never suppresses.
me = Me(Mon(VENUSAUR), [])
assert main._best_ability_index([Opt(AreaType.ACTIVE, 0)], [0], me) == 0

# An unresolvable option scores 0 and must not raise.
assert main._ability_option_score(Opt(AreaType.DECK, 3), Me(None, [])) == 0
assert main._ability_option_score(Opt(AreaType.BENCH, 9), Me(None, [])) == 0

print("EXP-0007 ability-order checks passed")
