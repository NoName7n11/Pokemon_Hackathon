"""Self-check for EXP-0014. The first assertion is the exact case that sank EXP-0013."""
import importlib.util, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4] / "sample_submission" / "sample_submission"))
spec = importlib.util.spec_from_file_location("e14", HERE / "candidate" / "main.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

GRASS = 1
VEN, MEG, CHIK, MEOW, FEZ, OGER = 652, 710, 917, 1071, 140, 96


class Mon:
    def __init__(s, cid, n=0, hp=200): s.id=cid; s.energies=[GRASS]*n; s.hp=hp; s.maxHp=hp
class P:
    def __init__(s, a, b): s.active=[a] if a else []; s.bench=list(b)
class S:
    def __init__(s, me, opp): s.yourIndex=0; s.players=[me, opp]


def total(mon, bench, opp):
    st = S(P(None, bench), opp); oa = opp.active[0] if opp.active else None
    return m._live_attacker_score(mon, oa) + m._promotion_adjust(mon, st, oa)


# THE EXP-0013 REGRESSION: a charged Ogerpon is the only attacker on a bench of chaff.
# It must be promoted, not buried under a 70 HP Chikorita.
opp = P(Mon(VEN, 4, 380), [])
bench = [Mon(OGER, 3, 210), Mon(CHIK, 0, 70)]
assert total(bench[0], bench, opp) > total(bench[1], bench, opp), \
    "regression: positional penalty outranked the only viable attacker"

# With a real alternative present, Ogerpon does stay Benched for Tera immunity.
bench = [Mon(OGER, 1, 210), Mon(VEN, 4, 380)]
assert total(bench[1], bench, opp) > total(bench[0], bench, opp)

# Operator's scenario: nothing charged -> Meowth ex is the Tuck Tail escape valve.
bench = [Mon(VEN,0,380), Mon(MEG,0,160), Mon(CHIK,0,70), Mon(MEOW,0,170), Mon(FEZ,0,210)]
weak_opp = P(Mon(CHIK, 0, 70), [])          # cannot KO anything: not a sacrifice spot
best = max(bench, key=lambda b: total(b, bench, weak_opp))
assert best.id == MEOW, f"expected Meowth ex escape, got {best.id}"

# ...but never over a charged attacker.
bench2 = [Mon(VEN, 4, 380), Mon(MEOW, 0, 170)]
assert total(bench2[0], bench2, weak_opp) > total(bench2[1], bench2, weak_opp)

# Sacrifice spot: everything dies. Prefer a non-Rule-Box duplicate over the sole Meganium.
opp_big = P(Mon(VEN, 4, 380), [])
bench3 = [Mon(CHIK,0,70), Mon(CHIK,0,70), Mon(MEG,0,160)]
best = max(bench3, key=lambda b: total(b, bench3, opp_big))
assert best.id == CHIK, f"chump should be the duplicate Chikorita, got {best.id}"

assert m._promotion_adjust(None, None, None) == 0
print("EXP-0014 promotion checks passed")
