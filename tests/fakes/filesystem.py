"""Filesystem fakes for tests."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from uk_sponsor_pipeline.infrastructure.io.validation import IncomingDataError, validate_as


def _empty_files() -> dict[str, object]:
    return {}


def _empty_mtimes() -> dict[str, float]:
    return {}


@dataclass
class InMemoryFileSystem:
    """In-memory filesystem for testing."""

    _files: dict[str, object] = field(default_factory=_empty_files)
    _mtimes: dict[str, float] = field(default_factory=_empty_mtimes)

    def read_csv(self, path: Path) -> pd.DataFrame:
        key = str(path)
        if key not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        data = self._files[key]
        if isinstance(data, pd.DataFrame):
            return data
        raise TypeError(f"Expected DataFrame at {path}")

    def write_csv(self, df: pd.DataFrame, path: Path) -> None:
        key = str(path)
        self._files[key] = df.copy()
        self._mtimes[key] = time.time()

    def append_csv(self, df: pd.DataFrame, path: Path) -> None:
        key = str(path)
        if key in self._files:
            existing = self.read_csv(path)
            combined = pd.concat([existing, df], ignore_index=True)
            self.write_csv(combined, path)
        else:
            self.write_csv(df, path)

    def read_json(self, path: Path) -> dict[str, object]:
        key = str(path)
        if key not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        data: object = self._files[key]
        try:
            return validate_as(dict[str, object], data)
        except IncomingDataError as exc:
            raise TypeError(f"Expected dict at {path}") from exc

    def write_json(self, data: Mapping[str, object], path: Path) -> None:
        key = str(path)
        self._files[key] = dict(data)
        self._mtimes[key] = time.time()

    def read_text(self, path: Path) -> str:
        key = str(path)
        if key not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        data = self._files[key]
        if isinstance(data, str):
            return data
        raise TypeError(f"Expected str at {path}")

    def write_text(self, content: str, path: Path) -> None:
        key = str(path)
        self._files[key] = content
        self._mtimes[key] = time.time()

    def read_bytes(self, path: Path) -> bytes:
        key = str(path)
        if key not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        data = self._files[key]
        if isinstance(data, bytes):
            return data
        raise TypeError(f"Expected bytes at {path}")

    def write_bytes(self, content: bytes, path: Path) -> None:
        key = str(path)
        self._files[key] = content
        self._mtimes[key] = time.time()

    def exists(self, path: Path) -> bool:
        return str(path) in self._files

    def mkdir(self, path: Path, parents: bool = True) -> None:
        # No-op for in-memory filesystem
        pass

    def list_files(self, path: Path, pattern: str = "*") -> list[Path]:
        import fnmatch

        prefix = str(path)
        matches: list[Path] = []
        for key in self._files:
            if key.startswith(prefix):
                relative = key[len(prefix) :].lstrip("/")
                if fnmatch.fnmatch(relative, pattern):
                    matches.append(Path(key))
        return sorted(matches)

    def mtime(self, path: Path) -> float:
        return self._mtimes.get(str(path), 0.0)
