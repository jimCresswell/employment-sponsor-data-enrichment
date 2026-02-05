"""Progress reporter fakes for tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import override

from uk_sponsor_pipeline.protocols import ProgressReporter


def _empty_starts() -> list[tuple[str, int | None]]:
    return []


def _empty_advances() -> list[int]:
    return []


@dataclass
class FakeProgressReporter(ProgressReporter):
    """In-memory progress reporter for assertions."""

    starts: list[tuple[str, int | None]] = field(default_factory=_empty_starts)
    advances: list[int] = field(default_factory=_empty_advances)
    finished: int = 0

    @override
    def start(self, label: str, total: int | None) -> None:
        self.starts.append((label, total))

    @override
    def advance(self, count: int) -> None:
        self.advances.append(count)

    @override
    def finish(self) -> None:
        self.finished += 1
