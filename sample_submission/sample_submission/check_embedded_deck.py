"""Regression check for main.py's _EMBEDDED_DECK last-resort deck.

Two things must hold, or a Kaggle submission silently plays the wrong deck (or
no deck at all -- that failure mode cost submissions #55521916/#55522008/
#55522139, all rejected with "Player 1's deck does not have 60 cards"):

1. _EMBEDDED_DECK matches the sibling deck.csv exactly.
2. read_deck_csv() still returns the 60-card deck under Kaggle's exec model,
   i.e. with no __file__ defined and the CWD pointing somewhere unrelated.

Run from this directory:
    python check_embedded_deck.py
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load_deck_csv() -> list[int]:
    rows = [ln.strip() for ln in (HERE / "deck.csv").read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) >= 60, f"deck.csv has {len(rows)} rows, need >= 60"
    return [int(x) for x in rows[:60]]


def check_embedded_matches_csv() -> None:
    import main

    expected = _load_deck_csv()
    assert main._EMBEDDED_DECK == expected, (
        "main.py's _EMBEDDED_DECK is out of sync with deck.csv.\n"
        f"  deck.csv:       {expected}\n"
        f"  _EMBEDDED_DECK: {main._EMBEDDED_DECK}\n"
        "Update _EMBEDDED_DECK to match, or the Kaggle fallback ships the wrong deck."
    )
    assert len(main._EMBEDDED_DECK) == 60, "embedded deck must be exactly 60 cards"
    print(f"OK  _EMBEDDED_DECK matches deck.csv ({len(expected)} cards)")


def check_exec_model_without_file() -> None:
    """Replicate Kaggle: exec() the source with no __file__, from a foreign CWD."""
    source = (HERE / "main.py").read_text(encoding="utf-8")
    original_cwd = os.getcwd()
    sys.path.insert(0, str(HERE))
    try:
        os.chdir(tempfile.mkdtemp())
        env: dict = {}
        exec(compile(source, "main.py", "exec"), env)
        assert "__file__" not in env, "harness bug: __file__ leaked into the exec env"

        deck = env["read_deck_csv"]()
        assert len(deck) == 60, f"read_deck_csv() returned {len(deck)} cards, need 60"

        # The real entry point: obs with select=None is the deck request.
        obs = {"current": None, "logs": [], "remainingOverageTime": 600,
               "search_begin_input": None, "select": None, "step": 0}
        action = env["agent"](obs)
        assert len(action) == 60, (
            f"agent() returned {len(action)} cards under the exec model, need 60 "
            "-- Kaggle would reject this with 'deck does not have 60 cards'"
        )
        assert action == _load_deck_csv(), "agent() returned a deck that isn't deck.csv"
        print(f"OK  exec model with no __file__ + foreign CWD -> {len(action)} cards")
    finally:
        os.chdir(original_cwd)
        sys.path.remove(str(HERE))


def check_agent_is_last_callable() -> None:
    """Kaggle's runner uses the LAST callable defined in the module as the agent.

    Commit 569ca1d appended a 2-arg helper after _agent_impl, so Kaggle called
    that instead of the agent, got None, and rejected every episode. This
    asserts the entry point is still the real agent.
    """
    source = (HERE / "main.py").read_text(encoding="utf-8")

    import re

    defs = re.findall(r"^def (\w+)\(", source, re.M)
    assert defs, "no top-level defs found in main.py"
    assert defs[-1] == "agent", (
        f"the LAST top-level def in main.py is {defs[-1]!r}, not 'agent'.\n"
        "Kaggle takes the last callable as the entry point, so this ships a "
        "non-agent function and every episode fails validation. Move new "
        "helpers ABOVE agent()."
    )

    # Same check against the real exec env, not just the source text.
    sys.path.insert(0, str(HERE))
    try:
        env: dict = {}
        exec(compile(source, "main.py", "exec"), env)
        callables = [v for v in env.values() if callable(v) and getattr(v, "__module__", None) != "builtins"]
        last = callables[-1]
        assert last.__name__ == "agent", (
            f"last callable in the exec env is {last.__name__!r}, not 'agent'"
        )
    finally:
        sys.path.remove(str(HERE))
    print("OK  last top-level def / last callable is agent()")


if __name__ == "__main__":
    check_agent_is_last_callable()
    check_embedded_matches_csv()
    check_exec_model_without_file()
    print("PASS")
