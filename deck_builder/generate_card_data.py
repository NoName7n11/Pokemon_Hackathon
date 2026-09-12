import csv
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CARD_DATA = ROOT / "data" / "dataset" / "EN_Card_Data.csv"
IMAGE_ROOT = Path(r"C:\Users\novan\Desktop\Pokemon_Dataset")
OUTPUT = Path(__file__).with_name("card-data.js")
PREVIEW_ROOT = Path(__file__).with_name("assets") / "cards"
PREVIEW_SIZE = (320, 448)


def clean(value):
    value = (value or "").strip()
    return "" if value == "n/a" else value


def to_int(value):
    value = clean(value)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def card_kind(stage_text):
    text = stage_text.lower()
    if any(value in text for value in ("tool", "item", "supporter", "stadium")):
        return "Trainer"
    if "pokémon" in text or "pokemon" in text:
        return "Pokemon"
    if "energy" in text:
        return "Energy"
    return "Trainer"


def source_image_for(card):
    expansion = card["expansion"]
    number = card["collectionNumber"]
    name = card["name"]
    if not expansion or not number:
        return None

    folder = IMAGE_ROOT / expansion
    candidate = folder / f"{int(number):03d} - {name}.jpg"
    if candidate.exists():
        return candidate

    if folder.exists():
        matches = list(folder.glob(f"{int(number):03d} - *.jpg"))
        if matches:
            return matches[0]
    return None


def preview_for(card):
    source = source_image_for(card)
    if source is None:
        return ""

    PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    destination = PREVIEW_ROOT / f"{card['id']}.webp"
    if not destination.exists() or destination.stat().st_mtime < source.stat().st_mtime:
        with Image.open(source) as image:
            image = image.convert("RGB")
            image.thumbnail(PREVIEW_SIZE, Image.Resampling.LANCZOS)
            image.save(destination, "WEBP", quality=82, method=6)
    return f"assets/cards/{card['id']}.webp"


def main():
    grouped = {}
    with CARD_DATA.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            card_id = int(row["Card ID"])
            card = grouped.setdefault(
                card_id,
                {
                    "id": card_id,
                    "name": clean(row["Card Name"]),
                    "expansion": clean(row["Expansion"]),
                    "collectionNumber": clean(row["Collection No."]),
                    "stage": clean(row["Stage (Pokémon)/Type (Energy and Trainer)"]),
                    "rule": clean(row["Rule"]),
                    "category": clean(row["Category"]),
                    "previousStage": clean(row["Previous stage"]),
                    "hp": to_int(row["HP"]),
                    "type": clean(row["Type"]),
                    "weakness": clean(row["Weakness"]),
                    "resistance": clean(row["Resistance (Type)"]),
                    "retreat": clean(row["Retreat"]),
                    "attacks": [],
                    "effectText": "",
                },
            )
            move_name = clean(row["Move Name"])
            effect = clean(row["Effect Explanation"])
            damage = clean(row["Damage"])
            cost = clean(row["Cost"])
            if move_name or effect:
                card["attacks"].append(
                    {"name": move_name, "cost": cost, "damage": damage, "effect": effect}
                )

    cards = []
    for card in grouped.values():
        card["kind"] = card_kind(card["stage"])
        card["isBasicEnergy"] = card["kind"] == "Energy" and "Basic" in card["stage"]
        card["isMega"] = "mega" in (card["name"] + " " + card["rule"]).lower()
        card["hasAbility"] = any(
            "ability" in attack["name"].lower() or "ability" in attack["effect"].lower()
            for attack in card["attacks"]
        )
        card["effectText"] = " ".join(
            part
            for attack in card["attacks"]
            for part in (attack["name"], attack["effect"])
            if part
        )
        card["image"] = preview_for(card)
        cards.append(card)

    cards.sort(key=lambda card: (card["expansion"], int(card["collectionNumber"] or 0), card["id"]))
    payload = {
        "cards": cards,
        "expansions": sorted({card["expansion"] for card in cards if card["expansion"]}),
        "types": sorted({card["type"] for card in cards if card["type"]}),
        "generatedFrom": str(CARD_DATA),
        "imageRoot": str(IMAGE_ROOT),
    }
    OUTPUT.write_text(
        "window.CARD_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"Generated {len(cards)} cards and {sum(bool(card['image']) for card in cards)} local previews.")


if __name__ == "__main__":
    main()
