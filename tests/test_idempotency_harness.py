"""The harness must pass a correct loader and fail each kind of broken one."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from idempotency_harness import (
    IdempotencyCase,
    assert_kill_and_resume_same,
    assert_run_twice_same,
    assert_wipe_and_reload_same,
    check_all,
)

SOURCE = [("a", 1), ("b", 2), ("c", 3), ("d", 4)]


class FakeLoader:
    """An in-memory target with switches that make it correct or subtly wrong."""

    def __init__(self, *, append_on_rerun=False, non_atomic=False, drift_on_reload=False, unresumable=False):
        self.rows: dict[str, int] = {}
        self.log: list[tuple[str, int]] = []
        self.kill_at: int | None = None
        self.append_on_rerun, self.non_atomic = append_on_rerun, non_atomic
        self.drift_on_reload, self.unresumable = drift_on_reload, unresumable
        self.was_killed = False
        self.wipes = 0

    def load(self) -> None:
        if self.unresumable and self.was_killed:
            self.was_killed = False
            return  # the resume after a kill silently loads nothing
        staged: dict[str, int] = {}
        target = self.rows if self.non_atomic else staged
        for index, (key, value) in enumerate(SOURCE):
            if self.kill_at is not None and index >= self.kill_at:
                self.was_killed = True
                raise RuntimeError("killed")
            if self.append_on_rerun and key in self.rows:
                self.log.append((key, value))  # duplicate work recorded
            target[key] = value + (self.wipes if self.drift_on_reload else 0)
        if not self.non_atomic:
            self.rows.update(staged)

    def wipe(self) -> None:
        self.rows = {}
        self.was_killed = False
        self.wipes += 1

    @contextmanager
    def interrupt(self, point: int):
        self.kill_at = point
        try:
            yield
        finally:
            self.kill_at = None

    def snapshot(self):
        return {"rows": len(self.rows), "content": tuple(sorted(self.rows.items())), "log": len(self.log)}

    def case(self) -> IdempotencyCase:
        return IdempotencyCase("fake", self.load, self.snapshot, self.wipe, self.interrupt, points=(0, 2))


def test_correct_loader_passes_all_three_properties() -> None:
    check_all(FakeLoader().case())


def test_loader_that_duplicates_work_on_rerun_fails_run_twice() -> None:
    with pytest.raises(AssertionError, match="second run changed"):
        assert_run_twice_same(FakeLoader(append_on_rerun=True).case())


def test_loader_that_leaves_partial_rows_fails_atomic_kill() -> None:
    with pytest.raises(AssertionError, match="left partial data"):
        assert_kill_and_resume_same(FakeLoader(non_atomic=True).case())


def test_non_atomic_loader_may_declare_it_and_still_must_converge() -> None:
    case = FakeLoader(non_atomic=True).case()
    case.atomic = False
    assert_kill_and_resume_same(case)


def test_loader_whose_reload_differs_fails_wipe_and_reload() -> None:
    with pytest.raises(AssertionError, match="wipe-and-reload differs"):
        assert_wipe_and_reload_same(FakeLoader(drift_on_reload=True).case())


def test_loader_that_cannot_resume_fails_kill_and_resume() -> None:
    with pytest.raises(AssertionError, match="differs from a clean load"):
        assert_kill_and_resume_same(FakeLoader(unresumable=True).case())


def test_interrupt_that_does_not_stop_the_load_is_reported() -> None:
    loader = FakeLoader()
    case = loader.case()
    case.interrupt = lambda point: contextmanager(lambda: (yield))()  # never arms a kill
    with pytest.raises(AssertionError, match="did not stop the load"):
        assert_kill_and_resume_same(case)


def test_resume_needs_an_interrupt_hook() -> None:
    case = FakeLoader().case()
    case.interrupt = None
    with pytest.raises(AssertionError, match="no interrupt hook"):
        assert_kill_and_resume_same(case)
