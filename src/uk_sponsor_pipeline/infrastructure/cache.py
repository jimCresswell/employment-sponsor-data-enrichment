"""Cache implementations for infrastructure.

Usage example:
    from pathlib import Path

    from uk_sponsor_pipeline.infrastructure.cache import DiskCache

    cache = DiskCache(Path("data/cache"))
    cache.set("key", {"value": 1})
    cached = cache.get("key")
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ..protocols import Cache


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

    def get(self, key: str) -> dict[str, Any] | None:
        p = self._path(key)
        if p.exists():
            return cast(dict[str, Any], json.loads(p.read_text(encoding="utf-8")))
        return None

    def set(self, key: str, value: dict[str, Any]) -> None:
        p = self._path(key)
        p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def has(self, key: str) -> bool:
        return self._path(key).exists()
