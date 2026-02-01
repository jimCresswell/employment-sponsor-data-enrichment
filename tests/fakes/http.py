"""HTTP fakes for tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeHttpClient:
    """Fake HTTP client that returns canned responses."""

    responses: dict[str, dict[str, Any]] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def get_json(self, url: str, cache_key: str | None = None) -> dict[str, Any]:
        self.calls.append(url)
        # Match by URL prefix for flexibility
        for pattern, response in self.responses.items():
            if pattern in url:
                return response
        raise ValueError(f"No canned response for URL: {url}")
