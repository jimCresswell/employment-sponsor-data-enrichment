"""Deprecated HTTP helpers (kept for compatibility).

Prefer using `uk_sponsor_pipeline.infrastructure.CachedHttpClient` directly.
"""

from __future__ import annotations

from typing import Any

import requests

from ..infrastructure import CachedHttpClient, CircuitBreaker, DiskCache, NullCache, RateLimiter


def get_json(
    session: requests.Session,
    url: str,
    cache: DiskCache | None,
    cache_key: str | None,
    sleep_s: float = 0.0,
) -> dict[str, Any]:
    """Legacy wrapper around CachedHttpClient.

    Note: This creates a new client per call, so circuit breaker state is not shared.
    """
    cache_impl = cache or NullCache()
    rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=sleep_s)
    circuit_breaker = CircuitBreaker(threshold=5)
    client = CachedHttpClient(
        session=session,
        cache=cache_impl,
        rate_limiter=rate_limiter,
        circuit_breaker=circuit_breaker,
        sleep_seconds=sleep_s,
    )
    return client.get_json(url, cache_key)
