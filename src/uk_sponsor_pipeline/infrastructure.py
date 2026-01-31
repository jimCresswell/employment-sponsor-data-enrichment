"""Concrete implementations of protocol interfaces.

These provide the production implementations that will be used by default,
while tests can substitute mock implementations.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd
import requests

from .exceptions import AuthenticationError, CircuitBreakerOpen, RateLimitError
from .protocols import Cache


@dataclass
class DiskCache:
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


@dataclass
class RateLimiter:
    """Rate limiter with minimum delay between requests.

    Enforces both per-minute limits and minimum inter-request delay.
    """

    max_rpm: int = 600
    min_delay_seconds: float = 0.2
    requests_this_minute: int = field(default=0, init=False)
    minute_start: float = field(default_factory=time.monotonic, init=False)
    last_request_time: float = field(default=0.0, init=False)

    def wait_if_needed(self) -> None:
        """Block if we've exceeded the rate limit or need inter-request delay."""
        now = time.monotonic()

        # Always enforce minimum delay between requests
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_delay_seconds:
            time.sleep(self.min_delay_seconds - time_since_last)
            now = time.monotonic()

        # Check per-minute limit
        if self.max_rpm <= 0:
            self.last_request_time = now
            return
        if now - self.minute_start >= 60:
            # Reset for new minute
            self.requests_this_minute = 0
            self.minute_start = now
        elif self.requests_this_minute >= self.max_rpm:
            # Wait until the minute is over
            sleep_time = 60 - (now - self.minute_start) + 0.1
            time.sleep(sleep_time)
            self.requests_this_minute = 0
            self.minute_start = time.monotonic()

        self.requests_this_minute += 1
        self.last_request_time = time.monotonic()


@dataclass
class CircuitBreaker:
    """Circuit breaker to prevent repeated failures from causing API bans.

    Opens after `threshold` consecutive failures. Must be manually reset.
    """

    threshold: int = 5
    recovery_timeout_seconds: float = 60.0
    half_open_max_calls: int = 1
    consecutive_failures: int = field(default=0, init=False)
    state: str = field(default="closed", init=False)  # closed | open | half_open
    opened_at: float | None = field(default=None, init=False)
    open_until: float | None = field(default=None, init=False)
    half_open_calls: int = field(default=0, init=False)

    @property
    def is_open(self) -> bool:
        return self.state == "open"

    def record_success(self) -> None:
        """Record a successful request - resets failure count."""
        self.consecutive_failures = 0
        self.state = "closed"
        self.opened_at = None
        self.open_until = None
        self.half_open_calls = 0

    def record_failure(self) -> None:
        """Record a failed request - may open circuit."""
        now = time.monotonic()
        if self.state == "half_open":
            # Fail fast in half-open state
            self.consecutive_failures += 1
            self._open(now)
            return

        self.consecutive_failures += 1
        if self.consecutive_failures >= self.threshold:
            self._open(now)

    def check(self) -> None:
        """Check if circuit is open - raises if so."""
        if self.state == "open":
            now = time.monotonic()
            if self.open_until is not None and now >= self.open_until:
                # Allow a limited probe attempt
                self.state = "half_open"
                self.half_open_calls = 0
            else:
                raise CircuitBreakerOpen(self.consecutive_failures, self.threshold)

        if self.state == "half_open":
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpen(self.consecutive_failures, self.threshold)
            self.half_open_calls += 1

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self.consecutive_failures = 0
        self.state = "closed"
        self.opened_at = None
        self.open_until = None
        self.half_open_calls = 0

    def _open(self, now: float) -> None:
        self.state = "open"
        self.opened_at = now
        self.open_until = now + self.recovery_timeout_seconds
        self.half_open_calls = 0


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


@dataclass
class RetryPolicy:
    """Retry policy for transient failures."""

    max_retries: int = 3
    backoff_factor: float = 0.5
    max_backoff_seconds: float = 60.0
    jitter_seconds: float = 0.1
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)
    retry_exceptions: tuple[type[Exception], ...] = (requests.Timeout, requests.ConnectionError)

    def compute_backoff(self, attempt: int, retry_after: int | None = None) -> float:
        """Compute backoff delay with optional Retry-After override."""
        base = min(self.max_backoff_seconds, self.backoff_factor * (2**attempt))
        if retry_after is not None:
            base = max(base, float(retry_after))
        if self.jitter_seconds > 0:
            base += random.uniform(0.0, self.jitter_seconds)
        return float(base)


@dataclass
class CachedHttpClient:
    """HTTP client with caching, rate limiting, and circuit breaker.

    Provides robust error handling:
    - 401 errors raise AuthenticationError immediately (fatal)
    - 429 errors trigger backoff and retry
    - Transient errors retry with exponential backoff
    - Other errors are recorded by circuit breaker
    - All requests respect rate limiting, including failures
    """

    session: requests.Session
    cache: Cache
    rate_limiter: RateLimiter
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    timeout_seconds: float = 30.0

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
                raise AuthenticationError("Companies House API returned 401 Unauthorized")

            if r.status_code == 403:
                self.circuit_breaker.record_failure()
                raise AuthenticationError(
                    "Companies House API returned 403 Forbidden. "
                    "Your IP may be temporarily blocked due to excessive requests."
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


@dataclass
class LocalFileSystem:
    """Local filesystem implementation."""

    def read_csv(self, path: Path) -> pd.DataFrame:
        return pd.read_csv(path, dtype=str).fillna("")

    def write_csv(self, df: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)

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
