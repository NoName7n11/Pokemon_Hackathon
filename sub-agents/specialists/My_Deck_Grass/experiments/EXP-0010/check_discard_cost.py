"""Self-check for the EXP-0010 discard-cost policy.

Replays the two hands captured from the live engine where Ultra Ball's cost was paid with
hand slots 0 and 1, and pins that the engine card and the prize-closer survive.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "sample_submission" / "sample_submission"))

spec = importlib.util.spec_from_file_location("exp0010_main", HERE / "candidate" / "main.py")
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)

from cg.api import AreaType, SelectContext  # noqa: E402

MEGANIUM, ENERGY, ENERGY_SWITCH, NIGHT_STRETCHER = 710, 1, 1116, 1097
LANAS_AID, BOSSS_ORDERS, BAYLEEF, BULBASAUR, IVYSAUR, VENUSAUR = 1184, 1182, 918, 650, 651, 652


class Card:
    def __init__(self, cid): self.id = cid


class Mon:
    def __init__(self, cid, n=0):
        self.id = cid; self.energies = [1] * n; self.hp = 100; self.maxHp = 100


class Player:
    def __init__(self, hand, active=None, bench=()):
        self.hand = [Card(c) for c in hand]
        self.active = [active] if active else []
        self.bench = list(bench)
        self.benchMax = 5


class State:
    def __init__(self, p): self.yourIndex = 0; self.players = [p, p]; self.looking = None


class Opt:
    def __init__(self, i):
        self.area = AreaType.HAND; self.index = i; self.playerIndex = 0; self.cardId = None; self.type = 3


class Sel:
    def __init__(self, n, k):
        self.type = 1; self.context = SelectContext.DISCARD
        self.option = [Opt(i) for i in range(n)]; self.minCount = k; self.maxCount = k
        self.deck = None


class Obs:
    def __init__(self, sel, cur): self.select = sel; self.current = cur


def discarded(hand, k=2, active=None, bench=()):
    obs = Obs(Sel(len(hand), k), State(Player(hand, active, bench)))
    return sorted(hand[i] for i in main._choose_card(obs))


# Real hand 1: it discarded Meganium + Energy, keeping two spare Night Stretchers.
got = discarded([MEGANIUM, ENERGY, ENERGY_SWITCH, NIGHT_STRETCHER, NIGHT_STRETCHER], active=Mon(BULBASAUR))
assert MEGANIUM not in got, f"still pitching the Wild Growth engine: {got}"
assert NIGHT_STRETCHER in got, f"duplicate Night Stretcher should pay the cost: {got}"

# Real hand 2: it discarded Lana's Aid + Boss's Orders, keeping Bayleef.
got = discarded([LANAS_AID, BOSSS_ORDERS, BAYLEEF], active=Mon(BULBASAUR))
assert BOSSS_ORDERS not in got, f"still pitching the prize-closer: {got}"

# A dead evolution (no pre-evolution anywhere) is cheaper than a live one.
dead = main._keep_value(VENUSAUR, Obs(None, State(Player([], Mon(BULBASAUR)))))
live = main._keep_value(IVYSAUR, Obs(None, State(Player([], Mon(BULBASAUR)))))
assert dead < live, (dead, live)

# Meganium already on board is no longer irreplaceable.
in_hand = main._keep_value(MEGANIUM, Obs(None, State(Player([], Mon(BULBASAUR)))))
on_board = main._keep_value(MEGANIUM, Obs(None, State(Player([], Mon(MEGANIUM)))))
assert on_board < in_hand, (on_board, in_hand)

# Unresolvable card must score 0, not raise.
assert main._keep_value(None, Obs(None, None)) == 0

print("EXP-0010 discard-cost checks passed")
