"""HTTP client implementations for infrastructure.

Usage example:
    import requests
    from pathlib import Path

    from uk_sponsor_pipeline.infrastructure.io.filesystem import DiskCache
    from uk_sponsor_pipeline.infrastructure.io.http import CachedHttpClient
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
from pathlib import Path
from typing import override

import requests
from requests.auth import HTTPBasicAuth

from ...exceptions import AuthenticationError, JsonObjectExpectedError, RateLimitError
from ...io_validation import IncomingDataError, validate_as, validate_json_as
from ...observability import get_logger
from ...protocols import Cache, CircuitBreaker, HttpClient, HttpSession, RateLimiter, RetryPolicy
from ..resilience import CircuitBreaker as CircuitBreakerImpl
from ..resilience import RateLimiter as RateLimiterImpl
from ..resilience import RetryPolicy as RetryPolicyImpl
from .filesystem import DiskCache

logger = get_logger("uk_sponsor_pipeline.infrastructure.http")


def build_companies_house_client(
    *,
    api_key: str,
    cache_dir: str | Path,
    max_rpm: int,
    min_delay_seconds: float,
    circuit_breaker_threshold: int,
    circuit_breaker_timeout_seconds: float,
    max_retries: int,
    backoff_factor: float,
    max_backoff_seconds: float,
    jitter_seconds: float,
    timeout_seconds: float,
) -> CachedHttpClient:
    session = requests.Session()
    session.auth = HTTPBasicAuth(api_key, "")
    cache = DiskCache(Path(cache_dir))
    rate_limiter = RateLimiterImpl(max_rpm=max_rpm, min_delay_seconds=min_delay_seconds)
    circuit_breaker = CircuitBreakerImpl(
        threshold=circuit_breaker_threshold,
        recovery_timeout_seconds=circuit_breaker_timeout_seconds,
    )
    retry_policy = RetryPolicyImpl(
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        max_backoff_seconds=max_backoff_seconds,
        jitter_seconds=jitter_seconds,
    )
    return CachedHttpClient(
        session=session,
        cache=cache,
        rate_limiter=rate_limiter,
        circuit_breaker=circuit_breaker,
        retry_policy=retry_policy,
        timeout_seconds=timeout_seconds,
    )


def is_auth_error(error: Exception) -> bool:
    """Check if an exception indicates an authentication error."""
    if isinstance(error, requests.HTTPError):
        if error.response is not None and error.response.status_code == 401:
            return True
    error_str = str(error).lower()
    return "401" in error_str or "unauthorized" in error_str or "unauthorised" in error_str


def is_rate_limit_error(error: Exception) -> bool:
    """Check if an exception indicates a rate limit error."""
    if isinstance(error, requests.HTTPError):
        if error.response is not None and error.response.status_code == 429:
            return True
    error_str = str(error).lower()
    return "429" in error_str or "rate limit" in error_str or "too many requests" in error_str


def parse_retry_after(headers: Mapping[str, str] | None) -> int | None:
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
    except (AttributeError, OverflowError, TypeError, ValueError):
        return None


def _response_details(response: requests.Response) -> str:
    """Return a compact status/body summary for error reporting."""
    try:
        body = response.text
    except (UnicodeDecodeError, ValueError, requests.RequestException):
        body = "<unreadable>"
    body = " ".join(body.split())
    if len(body) > 300:
        body = body[:300] + "..."
    return f"status={response.status_code}, body={body}"


class CachedHttpClient(HttpClient):
    """HTTP client with caching, rate limiting, and circuit breaker.

    Provides robust error handling:
    - 401 errors raise AuthenticationError immediately (fatal)
    - 429 errors trigger backoff and retry
    - Transient errors retry with exponential backoff
    - Other request failures are recorded by circuit breaker
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

    @override
    def get_json(self, url: str, cache_key: str | None = None) -> dict[str, object]:
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
            except requests.RequestException:
                self.circuit_breaker.record_failure()
                raise

            # Check for auth errors BEFORE raise_for_status
            if r.status_code == 401:
                self.circuit_breaker.record_failure()
                details = _response_details(r)
                raise AuthenticationError.for_status_401(details)

            if r.status_code == 403:
                self.circuit_breaker.record_failure()
                details = _response_details(r)
                raise AuthenticationError.for_status_403(details)

            if r.status_code in self.retry_policy.retry_statuses:
                retry_after = parse_retry_after(getattr(r, "headers", None))
                if attempt < self.retry_policy.max_retries:
                    delay = self.retry_policy.compute_backoff(attempt, retry_after)
                    time.sleep(delay)
                    attempt += 1
                    continue
                self.circuit_breaker.record_failure()
                if r.status_code == 429:
                    details = _response_details(r)
                    logger.warning("Rate limit response: %s", details)
                    raise RateLimitError(retry_after or 60)
                r.raise_for_status()

            try:
                r.raise_for_status()
            except requests.HTTPError as e:
                if is_auth_error(e):
                    self.circuit_breaker.record_failure()
                    raise AuthenticationError.for_http_error(e) from e
                if is_rate_limit_error(e):
                    self.circuit_breaker.record_failure()
                    raise RateLimitError(60) from e
                self.circuit_breaker.record_failure()
                raise

            try:
                data = validate_json_as(dict[str, object], r.text)
            except IncomingDataError:
                try:
                    payload: object = r.json()
                except (TypeError, ValueError) as exc:
                    raise JsonObjectExpectedError.for_companies_house_response() from exc
                try:
                    data = validate_as(dict[str, object], payload)
                except IncomingDataError as exc:
                    raise JsonObjectExpectedError.for_companies_house_response() from exc

            # Record success
            self.circuit_breaker.record_success()

            # Cache response
            if cache_key:
                self.cache.set(cache_key, data)

            return data


class RequestsSession(HttpSession):
    """Requests-backed session for non-JSON HTTP fetching."""

    def __init__(self, *, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()

    @override
    def get_text(self, url: str, *, timeout_seconds: float) -> str:
        response = self._session.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        return response.text

    @override
    def get_bytes(self, url: str, *, timeout_seconds: float) -> bytes:
        response = self._session.get(url, timeout=timeout_seconds, stream=True)
        response.raise_for_status()
        return response.content
