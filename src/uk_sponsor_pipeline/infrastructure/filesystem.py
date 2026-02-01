"""Filesystem implementations for infrastructure.

Usage example:
    from pathlib import Path

    import pandas as pd

    from uk_sponsor_pipeline.infrastructure.filesystem import LocalFileSystem

    fs = LocalFileSystem()
    fs.write_csv(pd.DataFrame({"col": ["a"]}), Path("data/out.csv"))
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pandas as pd

from ..protocols import FileSystem


class LocalFileSystem(FileSystem):
    """Local filesystem implementation."""

    def read_csv(self, path: Path) -> pd.DataFrame:
        return pd.read_csv(path, dtype=str).fillna("")

    def write_csv(self, df: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)

    def append_csv(self, df: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists()
        df.to_csv(path, mode="a", header=write_header, index=False)

    def read_json(self, path: Path) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))

    def write_json(self, data: dict[str, Any], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def write_text(self, content: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def read_bytes(self, path: Path) -> bytes:
        return path.read_bytes()

    def write_bytes(self, content: bytes, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def exists(self, path: Path) -> bool:
        return path.exists()

    def mkdir(self, path: Path, parents: bool = True) -> None:
        path.mkdir(parents=parents, exist_ok=True)

    def list_files(self, path: Path, pattern: str = "*") -> list[Path]:
        return sorted(path.glob(pattern))

    def mtime(self, path: Path) -> float:
        return path.stat().st_mtime
