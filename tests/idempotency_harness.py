"""Shared idempotency harness (Story 9.1 / ADR-0003).

Any loader proves the same three properties by describing itself with an
:class:`IdempotencyCase`:

* **run twice**: loading again changes nothing.
* **kill and resume**: a load killed part-way, then run again, ends exactly where a clean
  load ends.
* **wipe and reload**: deleting the derived rows and loading again reproduces them.

``snapshot`` must be a digest over *natural keys and content*, never surrogate UUIDs or
timestamps, or a correct reload would look different. ``wipe`` removes derived rows only;
retained artifact bytes are evidence and are never wiped.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

Snapshot = Mapping[str, Any]


@dataclass
class IdempotencyCase:
    """What the harness needs to know about one loader."""

    name: str
    load: Callable[[], object]
    snapshot: Callable[[], Snapshot]
    wipe: Callable[[], None]
    #: ``interrupt(point)`` returns a context manager inside which ``load`` raises at that
    #: point (0 = before any write, higher = later). ``points`` lists the ones to exercise.
    interrupt: Callable[[int], AbstractContextManager[None]] | None = None
    points: tuple[int, ...] = (0, 1)
    #: True when a killed load must leave the target exactly as it found it.
    atomic: bool = True


def _clean_reference(case: IdempotencyCase) -> Snapshot:
    case.wipe()
    case.load()
    return case.snapshot()


def assert_run_twice_same(case: IdempotencyCase) -> Snapshot:
    """Second load of unchanged input leaves the snapshot untouched."""
    reference = _clean_reference(case)
    case.load()
    again = case.snapshot()
    assert again == reference, f"{case.name}: a second run changed the result: {_diff(reference, again)}"
    return reference


def assert_kill_and_resume_same(case: IdempotencyCase) -> None:
    """A load killed at each point, then rerun, ends where a clean load ends."""
    assert case.interrupt is not None, f"{case.name}: no interrupt hook; cannot prove resume"
    reference = _clean_reference(case)
    for point in case.points:
        case.wipe()
        empty = case.snapshot()
        stopped = False
        try:
            with case.interrupt(point):
                case.load()
        except Exception:  # noqa: BLE001 - any failure is the simulated kill
            stopped = True
        assert stopped, f"{case.name}: interrupt at point {point} did not stop the load"
        if case.atomic:
            partial = case.snapshot()
            assert partial == empty, (
                f"{case.name}: killed at point {point} left partial data: {_diff(empty, partial)}"
            )
        case.load()
        resumed = case.snapshot()
        assert resumed == reference, (
            f"{case.name}: resume after a kill at point {point} differs from a clean load: "
            f"{_diff(reference, resumed)}"
        )


def assert_wipe_and_reload_same(case: IdempotencyCase) -> None:
    """Deleting the derived rows and loading again reproduces them exactly."""
    reference = _clean_reference(case)
    case.wipe()
    case.load()
    reloaded = case.snapshot()
    assert reloaded == reference, f"{case.name}: wipe-and-reload differs: {_diff(reference, reloaded)}"


def check_all(case: IdempotencyCase) -> None:
    """Run the three properties; kill-and-resume only when an interrupt hook is given."""
    assert_run_twice_same(case)
    assert_wipe_and_reload_same(case)
    if case.interrupt is not None:
        assert_kill_and_resume_same(case)


def _diff(a: Snapshot, b: Snapshot) -> dict[str, tuple[Any, Any]]:
    return {k: (a.get(k), b.get(k)) for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)}
