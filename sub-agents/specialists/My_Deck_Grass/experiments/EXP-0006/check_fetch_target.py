"""Self-check for the EXP-0006 fetch-target policy.

Replays the two real Dawn selections captured from the live engine, where the baseline
took index 0 because every option scored 0, and pins that the new scoring picks the card
the board actually needs.

Run: python sub-agents/specialists/My_Deck_Grass/experiments/EXP-0006/check_fetch_target.py
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "sample_submission" / "sample_submission"))

spec = importlib.util.spec_from_file_location("exp0006_main", HERE / "candidate" / "main.py")
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)

from cg.api import AreaType, SelectContext  # noqa: E402

BULBASAUR, IVYSAUR, VENUSAUR = 650, 651, 652
CHIKORITA, BAYLEEF, MEGANIUM = 917, 918, 710
OGERPON, MEOWTH = 96, 1071
ENERGY = 1


class Card:
    def __init__(self, card_id):
        self.id = card_id
        self.serial = 0
        self.playerIndex = 0


class Mon:
    def __init__(self, card_id, n_energy=0):
        self.id = card_id
        self.energies = [1] * n_energy
        self.hp = 100
        self.maxHp = 100


class Player:
    def __init__(self, active, bench, hand):
        self.active = [active] if active else []
        self.bench = list(bench)
        self.benchMax = 5
        self.hand = [Card(c) for c in hand]
        self.discard = []


class State:
    def __init__(self, player):
        self.yourIndex = 0
        self.players = [player, player]
        self.looking = None


class Opt:
    def __init__(self, index, area=AreaType.DECK):
        self.type = 3
        self.area = area
        self.index = index
        self.playerIndex = 0
        self.cardId = None


class Sel:
    def __init__(self, options, deck, context=SelectContext.TO_HAND):
        self.type = 1
        self.context = context
        self.option = options
        self.deck = [Card(c) for c in deck]
        self.minCount = 0
        self.maxCount = 1


class Obs:
    def __init__(self, select, current):
        self.select = select
        self.current = current


def pick(deck_ids, board, hand):
    """Return the card id the policy chooses from a deck-search offering."""
    player = Player(board[0] if board else None, board[1:], hand)
    sel = Sel([Opt(i) for i in range(len(deck_ids))], deck_ids)
    obs = Obs(sel, State(player))
    ranked = main._choose_card(obs)
    return deck_ids[sel.option[ranked[0]].index]


# Real sample 1: Dawn's Basic offering. Baseline took Meowth ex (index 0). Bulbasaur
# starts the Mega Venusaur ex line, which is the deck's win condition.
chosen = pick([MEOWTH, CHIKORITA, OGERPON, BULBASAUR], [Mon(CHIKORITA)], [])
assert chosen != MEOWTH, "still fetching the support ex over a line starter"
assert chosen in (BULBASAUR, OGERPON), chosen

# Real sample 2: Dawn's Stage 1 offering with a Bulbasaur already in play. Baseline took
# Bayleef; Ivysaur is the one that can actually be played onto the board.
chosen = pick([BAYLEEF, IVYSAUR, IVYSAUR], [Mon(BULBASAUR)], [])
assert chosen == IVYSAUR, chosen

# Mirror case: with Chikorita in play instead, Bayleef becomes the live evolution.
chosen = pick([BAYLEEF, IVYSAUR, IVYSAUR], [Mon(CHIKORITA)], [])
assert chosen == BAYLEEF, chosen

# A duplicate already in hand is near-worthless next to a live evolution.
chosen = pick([VENUSAUR, IVYSAUR], [Mon(BULBASAUR)], [VENUSAUR])
assert chosen == IVYSAUR, chosen

# Energy outranks a dead evolution while nothing on board can attack yet...
chosen = pick([VENUSAUR, ENERGY], [Mon(CHIKORITA)], [])
assert chosen == ENERGY, chosen
# ...but a live evolution still beats Energy.
chosen = pick([VENUSAUR, ENERGY], [Mon(IVYSAUR)], [])
assert chosen == VENUSAUR, chosen

# Unresolvable option must score 0 rather than raise.
assert main._fetch_target_score(None, Obs(None, None)) == 0

print("EXP-0006 fetch-target checks passed")
