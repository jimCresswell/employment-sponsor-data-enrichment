"""CLI progress reporter implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import override

from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from .protocols import ProgressReporter


def _build_progress() -> Progress:
    return Progress(
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        transient=True,
    )


def _default_task_id() -> TaskID | None:
    return None


@dataclass
class CliProgressReporter(ProgressReporter):
    """Rich-based progress reporter for CLI commands."""

    _progress: Progress = field(default_factory=_build_progress)
    _task_id: TaskID | None = field(default_factory=_default_task_id)
    _started: bool = False

    @override
    def start(self, label: str, total: int | None) -> None:
        if not self._started:
            self._progress.start()
            self._started = True
        if self._task_id is not None:
            self._progress.remove_task(self._task_id)
        self._task_id = self._progress.add_task(label, total=total)

    @override
    def advance(self, count: int) -> None:
        if self._task_id is None:
            return
        self._progress.advance(self._task_id, count)

    @override
    def finish(self) -> None:
        if self._task_id is None:
            return
        self._progress.stop_task(self._task_id)
        self._progress.remove_task(self._task_id)
        self._task_id = None
        if self._started:
            self._progress.stop()
            self._started = False
