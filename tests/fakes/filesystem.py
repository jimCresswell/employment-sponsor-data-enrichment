"""Filesystem fakes for tests."""

from __future__ import annotations

import io
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, TextIO, override

import pandas as pd

from tests.support.errors import FakeFileNotFoundError, FakeFileTypeError
from uk_sponsor_pipeline.io_validation import IncomingDataError, validate_as
from uk_sponsor_pipeline.protocols import BinaryOpenMode, FileSystem, TextOpenMode


def _empty_files() -> dict[str, object]:
    return {}


def _empty_mtimes() -> dict[str, float]:
    return {}


@dataclass
class InMemoryFileSystem(FileSystem):
    """In-memory filesystem for testing."""

    _files: dict[str, object] = field(default_factory=_empty_files)
    _mtimes: dict[str, float] = field(default_factory=_empty_mtimes)

    @override
    def read_csv(self, path: Path) -> pd.DataFrame:
        key = str(path)
        if key not in self._files:
            raise FakeFileNotFoundError(str(path))
        data = self._files[key]
        if isinstance(data, pd.DataFrame):
            return data
        raise FakeFileTypeError("DataFrame", str(path))

    @override
    def write_csv(self, df: pd.DataFrame, path: Path) -> None:
        key = str(path)
        self._files[key] = df.copy()
        self._mtimes[key] = time.time()

    @override
    def append_csv(self, df: pd.DataFrame, path: Path) -> None:
        key = str(path)
        if key in self._files:
            existing = self.read_csv(path)
            combined = pd.concat([existing, df], ignore_index=True)
            self.write_csv(combined, path)
        else:
            self.write_csv(df, path)

    @override
    def read_json(self, path: Path) -> dict[str, object]:
        key = str(path)
        if key not in self._files:
            raise FakeFileNotFoundError(str(path))
        data: object = self._files[key]
        try:
            return validate_as(dict[str, object], data)
        except IncomingDataError as exc:
            raise FakeFileTypeError("dict", str(path)) from exc

    @override
    def write_json(self, data: Mapping[str, object], path: Path) -> None:
        key = str(path)
        self._files[key] = dict(data)
        self._mtimes[key] = time.time()

    @override
    def read_text(self, path: Path) -> str:
        key = str(path)
        if key not in self._files:
            raise FakeFileNotFoundError(str(path))
        data = self._files[key]
        if isinstance(data, str):
            return data
        raise FakeFileTypeError("str", str(path))

    @override
    def write_text(self, content: str, path: Path) -> None:
        key = str(path)
        self._files[key] = content
        self._mtimes[key] = time.time()

    @override
    def read_bytes(self, path: Path) -> bytes:
        key = str(path)
        if key not in self._files:
            raise FakeFileNotFoundError(str(path))
        data = self._files[key]
        if isinstance(data, bytes):
            return data
        raise FakeFileTypeError("bytes", str(path))

    @override
    def write_bytes(self, content: bytes, path: Path) -> None:
        key = str(path)
        self._files[key] = content
        self._mtimes[key] = time.time()

    @override
    def write_bytes_stream(self, path: Path, chunks: Iterable[bytes]) -> None:
        key = str(path)
        buffer = bytearray()
        for chunk in chunks:
            buffer.extend(chunk)
        self._files[key] = bytes(buffer)
        self._mtimes[key] = time.time()

    @override
    def open_text(
        self,
        path: Path,
        *,
        mode: TextOpenMode,
        encoding: str,
        newline: str | None = None,
    ) -> TextIO:
        _ = (encoding, newline)
        if "b" in mode:
            raise ValueError
        key = str(path)
        initial = _resolve_initial_text(self._files, key, mode)
        initial_position = 0
        if "a" in mode:
            initial_position = len(initial)
        return _InMemoryTextHandle(
            initial_value=initial,
            initial_position=initial_position,
            files=self._files,
            mtimes=self._mtimes,
            key=key,
            write_back=_mode_writes(mode),
        )

    @override
    def open_binary(self, path: Path, *, mode: BinaryOpenMode) -> BinaryIO:
        key = str(path)
        initial = _resolve_initial_bytes(self._files, key, mode)
        initial_position = 0
        if "a" in mode:
            initial_position = len(initial)
        return _InMemoryBinaryHandle(
            initial_value=initial,
            initial_position=initial_position,
            files=self._files,
            mtimes=self._mtimes,
            key=key,
            write_back=_mode_writes(mode),
        )

    @override
    def exists(self, path: Path) -> bool:
        return str(path) in self._files

    @override
    def rename(self, src: Path, dest: Path) -> None:
        src_key = str(src)
        dest_key = str(dest)
        updates: dict[str, object] = {}
        updated_times: dict[str, float] = {}
        for key, value in list(self._files.items()):
            if key == src_key or key.startswith(f"{src_key}/"):
                suffix = key[len(src_key) :]
                new_key = f"{dest_key}{suffix}"
                updates[new_key] = value
                updated_times[new_key] = self._mtimes.get(key, time.time())
                del self._files[key]
                self._mtimes.pop(key, None)
        self._files.update(updates)
        self._mtimes.update(updated_times)

    @override
    def mkdir(self, path: Path, parents: bool = True) -> None:
        # No-op for in-memory filesystem
        pass

    @override
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

    @override
    def mtime(self, path: Path) -> float:
        return self._mtimes.get(str(path), 0.0)


@dataclass
class _InMemoryTextHandle(io.StringIO):
    """Text handle that writes back to the in-memory filesystem on close."""

    initial_value: str
    initial_position: int
    files: dict[str, object]
    mtimes: dict[str, float]
    key: str
    write_back: bool

    def __post_init__(self) -> None:
        super().__init__(self.initial_value)
        self.seek(self.initial_position)

    @override
    def close(self) -> None:
        if not self.closed and self.write_back:
            self.files[self.key] = self.getvalue()
            self.mtimes[self.key] = time.time()
        super().close()


@dataclass
class _InMemoryBinaryHandle(io.BytesIO):
    """Binary handle that writes back to the in-memory filesystem on close."""

    initial_value: bytes
    initial_position: int
    files: dict[str, object]
    mtimes: dict[str, float]
    key: str
    write_back: bool

    def __post_init__(self) -> None:
        super().__init__(self.initial_value)
        self.seek(self.initial_position)

    @override
    def close(self) -> None:
        if not self.closed and self.write_back:
            self.files[self.key] = self.getvalue()
            self.mtimes[self.key] = time.time()
        super().close()


def _mode_writes(mode: str) -> bool:
    return any(flag in mode for flag in ("w", "a", "x", "+"))


def _resolve_initial_text(files: dict[str, object], key: str, mode: TextOpenMode) -> str:
    if mode.startswith("r"):
        if key not in files:
            raise FakeFileNotFoundError(key)
        value = files[key]
        if isinstance(value, str):
            return value
        raise FakeFileTypeError("str", key)
    if "a" in mode:
        if key not in files:
            return ""
        value = files[key]
        if isinstance(value, str):
            return value
        raise FakeFileTypeError("str", key)
    if "x" in mode and key in files:
        raise FileExistsError(key)
    return ""


def _resolve_initial_bytes(files: dict[str, object], key: str, mode: BinaryOpenMode) -> bytes:
    if mode.startswith("r"):
        if key not in files:
            raise FakeFileNotFoundError(key)
        value = files[key]
        if isinstance(value, bytes):
            return value
        raise FakeFileTypeError("bytes", key)
    if "a" in mode:
        if key not in files:
            return b""
        value = files[key]
        if isinstance(value, bytes):
            return value
        raise FakeFileTypeError("bytes", key)
    if "x" in mode and key in files:
        raise FileExistsError(key)
    return b""
