"""Build a synergistic 60-card deck from EN_Card_Data.csv.

Strategy (documented in PROGRESS.md):
  - Pick one Energy type with a deep card pool.
  - Find the best 3-stage (Basic->Stage1->Stage2) evolution line of that type
    that is NOT a rule-box Pokemon (Rule == 'n/a'), to avoid giving up extra
    Prize cards on KO -- favors a stable, low-risk baseline deck.
  - Add a second, cheaper 2-stage line of the same type for early-game plays.
  - Fill remaining Pokemon slots with the strongest single Basics of that type.
  - Add ~15 Basic Energy of that type.
  - Fill Trainer slots with cards whose effect text mentions draw/search/heal
    (consistency engine), skipping ACE SPEC cards beyond 1 total.

Run from repo root:
    python scripts/build_deck.py
Writes: sample_submission/sample_submission/deck.csv
"""
import csv
import re
import sys
from collections import defaultdict

CSV_PATH = "data/dataset/EN_Card_Data.csv"
DECK_OUT = "sample_submission/sample_submission/deck.csv"
STAGE_COL = "Stage (Pokémon)/Type (Energy and Trainer)"

CHOSEN_TYPE = "{W}"  # Water -- deep pool, decent draw/search support.
MAX_COPIES = 4


def load_rows():
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def group_cards(rows):
    """Group multi-row (per-move) entries into one record per Card ID."""
    by_id = defaultdict(list)
    for r in rows:
        by_id[r["Card ID"]].append(r)
    cards = {}
    for cid, rs in by_id.items():
        base = rs[0]
        moves = [
            {"name": r["Move Name"], "cost": r["Cost"], "damage": r["Damage"]}
            for r in rs
            if r["Move Name"] and r["Move Name"] != "n/a"
        ]
        best_dmg = 0
        for m in moves:
            try:
                best_dmg = max(best_dmg, int(re.sub(r"[^0-9]", "", m["damage"]) or 0))
            except ValueError:
                pass
        cards[cid] = {
            "id": cid,
            "name": base["Card Name"],
            "stage": base[STAGE_COL],
            "rule": base["Rule"],
            "type": base["Type"],
            "hp": int(base["HP"]) if base["HP"].isdigit() else 0,
            "retreat": base["Retreat"],
            "prev": base["Previous stage"],
            "moves": moves,
            "best_dmg": best_dmg,
        }
    return cards


def find_chains(cards, ptype):
    """Return list of (basic, stage1, stage2_or_None) same-type chains."""
    basics = [c for c in cards.values() if c["stage"] == "Basic Pokémon" and c["type"] == ptype and c["rule"] == "n/a"]
    chains = []
    for b in basics:
        s1_candidates = [
            c for c in cards.values()
            if c["stage"] == "Stage 1 Pokémon" and c["prev"] == b["name"] and c["type"] == ptype
        ]
        if not s1_candidates:
            chains.append((b, None, None))
            continue
        for s1 in s1_candidates:
            if s1["rule"] != "n/a":
                continue
            s2_candidates = [
                c for c in cards.values()
                if c["stage"] == "Stage 2 Pokémon" and c["prev"] == s1["name"] and c["type"] == ptype
                and c["rule"] == "n/a"
            ]
            if s2_candidates:
                for s2 in s2_candidates:
                    chains.append((b, s1, s2))
            else:
                chains.append((b, s1, None))
    return chains


def score_chain(chain):
    b, s1, s2 = chain
    top = s2 or s1 or b
    return top["best_dmg"] * 2 + top["hp"]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = load_rows()
    cards = group_cards(rows)

    chains3 = [c for c in find_chains(cards, CHOSEN_TYPE) if c[2] is not None]
    chains2 = [c for c in find_chains(cards, CHOSEN_TYPE) if c[2] is None and c[1] is not None]
    chains3.sort(key=score_chain, reverse=True)
    chains2.sort(key=score_chain, reverse=True)

    primary = chains3[0]
    # Secondary line: different Basic than primary's.
    secondary = next(c for c in chains2 if c[0]["name"] != primary[0]["name"])

    print("Primary line:", [c["name"] for c in primary if c])
    for c in primary:
        if c:
            print(f"  {c['name']:<20} stage={c['stage']:<16} hp={c['hp']:<4} best_dmg={c['best_dmg']}")
    print("Secondary line:", [c["name"] for c in secondary if c])
    for c in secondary:
        if c:
            print(f"  {c['name']:<20} stage={c['stage']:<16} hp={c['hp']:<4} best_dmg={c['best_dmg']}")

    pokemon_slots = []  # list of (card_id, copies)
    pokemon_slots.append((primary[0]["id"], 4))
    pokemon_slots.append((primary[1]["id"], 3))
    pokemon_slots.append((primary[2]["id"], 2))
    pokemon_slots.append((secondary[0]["id"], 3))
    pokemon_slots.append((secondary[1]["id"], 3))

    used_names = {primary[0]["name"], primary[1]["name"], primary[2]["name"], secondary[0]["name"], secondary[1]["name"]}

    # Fill remaining Pokemon slots (target ~20 total) with strongest lone Basics of the type.
    lone_basics = [
        c for c in cards.values()
        if c["stage"] == "Basic Pokémon" and c["type"] == CHOSEN_TYPE and c["rule"] == "n/a"
        and c["name"] not in used_names
    ]
    lone_basics.sort(key=lambda c: c["best_dmg"] * 2 + c["hp"], reverse=True)

    pokemon_total = sum(n for _, n in pokemon_slots)
    target_pokemon = 20
    for c in lone_basics:
        if pokemon_total >= target_pokemon:
            break
        copies = min(3, target_pokemon - pokemon_total)
        pokemon_slots.append((c["id"], copies))
        pokemon_total += copies

    print(f"\nPokemon total: {pokemon_total}")
    for cid, n in pokemon_slots:
        print(f"  x{n}  {cards[cid]['name']} (id={cid})")

    # Energy: chosen type Basic Energy card ID.
    energy_card = next(c for c in cards.values() if c["stage"] == "Basic Energy" and c["type"] == CHOSEN_TYPE)
    energy_count = 14
    print(f"\nEnergy: x{energy_count} {energy_card['name']} (id={energy_card['id']})")

    # Trainers: prefer draw/search/heal effect text, skip ACE SPEC beyond 1.
    trainer_rows = [
        r for r in rows
        if r[STAGE_COL] in ("Item", "Supporter", "Stadium")
    ]
    keywords = re.compile(
        r"draw|search your deck|heal|shuffle.*hand|Basic Pok[ée]mon|Stage 2|evol",
        re.IGNORECASE,
    )

    trainer_candidates = []
    for r in trainer_rows:
        effect = r["Effect Explanation"] or ""
        if not keywords.search(effect):
            continue
        if "Tera Pokémon" in effect:
            continue
        if "Mega Evolution Pokémon" in effect:
            continue
        if "Team Rocket" in effect:
            continue
        if "same name as 1 of your opponent" in effect:
            continue
        trainer_candidates.append(r)

    # De-dupe by Card ID, keep first occurrence.
    seen = {}
    for r in trainer_candidates:
        seen.setdefault(r["Card ID"], r)
    trainer_list = list(seen.values())

    def trainer_score(r):
        effect = (r["Effect Explanation"] or "").lower()
        score = 0
        name = r["Card Name"].lower()
        if "rare candy" in name:
            score += 90
        if "ultra ball" in name:
            score += 75
        if "buddy-buddy poffin" in name:
            score += 65
        if "search your deck" in effect:
            score += 50
        if "draw" in effect:
            score += 40
        if "stage 2" in effect or "evol" in effect:
            score += 35
        if "basic pokémon" in effect or "basic pokemon" in effect:
            score += 35
        if "heal" in effect:
            score += 20
        if "discard 2 other cards" in effect:
            score -= 10
        if "your turn ends" in effect:
            score -= 25
        if r["Rule"] == "ACE SPEC":
            score += 15
        if r[STAGE_COL] == "Supporter":
            score -= 10
        return score

    trainer_list.sort(key=lambda r: (trainer_score(r), r["Card Name"], r["Card ID"]), reverse=True)

    trainer_total_target = 60 - pokemon_total - energy_count
    trainer_slots = []
    ace_spec_used = False
    supporter_count = 0
    supporter_cap = 8
    t_count = 0
    for r in trainer_list:
        if t_count >= trainer_total_target:
            break
        cid = r["Card ID"]
        is_ace = r["Rule"] == "ACE SPEC"
        if is_ace:
            if ace_spec_used:
                continue
            copies = 1
            ace_spec_used = True
        else:
            copies = min(MAX_COPIES, trainer_total_target - t_count)
        if r[STAGE_COL] == "Supporter":
            copies = min(copies, 2, supporter_cap - supporter_count)
            if copies <= 0:
                continue
            supporter_count += copies
        trainer_slots.append((cid, copies, r["Card Name"], r[STAGE_COL]))
        t_count += copies

    print(f"\nTrainers: {t_count} (target {trainer_total_target})")
    for cid, n, name, kind in trainer_slots:
        print(f"  x{n}  {name} (id={cid}, {kind})")

    # Assemble final 60-card deck list.
    deck = []
    for cid, n in pokemon_slots:
        deck += [cid] * n
    deck += [energy_card["id"]] * energy_count
    for cid, n, _, _ in trainer_slots:
        deck += [cid] * n

    # Pad/trim to exactly 60 with extra Basic Energy if short.
    if len(deck) < 60:
        deck += [energy_card["id"]] * (60 - len(deck))
    deck = deck[:60]

    print(f"\nFinal deck size: {len(deck)}")
    assert len(deck) == 60

    with open(DECK_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(str(c) for c in deck) + "\n")
    print(f"Wrote {DECK_OUT}")


if __name__ == "__main__":
    main()
