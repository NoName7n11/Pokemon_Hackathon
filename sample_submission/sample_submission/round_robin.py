"""Full round-robin of all Decs/*.csv decks, heuristic agent on both seats.

Plays every ordered pair (deckA as P0 vs deckB as P1) for N games, then reports:
  - a raw P0-win% matrix (rows = P0 deck, cols = P1 opponent)
  - a seat-averaged win% matrix that cancels the engine's first/second-seat bias:
      winrate(A vs B) = mean( P0win(A over B), 1 - P0win(B over A) )
  - a ranking by average seat-neutral win rate across opponents.

Run from this directory:
    python3 round_robin.py [n_games]     (default 50)
Writes round_robin_results.md.
"""
import sys
from pathlib import Path

import main as agent_mod
from cg.api import to_observation_class
from cg.game import battle_finish, battle_select, battle_start

DECS = Path(__file__).resolve().parents[2] / "Decs"


def load_deck(path: Path) -> list[int]:
    ids = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [int(x) for x in ids[:60]]


def seat_agent(deck_ids):
    """Agent bound to a specific deck.

    The lookahead builds its hidden-info predictions from `agent_mod._MY_DECK`, which
    otherwise defaults to the submission `deck.csv`. Without this binding every
    seat would predict the submission deck's cards while actually piloting a
    different list, biasing the round-robin toward that deck."""
    def act(obs_dict):
        agent_mod._MY_DECK = deck_ids
        return agent_mod.agent(obs_dict)
    return act


def play_one(deck0, deck1, max_steps=3000) -> int:
    a0, a1 = seat_agent(deck0), seat_agent(deck1)
    obs_dict, start = battle_start(deck0, deck1)
    if obs_dict is None:
        return 2
    try:
        agents = [a0, a1]
        for _ in range(max_steps):
            obs = to_observation_class(obs_dict)
            if obs.current is not None and obs.current.result != -1:
                return obs.current.result
            pi = obs.current.yourIndex if obs.current else 0
            obs_dict = battle_select(agents[pi](obs_dict))
        return 2
    finally:
        battle_finish()


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    names = sorted(p.stem for p in DECS.glob("*.csv"))
    decks = {name: load_deck(DECS / f"{name}.csv") for name in names}

    # p0win[a][b] = P0 wins when a is P0 and b is P1, out of n.
    p0win = {a: {} for a in names}
    for a in names:
        for b in names:
            w0 = sum(1 for _ in range(n) if play_one(decks[a], decks[b]) == 0)
            p0win[a][b] = w0
        print(f"done P0={a}", flush=True)

    short = {name: name.replace("_ex", "").replace("_", " ")[:12] for name in names}

    def fmt_matrix(cellfn, title):
        lines = [f"### {title}", "", "| P0 \\ P1 | " + " | ".join(short[b] for b in names) + " |",
                 "|" + "---|" * (len(names) + 1)]
        for a in names:
            row = " | ".join(cellfn(a, b) for b in names)
            lines.append(f"| **{short[a]}** | {row} |")
        return "\n".join(lines)

    raw = fmt_matrix(lambda a, b: f"{p0win[a][b]/n:.0%}", f"Raw P0 win% ({n} games/cell)")

    # Seat-averaged: A's win rate vs B = mean(P0win(A,B), 1 - P0win(B,A)).
    def sa(a, b):
        return (p0win[a][b] / n + (1 - p0win[b][a] / n)) / 2

    avg = fmt_matrix(lambda a, b: f"{sa(a,b):.0%}", "Seat-averaged win% (bias-cancelled)")

    # Ranking by mean seat-averaged win rate vs the field (excluding mirror).
    ranking = []
    for a in names:
        others = [sa(a, b) for b in names if b != a]
        ranking.append((a, sum(others) / len(others)))
    ranking.sort(key=lambda x: -x[1])
    rank_txt = "### Deck strength ranking (mean seat-neutral win% vs field)\n\n" + "\n".join(
        f"{i+1}. **{a}** — {r:.1%}" for i, (a, r) in enumerate(ranking)
    )

    # Mirror seat bias check (P0 win% when a deck faces itself).
    bias = "### Seat bias check (mirror P0 win%)\n\n" + "\n".join(
        f"- {a}: {p0win[a][a]/n:.0%}" for a in names
    )

    out = "\n\n".join([f"# Round-robin results ({n} games/ordered pair, heuristic both seats)",
                       rank_txt, avg, raw, bias])
    Path(sys.argv[2] if len(sys.argv) > 2 else "round_robin_results.md").write_text(out + "\n", encoding="utf-8")
    print("\n" + rank_txt)
    print("\nWrote round_robin_results.md")


if __name__ == "__main__":
    main()
