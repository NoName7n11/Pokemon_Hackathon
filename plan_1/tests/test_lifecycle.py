from __future__ import annotations

import unittest
from dataclasses import dataclass
from types import SimpleNamespace

import _path  # noqa: F401

from plan1.engine.lifecycle import SearchInputs, SearchSession, SearchSessionError


@dataclass
class FakeState:
    searchId: int


class FakeBackend:
    def __init__(self, fail_step: bool = False, fail_begin: bool = False):
        self.next_id = 1
        self.begin_calls: list[tuple] = []
        self.step_calls: list[tuple[int, list[int]]] = []
        self.release_calls: list[int] = []
        self.end_calls = 0
        self.fail_step = fail_step
        self.fail_begin = fail_begin

    def search_begin(self, *args, **kwargs):
        self.begin_calls.append((args, kwargs))
        if self.fail_begin:
            raise RuntimeError("begin failed")
        return FakeState(0)

    def search_step(self, search_id, select):
        self.step_calls.append((search_id, select))
        if self.fail_step:
            raise RuntimeError("step failed")
        state = FakeState(self.next_id)
        self.next_id += 1
        return state

    def search_release(self, search_id):
        self.release_calls.append(search_id)

    def search_end(self):
        self.end_calls += 1


def inputs() -> SearchInputs:
    return SearchInputs.from_sequences(
        your_deck=[1], your_prize=[2], opponent_deck=[3], opponent_prize=[4], opponent_hand=[5]
    )


class LifecycleTests(unittest.TestCase):
    def test_context_closes_once_and_disables_manual_coin(self) -> None:
        backend = FakeBackend()
        with SearchSession(backend, SimpleNamespace(), inputs()) as session:
            child = session.step(session.root, [0])
            self.assertEqual(child.searchId, 1)
        session.close()
        self.assertEqual(backend.end_calls, 1)
        self.assertFalse(backend.begin_calls[0][1]["manual_coin"])

    def test_exception_still_ends_search(self) -> None:
        backend = FakeBackend(fail_step=True)
        with self.assertRaisesRegex(RuntimeError, "step failed"):
            with SearchSession(backend, SimpleNamespace(), inputs()) as session:
                session.step(session.root, [0])
        self.assertEqual(backend.end_calls, 1)

    def test_begin_exception_attempts_cleanup(self) -> None:
        backend = FakeBackend(fail_begin=True)
        session = SearchSession(backend, SimpleNamespace(), inputs())
        with self.assertRaisesRegex(RuntimeError, "begin failed"):
            with session:
                pass
        self.assertTrue(session.closed)
        self.assertEqual(backend.end_calls, 1)

    def test_foreign_and_released_states_rejected(self) -> None:
        backend = FakeBackend()
        with SearchSession(backend, SimpleNamespace(), inputs()) as session:
            with self.assertRaisesRegex(SearchSessionError, "not owned"):
                session.step(FakeState(99), [0])
            session.release(session.root)
            with self.assertRaisesRegex(SearchSessionError, "released"):
                session.step(session.root, [0])
        self.assertEqual(backend.release_calls, [0])

    def test_release_is_idempotent_and_surviving_child_remains_owned(self) -> None:
        backend = FakeBackend()
        with SearchSession(backend, SimpleNamespace(), inputs()) as session:
            child = session.step(session.root, [0])
            session.release(session.root)
            session.release(session.root)
            grandchild = session.step(child, [0])
            self.assertEqual(grandchild.searchId, 2)
        self.assertEqual(backend.release_calls, [0])

    def test_card_ids_must_be_positive_integers(self) -> None:
        with self.assertRaises(ValueError):
            SearchInputs.from_sequences(
                your_deck=[0], your_prize=[2], opponent_deck=[3], opponent_prize=[4], opponent_hand=[5]
            )


if __name__ == "__main__":
    unittest.main()
