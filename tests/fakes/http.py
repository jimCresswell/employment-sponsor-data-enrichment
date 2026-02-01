"""HTTP fakes for tests."""

from __future__ import annotations

from dataclasses import dataclass, field


def _empty_responses() -> dict[str, dict[str, object]]:
    return {}


def _empty_calls() -> list[str]:
    return []


@dataclass
class FakeHttpClient:
    """Fake HTTP client that returns canned responses."""

    responses: dict[str, dict[str, object]] = field(default_factory=_empty_responses)
    calls: list[str] = field(default_factory=_empty_calls)

    def get_json(self, url: str, cache_key: str | None = None) -> dict[str, object]:
        self.calls.append(url)
        # Match by URL prefix for flexibility
        for pattern, response in self.responses.items():
            if pattern in url:
                return response
        raise ValueError(f"No canned response for URL: {url}")
