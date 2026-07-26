"""Rewrite every Decs/*.txt so each card line gains its dataset Card ID:

    <count> <Card Name> - <Card ID>

Section headers, blanks, and the banner/total lines are left untouched. Card
lines are matched to dataset/EN_Card_Data.csv by normalized name (reusing the
matching logic from check_decks.py). Run from repo root:

    python scripts/annotate_decks.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_decks import load_pool, norm  # noqa: E402

DECS_DIR = "Decs"
# A card line: leading count, then the name (optionally trailing "SET Collector").
CARD_LINE = re.compile(r"^(\d+)\s+(.*?)\s*$")
SET_SUFFIX = re.compile(r"\s+([A-Z0-9]{2,4})\s+(\d+)\s*$")
SECTION = re.compile(r"^(Pok[eé]mon|Trainer|Energy|Total)", re.IGNORECASE)


def resolve_id(name: str, set_code, coll, pool) -> str | None:
    matches = pool.get(norm(name))
    if not matches:
        return None
    if set_code and coll:
        for cid, exp, cno in matches:
            if exp.upper() == set_code.upper() and cno == coll:
                return cid
    return matches[0][0]


def annotate_file(path: Path, pool) -> tuple[int, int]:
    out_lines = []
    done = missing = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        m = CARD_LINE.match(stripped)
        if not m or SECTION.match(stripped):
            out_lines.append(line.rstrip())
            continue
        count, rest = m.group(1), m.group(2)
        set_code = coll = None
        name = rest
        sm = SET_SUFFIX.search(rest)
        if sm:
            set_code, coll = sm.group(1), sm.group(2)
            name = rest[: sm.start()].strip()
        cid = resolve_id(name, set_code, coll, pool)
        if cid is None:
            out_lines.append(f"{count} {name}")
            missing += 1
        else:
            out_lines.append(f"{count} {name} - {cid}")
            done += 1
    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return done, missing


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    pool = load_pool()
    for path in sorted(Path(DECS_DIR).glob("*.txt")):
        done, missing = annotate_file(path, pool)
        flag = "" if missing == 0 else f"  ({missing} UNMATCHED)"
        print(f"{path.name}: annotated {done} card lines{flag}")


if __name__ == "__main__":
    main()
