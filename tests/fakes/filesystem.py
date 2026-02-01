"""Filesystem fakes for tests."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class InMemoryFileSystem:
    """In-memory filesystem for testing."""

    _files: dict[str, Any] = field(default_factory=dict)
    _mtimes: dict[str, float] = field(default_factory=dict)

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

    def read_json(self, path: Path) -> dict[str, Any]:
        key = str(path)
        if key not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        return self._files[key]

    def write_json(self, data: dict[str, Any], path: Path) -> None:
        key = str(path)
        self._files[key] = data
        self._mtimes[key] = time.time()

    def read_text(self, path: Path) -> str:
        key = str(path)
        if key not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        return self._files[key]

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
        matches = []
        for key in self._files:
            if key.startswith(prefix):
                relative = key[len(prefix) :].lstrip("/")
                if fnmatch.fnmatch(relative, pattern):
                    matches.append(Path(key))
        return sorted(matches)

    def mtime(self, path: Path) -> float:
        return self._mtimes.get(str(path), 0.0)
