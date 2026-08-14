from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from plan1.data.replay_buffer import CorpusStore
from plan1.data.trajectory import DecisionRecord, GameTrajectory


@dataclass(frozen=True, slots=True)
class ReplaySelection:
    split: str
    games: tuple[GameTrajectory, ...]
    source_manifests: tuple[str, ...]

    @property
    def decisions(self) -> tuple[DecisionRecord, ...]:
        return tuple(decision for game in self.games for decision in game.decisions)

    @property
    def game_ids(self) -> tuple[str, ...]:
        return tuple(game.game_id for game in self.games)


def select_replay_window(
    stores: Sequence[CorpusStore],
    *,
    split: str,
    max_games: int,
) -> ReplaySelection:
    if split not in {"train", "validation"} or max_games < 1:
        raise ValueError("replay split must be train/validation and max_games positive")
    games: list[GameTrajectory] = []
    manifests: list[str] = []
    seen: set[str] = set()
    for store in stores:
        manifest = store.load_manifest()
        manifests.append(manifest.fingerprint)
        for entry in manifest.entries:
            if entry.purpose != "training" or entry.split != split:
                continue
            game = store.read_entry(entry)
            if game.game_id in seen:
                raise ValueError(f"duplicate replay game ID across stores: {game.game_id}")
            seen.add(game.game_id)
            games.append(game)
    games.sort(key=lambda game: (game.created_utc, game.game_id))
    selected = tuple(games[-max_games:])
    if not selected:
        raise ValueError(f"replay window has no {split} games")
    return ReplaySelection(split, selected, tuple(manifests))
