"""Shared Rich terminal feedback for bounded, resumable project operations."""
from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Callable, Iterator
from time import monotonic

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn


@contextmanager
def progress(label: str, total: int) -> Iterator[Callable[[str], None]]:
    """Render a progress bar and yield a callback that advances one work unit."""
    console = Console()
    columns = [SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), TimeElapsedColumn(), TimeRemainingColumn()]
    with Progress(*columns, console=console) as display:
        task_id = display.add_task(label, total=total)

        def advance(phase: str) -> None:
            """Advance one unit while explaining the current provider phase."""
            display.update(task_id, advance=1, description=phase)

        yield advance


@contextmanager
def timed(label: str, seconds: int) -> Iterator[Callable[[str], None]]:
    """Render elapsed/remaining time for a bounded runner with unknown item count."""
    console = Console()
    columns = [SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), TimeElapsedColumn(), TimeRemainingColumn()]
    started = monotonic()
    with Progress(*columns, console=console) as display:
        task_id = display.add_task(label, total=seconds)

        def update(phase: str) -> None:
            """Refresh the time budget and describe the provider's current phase."""
            display.update(task_id, completed=min(seconds, monotonic() - started), description=phase)

        yield update


@contextmanager
def spinner(label: str) -> Iterator[Callable[[str], None]]:
    """Render elapsed-time feedback when a safe work total is unavailable."""
    console = Console()
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), TimeElapsedColumn(), console=console) as display:
        task_id = display.add_task(label, total=None)

        def update(phase: str) -> None:
            """Refresh the current operation phase without inventing an ETA."""
            display.update(task_id, description=phase)

        yield update
