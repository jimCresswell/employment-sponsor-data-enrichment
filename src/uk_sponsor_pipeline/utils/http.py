from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests


@dataclass
class DiskCache:
    cache_dir: Path

    def __post_init__(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{h}.json"

    def get(self, key: str) -> Optional[dict]:
        p = self._path(key)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return None

    def set(self, key: str, value: dict) -> None:
        p = self._path(key)
        p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def get_json(
    session: requests.Session,
    url: str,
    cache: Optional[DiskCache],
    cache_key: Optional[str],
    sleep_s: float = 0.0,
) -> Dict[str, Any]:
    if cache and cache_key:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    r = session.get(url, timeout=30)
    if r.status_code == 429:
        # light backoff
        time.sleep(max(5.0, sleep_s) * 6)
        r = session.get(url, timeout=30)

    r.raise_for_status()
    data = r.json()

    if cache and cache_key:
        cache.set(cache_key, data)

    if sleep_s > 0:
        time.sleep(sleep_s)

    return data
