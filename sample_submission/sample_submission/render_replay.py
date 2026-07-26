"""Render a watchable HTML replay of one cabt battle (the official Kaggle visualizer).

Requires kaggle-environments (install once, without its heavy optional deps):
    pip install --no-deps kaggle-environments

Run from this directory:
    python render_replay.py                       # heuristic mirror, our deck
    python render_replay.py --p1 random           # heuristic vs random
    python render_replay.py --deck1 ../../decks/marnie.csv   # custom P1 deck
    python render_replay.py --open                # also open it in the browser

Writes replay.html; open it in any browser and use the player controls to step
through the match visually.
"""
import argparse
import random
import webbrowser
from pathlib import Path

from kaggle_environments import make
from main import agent as heuristic_agent, read_deck_csv


def random_agent(obs_dict):
    from cg.api import to_observation_class
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return read_deck_csv()
    return random.sample(range(len(obs.select.option)), obs.select.maxCount)


def load_deck(path: str | None) -> list[int]:
    if path is None:
        return read_deck_csv()
    lines = [ln.strip() for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [int(x) for x in lines[:60]]


AGENTS = {"heuristic": heuristic_agent, "random": random_agent}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p0", choices=AGENTS, default="heuristic")
    ap.add_argument("--p1", choices=AGENTS, default="heuristic")
    ap.add_argument("--deck0", default=None, help="path to P0 deck.csv (default: ./deck.csv)")
    ap.add_argument("--deck1", default=None, help="path to P1 deck.csv (default: ./deck.csv)")
    ap.add_argument("--out", default="replay.html")
    ap.add_argument("--open", action="store_true", help="open the replay in a browser")
    args = ap.parse_args()

    deck0 = load_deck(args.deck0)
    deck1 = load_deck(args.deck1)
    env = make("cabt", configuration={"decks": [deck0, deck1]}, debug=True)
    out = env.run([AGENTS[args.p0], AGENTS[args.p1]])
    r0, r1 = out[-1][0].reward, out[-1][1].reward
    winner = "P0" if r0 > r1 else "P1" if r1 > r0 else "draw"
    print(f"{args.p0}(P0) vs {args.p1}(P1): {len(out)} steps, winner={winner} (reward {r0}/{r1})")

    html = env.render(mode="html")
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"Wrote {args.out} ({len(html)//1024} KB) -- open it in a browser to watch.")
    if args.open:
        webbrowser.open(Path(args.out).resolve().as_uri())


if __name__ == "__main__":
    main()
