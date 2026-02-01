"""Cache fakes for tests."""

from __future__ import annotations

from dataclasses import dataclass, field


def _empty_store() -> dict[str, dict[str, object]]:
    return {}


@dataclass
class InMemoryCache:
    """In-memory cache for testing."""

    _store: dict[str, dict[str, object]] = field(default_factory=_empty_store)

    def get(self, key: str) -> dict[str, object] | None:
        return self._store.get(key)

    def set(self, key: str, value: dict[str, object]) -> None:
        self._store[key] = value

    def has(self, key: str) -> bool:
        return key in self._store
