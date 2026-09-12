"""Self-check for the EXP-0013 promotion policy — the operator's scenario, encoded."""
import importlib.util, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4] / "sample_submission" / "sample_submission"))
spec = importlib.util.spec_from_file_location("exp0013", HERE / "candidate" / "main.py")
main = importlib.util.module_from_spec(spec); spec.loader.exec_module(main)

GRASS = 1
VENUSAUR, MEGANIUM, CHIKORITA, MEOWTH, FEZ, OGERPON = 652, 710, 917, 1071, 140, 96


class Mon:
    def __init__(self, cid, n=0, hp=None):
        self.id = cid; self.energies = [GRASS] * n
        self.hp = hp if hp is not None else 200; self.maxHp = self.hp


class P:
    def __init__(self, active, bench):
        self.active = [active] if active else []
        self.bench = list(bench)


class S:
    def __init__(self, me, opp): self.yourIndex = 0; self.players = [me, opp]


def adj(mon, me, opp):
    return main._promotion_adjust(mon, S(me, opp), opp.active[0] if opp.active else None)


# The operator's scenario: Active just knocked out. Bench = Mega Venusaur ex, Meganium,
# Chikorita, Meowth ex, Fezandipiti ex -- and NOTHING is charged enough to attack.
bench = [Mon(VENUSAUR, 0, 380), Mon(MEGANIUM, 0, 160), Mon(CHIKORITA, 0, 70),
         Mon(MEOWTH, 0, 170), Mon(FEZ, 0, 210)]
me = P(None, bench); opp = P(Mon(OGERPON, 2, 210), [])
scores = {m.id: adj(m, me, opp) for m in bench}
assert scores[MEOWTH] == max(scores.values()), scores
assert scores[MEOWTH] > 0, "Meowth ex must be the escape valve when the bench is dead"

# Same board but Mega Venusaur ex is charged: 240 damage beats a 60-damage Tuck Tail.
bench2 = [Mon(VENUSAUR, 4, 380), Mon(MEOWTH, 0, 170)]
me2 = P(None, bench2)
assert adj(bench2[1], me2, opp) < 0, "Meowth ex must not be promoted over a live attacker"

# Ogerpon ex stays Benched for Tera immunity when it cannot take the knockout...
assert adj(Mon(OGERPON, 1, 210), P(None, [Mon(OGERPON, 1, 210)]), opp) < 0
# ...but a lethal Ogerpon is promoted regardless.
lethal_opp = P(Mon(CHIKORITA, 0, 20), [])
assert adj(Mon(OGERPON, 3, 210), P(None, [Mon(OGERPON, 3, 210)]), lethal_opp) > 0

# Fezandipiti ex: promoted only with a <=100 HP target AND when it survives the reply.
weak_target = P(Mon(VENUSAUR, 0, 380), [Mon(CHIKORITA, 0, 60)])
assert adj(Mon(FEZ, 0, 210), P(None, [Mon(FEZ, 0, 210)]), weak_target) > 0
no_target = P(Mon(VENUSAUR, 0, 380), [Mon(MEGANIUM, 0, 160)])
assert adj(Mon(FEZ, 0, 210), P(None, [Mon(FEZ, 0, 210)]), no_target) < 0
# A lethal opposing Active means Fezandipiti ex would just hand over 2 prizes.
deadly = P(Mon(VENUSAUR, 4, 380), [Mon(CHIKORITA, 0, 60)])
assert adj(Mon(FEZ, 0, 210), P(None, [Mon(FEZ, 0, 210)]), deadly) < 0

assert main._promotion_adjust(None, None, None) == 0
print("EXP-0013 promotion checks passed")
