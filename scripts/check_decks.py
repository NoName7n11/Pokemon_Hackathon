"""Cross-reference the deck lists in Decs/ against dataset/EN_Card_Data.csv.

For each deck, report which cards are found (by name) in the competition card
pool and which are missing, and whether a legal 60-card cabt deck (list of
Card IDs) can be assembled.

Run from repo root:
    python scripts/check_decks.py
"""
import csv
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

CSV_PATH = "dataset/EN_Card_Data.csv"
DECS_DIR = "Decs"


ENERGY_ALIAS = {
    "grass energy": "basic {g} energy",
    "fire energy": "basic {r} energy",
    "water energy": "basic {w} energy",
    "lightning energy": "basic {l} energy",
    "psychic energy": "basic {p} energy",
    "fighting energy": "basic {f} energy",
    "darkness energy": "basic {d} energy",
    "metal energy": "basic {m} energy",
}


def norm(s: str) -> str:
    """Normalize a card name for matching: unify apostrophes, drop them, strip
    accents, collapse whitespace, lowercase. Curly apostrophes must be unified
    BEFORE the ASCII strip (which would otherwise delete them and desync from
    straight-quote spellings)."""
    s = s.replace("’", "'").replace("`", "'").replace("'", "")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return ENERGY_ALIAS.get(s, s)


def load_pool():
    """name -> list of (cardId, expansion, collectionNo)."""
    by_name = defaultdict(list)
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            by_name[norm(r["Card Name"])].append(
                (r["Card ID"], r["Expansion"], r["Collection No."])
            )
    return by_name


DECK_LINE = re.compile(r"^\s*(\d+)\s+(.*?)\s*$")


def parse_deck(path: Path):
    """Return list of (count, raw_name, set_code, collector_no)."""
    entries = []
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        low = line.lower()
        if low.startswith(("pokémon", "pokemon", "trainer", "energy", "total")):
            section = low
            continue
        m = DECK_LINE.match(line)
        if not m:
            continue
        count = int(m.group(1))
        rest = m.group(2)
        # Trailing "SET 123" set-code + collector number, if present.
        setm = re.search(r"\s+([A-Z0-9]{2,4})\s+(\d+)\s*$", rest)
        set_code = coll = None
        name = rest
        if setm:
            set_code, coll = setm.group(1), setm.group(2)
            name = rest[: setm.start()].strip()
        entries.append((count, name, set_code, coll))
    return entries


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    pool = load_pool()

    grand_missing = defaultdict(set)
    for path in sorted(Path(DECS_DIR).glob("*.txt")):
        entries = parse_deck(path)
        total = sum(c for c, *_ in entries)
        found_ids = 0
        missing = []
        print(f"\n===== {path.name}  ({total} cards) =====")
        for count, name, set_code, coll in entries:
            key = norm(name)
            matches = pool.get(key)
            if matches:
                # Prefer exact set+collector match if the deck specified it.
                pick = None
                if set_code and coll:
                    for cid, exp, cno in matches:
                        if exp.upper() == set_code.upper() and cno == coll:
                            pick = (cid, exp, cno)
                            break
                pick = pick or matches[0]
                found_ids += count
                exact = " (exact set)" if (set_code and pick[1].upper() == set_code.upper() and pick[2] == coll) else ""
                print(f"  OK   x{count:<2} {name:<32} -> id {pick[0]} [{pick[1]} {pick[2]}]{exact}")
            else:
                missing.append((count, name))
                grand_missing[path.name].add(name)
                print(f"  MISS x{count:<2} {name}")
        legal = found_ids == 60 and not missing
        print(f"  --- matched {found_ids}/{total} card-copies; missing {len(missing)} distinct names; "
              f"buildable={'YES' if legal else 'NO'}")

    print("\n===== SUMMARY =====")
    for deck, names in grand_missing.items():
        print(f"{deck}: {len(names)} missing -> {', '.join(sorted(names))}")
    if not grand_missing:
        print("All decks fully matched.")


if __name__ == "__main__":
    main()
