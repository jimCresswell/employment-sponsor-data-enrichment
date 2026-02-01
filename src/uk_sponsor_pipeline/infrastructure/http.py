"""HTTP client implementations for infrastructure.

Usage example:
    import requests
    from pathlib import Path

    from uk_sponsor_pipeline.infrastructure.cache import DiskCache
    from uk_sponsor_pipeline.infrastructure.http import CachedHttpClient
    from uk_sponsor_pipeline.infrastructure.resilience import CircuitBreaker, RateLimiter

    session = requests.Session()
    cache = DiskCache(Path("data/cache"))
    client = CachedHttpClient(
        session=session,
        cache=cache,
        rate_limiter=RateLimiter(),
        circuit_breaker=CircuitBreaker(),
    )
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, cast

import requests

from ..exceptions import AuthenticationError, RateLimitError
from ..protocols import Cache, CircuitBreaker, RateLimiter, RetryPolicy
from .resilience import CircuitBreaker as CircuitBreakerImpl
from .resilience import RateLimiter as RateLimiterImpl
from .resilience import RetryPolicy as RetryPolicyImpl


def _is_auth_error(error: Exception) -> bool:
    """Check if an exception indicates an authentication error."""
    if isinstance(error, requests.HTTPError):
        if error.response is not None and error.response.status_code == 401:
            return True
    error_str = str(error).lower()
    return "401" in error_str or "unauthorized" in error_str


def _is_rate_limit_error(error: Exception) -> bool:
    """Check if an exception indicates a rate limit error."""
    if isinstance(error, requests.HTTPError):
        if error.response is not None and error.response.status_code == 429:
            return True
    error_str = str(error).lower()
    return "429" in error_str or "rate limit" in error_str or "too many requests" in error_str


def _parse_retry_after(headers: Mapping[str, str] | None) -> int | None:
    """Parse Retry-After header into seconds, if available."""
    if not headers:
        return None
    value = headers.get("Retry-After")
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return int(value)
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        delta = (dt - datetime.now(UTC)).total_seconds()
        return max(0, int(delta))
    except Exception:
        return None


def _response_details(response: requests.Response) -> str:
    """Return a compact status/body summary for error reporting."""
    try:
        body = response.text
    except Exception:
        body = "<unreadable>"
    body = " ".join(body.split())
    if len(body) > 300:
        body = body[:300] + "..."
    return f"status={response.status_code}, body={body}"


class CachedHttpClient:
    """HTTP client with caching, rate limiting, and circuit breaker.

    Provides robust error handling:
    - 401 errors raise AuthenticationError immediately (fatal)
    - 429 errors trigger backoff and retry
    - Transient errors retry with exponential backoff
    - Other errors are recorded by circuit breaker
    - All requests respect rate limiting, including failures
    """

    def __init__(
        self,
        *,
        session: requests.Session,
        cache: Cache,
        rate_limiter: RateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.session = session
        self.cache = cache
        self.rate_limiter = rate_limiter or RateLimiterImpl()
        self.circuit_breaker = circuit_breaker or CircuitBreakerImpl()
        self.retry_policy = retry_policy or RetryPolicyImpl()
        self.timeout_seconds = timeout_seconds

    def get_json(self, url: str, cache_key: str | None = None) -> dict[str, Any]:
        """Fetch JSON from URL with caching and rate limiting.

        Raises:
            AuthenticationError: If API returns 401 (invalid/expired key)
            CircuitBreakerOpen: If too many consecutive failures
            RateLimitError: If rate limit exceeded and backoff fails
            requests.HTTPError: For other HTTP errors
        """
        # Check cache first
        if cache_key:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        attempt = 0
        while True:
            # Check circuit breaker BEFORE making any request
            self.circuit_breaker.check()

            # Rate limit BEFORE making request
            self.rate_limiter.wait_if_needed()

            try:
                r = self.session.get(url, timeout=self.timeout_seconds)
            except self.retry_policy.retry_exceptions:
                if attempt < self.retry_policy.max_retries:
                    delay = self.retry_policy.compute_backoff(attempt)
                    time.sleep(delay)
                    attempt += 1
                    continue
                self.circuit_breaker.record_failure()
                raise
            except Exception:
                self.circuit_breaker.record_failure()
                raise

            # Check for auth errors BEFORE raise_for_status
            if r.status_code == 401:
                self.circuit_breaker.record_failure()
                details = _response_details(r)
                raise AuthenticationError(
                    f"Companies House API returned 401 Unauthorized ({details})"
                )

            if r.status_code == 403:
                self.circuit_breaker.record_failure()
                details = _response_details(r)
                raise AuthenticationError(
                    "Companies House API returned 403 Forbidden. "
                    "Your IP may be temporarily blocked due to excessive requests. "
                    f"({details})"
                )

            if r.status_code in self.retry_policy.retry_statuses:
                retry_after = _parse_retry_after(getattr(r, "headers", None))
                if attempt < self.retry_policy.max_retries:
                    delay = self.retry_policy.compute_backoff(attempt, retry_after)
                    time.sleep(delay)
                    attempt += 1
                    continue
                self.circuit_breaker.record_failure()
                if r.status_code == 429:
                    details = _response_details(r)
                    print(f"Rate limit response: {details}")
                    raise RateLimitError(retry_after or 60)
                r.raise_for_status()

            try:
                r.raise_for_status()
            except requests.HTTPError as e:
                if _is_auth_error(e):
                    self.circuit_breaker.record_failure()
                    raise AuthenticationError(f"HTTP error indicates auth failure: {e}") from e
                self.circuit_breaker.record_failure()
                raise

            try:
                data = cast(dict[str, Any], r.json())
            except Exception:
                self.circuit_breaker.record_failure()
                raise

            # Record success
            self.circuit_breaker.record_success()

            # Cache response
            if cache_key:
                self.cache.set(cache_key, data)

            return data
