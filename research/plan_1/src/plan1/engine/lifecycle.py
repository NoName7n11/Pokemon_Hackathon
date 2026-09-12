from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence


class SearchBackend(Protocol):
    def search_begin(self, *args: Any, **kwargs: Any) -> Any: ...
    def search_step(self, search_id: int, select: list[int]) -> Any: ...
    def search_release(self, search_id: int) -> None: ...
    def search_end(self) -> None: ...


class SearchSessionError(RuntimeError):
    """Raised for invalid ownership or lifecycle operations."""


@dataclass(frozen=True)
class SearchInputs:
    your_deck: tuple[int, ...]
    your_prize: tuple[int, ...]
    opponent_deck: tuple[int, ...]
    opponent_prize: tuple[int, ...]
    opponent_hand: tuple[int, ...]
    opponent_active: tuple[int, ...] = ()

    @classmethod
    def from_sequences(
        cls,
        *,
        your_deck: Sequence[int],
        your_prize: Sequence[int],
        opponent_deck: Sequence[int],
        opponent_prize: Sequence[int],
        opponent_hand: Sequence[int],
        opponent_active: Sequence[int] = (),
    ) -> "SearchInputs":
        fields = {
            "your_deck": your_deck,
            "your_prize": your_prize,
            "opponent_deck": opponent_deck,
            "opponent_prize": opponent_prize,
            "opponent_hand": opponent_hand,
            "opponent_active": opponent_active,
        }
        normalized: dict[str, tuple[int, ...]] = {}
        for name, values in fields.items():
            if not all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in values):
                raise ValueError(f"{name} must contain positive integer card IDs")
            normalized[name] = tuple(values)
        return cls(**normalized)


class SearchSession:
    """Own one native search session and guarantee one final `search_end` call.

    Explicit `release` is available after branch semantics are proven. Closing a
    session relies on `search_end`, the API's documented whole-session cleanup,
    rather than guessing a safe parent/child release order.
    """

    def __init__(self, backend: SearchBackend, observation: Any, inputs: SearchInputs):
        self._backend = backend
        self._observation = observation
        self._inputs = inputs
        self._root: Any | None = None
        self._known_ids: set[int] = set()
        self._released_ids: set[int] = set()
        self._closed = False

    @property
    def root(self) -> Any:
        if self._root is None:
            raise SearchSessionError("search session has not been entered")
        return self._root

    @property
    def closed(self) -> bool:
        return self._closed

    def __enter__(self) -> "SearchSession":
        if self._closed or self._root is not None:
            raise SearchSessionError("search session cannot be entered more than once")
        i = self._inputs
        # Production search intentionally has no manual-coin escape hatch.
        try:
            self._root = self._backend.search_begin(
                self._observation,
                list(i.your_deck),
                list(i.your_prize),
                list(i.opponent_deck),
                list(i.opponent_prize),
                list(i.opponent_hand),
                list(i.opponent_active),
                manual_coin=False,
            )
        except BaseException:
            # SearchBegin may allocate native state before reporting an error.
            # Preserve the original exception even if defensive cleanup fails.
            try:
                self._backend.search_end()
            except BaseException:
                pass
            self._closed = True
            raise
        self._known_ids.add(self._state_id(self._root))
        return self

    def step(self, state: Any, selection: Sequence[int]) -> Any:
        self._ensure_open()
        state_id = self._state_id(state)
        if state_id not in self._known_ids:
            raise SearchSessionError(f"search state {state_id} is not owned by this session")
        if state_id in self._released_ids:
            raise SearchSessionError(f"search state {state_id} has already been released")
        if not isinstance(selection, (list, tuple)) or not all(
            isinstance(value, int) and not isinstance(value, bool) for value in selection
        ):
            raise TypeError("selection must be a sequence of integer option indices")
        child = self._backend.search_step(state_id, list(selection))
        self._known_ids.add(self._state_id(child))
        return child

    def release(self, state: Any) -> None:
        self._ensure_open()
        state_id = self._state_id(state)
        if state_id not in self._known_ids:
            raise SearchSessionError(f"search state {state_id} is not owned by this session")
        if state_id in self._released_ids:
            return
        self._backend.search_release(state_id)
        self._released_ids.add(state_id)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._root is not None:
                self._backend.search_end()
        finally:
            self._known_ids.clear()

    def __exit__(self, exc_type: Any, exc: BaseException | None, traceback: Any) -> bool:
        self.close()
        return False

    def _ensure_open(self) -> None:
        if self._closed or self._root is None:
            raise SearchSessionError("search session is not open")

    @staticmethod
    def _state_id(state: Any) -> int:
        state_id = getattr(state, "searchId", None)
        if not isinstance(state_id, int):
            raise SearchSessionError("search state does not expose an integer searchId")
        return state_id
