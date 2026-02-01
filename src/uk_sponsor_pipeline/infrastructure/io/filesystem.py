"""Filesystem implementations for infrastructure.

Usage example:
    from pathlib import Path

    import pandas as pd

    from uk_sponsor_pipeline.infrastructure.io.filesystem import DiskCache, LocalFileSystem

    fs = LocalFileSystem()
    fs.write_csv(pd.DataFrame({"col": ["a"]}), Path("data/out.csv"))

    cache = DiskCache(Path("data/cache"))
    cache.set("key", {"value": 1})
    cached = cache.get("key")
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import override

import pandas as pd

from ...protocols import Cache, FileSystem
from .validation import IncomingDataError, validate_json_as


class LocalFileSystem(FileSystem):
    """Local filesystem implementation."""

    @override
    def read_csv(self, path: Path) -> pd.DataFrame:
        return pd.read_csv(path, dtype=str).fillna("")

    @override
    def write_csv(self, df: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)

    @override
    def append_csv(self, df: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists()
        df.to_csv(path, mode="a", header=write_header, index=False)

    @override
    def read_json(self, path: Path) -> dict[str, object]:
        payload = path.read_text(encoding="utf-8")
        try:
            return validate_json_as(dict[str, object], payload)
        except IncomingDataError as exc:
            raise RuntimeError("JSON file must contain an object.") from exc

    @override
    def write_json(self, data: Mapping[str, object], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(data), ensure_ascii=False, indent=2), encoding="utf-8")

    @override
    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    @override
    def write_text(self, content: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @override
    def read_bytes(self, path: Path) -> bytes:
        return path.read_bytes()

    @override
    def write_bytes(self, content: bytes, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    @override
    def exists(self, path: Path) -> bool:
        return path.exists()

    @override
    def mkdir(self, path: Path, parents: bool = True) -> None:
        path.mkdir(parents=parents, exist_ok=True)

    @override
    def list_files(self, path: Path, pattern: str = "*") -> list[Path]:
        return sorted(path.glob(pattern))

    @override
    def mtime(self, path: Path) -> float:
        return path.stat().st_mtime


@dataclass
class DiskCache(Cache):
    """File-based cache implementation."""

    cache_dir: Path

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{h}.json"

    @override
    def get(self, key: str) -> dict[str, object] | None:
        p = self._path(key)
        if p.exists():
            payload = p.read_text(encoding="utf-8")
            try:
                return validate_json_as(dict[str, object], payload)
            except IncomingDataError as exc:
                raise RuntimeError("Cache data must be a JSON object.") from exc
        return None

    @override
    def set(self, key: str, value: dict[str, object]) -> None:
        p = self._path(key)
        p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    @override
    def has(self, key: str) -> bool:
        return self._path(key).exists()
