"""Concrete implementations of protocol interfaces.

These provide the production implementations that will be used by default,
while tests can substitute mock implementations.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from .exceptions import AuthenticationError, CircuitBreakerOpen, RateLimitError
from .protocols import Cache, FileSystem, HttpClient


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
            return json.loads(p.read_text(encoding="utf-8"))
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
    minute_start: float = field(default_factory=time.time, init=False)
    last_request_time: float = field(default=0.0, init=False)

    def wait_if_needed(self) -> None:
        """Block if we've exceeded the rate limit or need inter-request delay."""
        now = time.time()

        # Always enforce minimum delay between requests
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_delay_seconds:
            time.sleep(self.min_delay_seconds - time_since_last)
            now = time.time()

        # Check per-minute limit
        if now - self.minute_start >= 60:
            # Reset for new minute
            self.requests_this_minute = 0
            self.minute_start = now
        elif self.requests_this_minute >= self.max_rpm:
            # Wait until the minute is over
            sleep_time = 60 - (now - self.minute_start) + 0.1
            time.sleep(sleep_time)
            self.requests_this_minute = 0
            self.minute_start = time.time()

        self.requests_this_minute += 1
        self.last_request_time = time.time()


@dataclass
class CircuitBreaker:
    """Circuit breaker to prevent repeated failures from causing API bans.

    Opens after `threshold` consecutive failures. Must be manually reset.
    """

    threshold: int = 5
    consecutive_failures: int = field(default=0, init=False)
    is_open: bool = field(default=False, init=False)

    def record_success(self) -> None:
        """Record a successful request - resets failure count."""
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        """Record a failed request - may open circuit."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.threshold:
            self.is_open = True

    def check(self) -> None:
        """Check if circuit is open - raises if so."""
        if self.is_open:
            raise CircuitBreakerOpen(self.consecutive_failures, self.threshold)

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self.consecutive_failures = 0
        self.is_open = False


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


@dataclass
class CachedHttpClient:
    """HTTP client with caching, rate limiting, and circuit breaker.

    Provides robust error handling:
    - 401 errors raise AuthenticationError immediately (fatal)
    - 429 errors trigger backoff and retry
    - Other errors are recorded by circuit breaker
    - All requests respect rate limiting, including failures
    """

    session: requests.Session
    cache: Cache
    rate_limiter: RateLimiter
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    sleep_seconds: float = 0.2

    def get_json(self, url: str, cache_key: str | None = None) -> dict[str, Any]:
        """Fetch JSON from URL with caching and rate limiting.

        Raises:
            AuthenticationError: If API returns 401 (invalid/expired key)
            CircuitBreakerOpen: If too many consecutive failures
            RateLimitError: If rate limit exceeded and backoff fails
            requests.HTTPError: For other HTTP errors
        """
        # Check circuit breaker BEFORE making any request
        self.circuit_breaker.check()

        # Check cache first
        if cache_key:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # Rate limit BEFORE making request
        self.rate_limiter.wait_if_needed()

        try:
            r = self.session.get(url, timeout=30)

            # Check for auth errors BEFORE raise_for_status
            if r.status_code == 401:
                self.circuit_breaker.record_failure()
                raise AuthenticationError("Companies House API returned 401 Unauthorized")

            # Check for 403 Forbidden - indicates IP ban or blocked access
            if r.status_code == 403:
                self.circuit_breaker.record_failure()
                raise AuthenticationError(
                    "Companies House API returned 403 Forbidden. "
                    "Your IP may be temporarily blocked due to excessive requests."
                )

            # Check for rate limit errors - backoff and retry once
            if r.status_code == 429:
                retry_after = int(r.headers.get("Retry-After", 60))
                time.sleep(min(retry_after, 120))  # Cap at 2 minutes
                self.rate_limiter.wait_if_needed()

                r = self.session.get(url, timeout=30)
                if r.status_code == 401:
                    self.circuit_breaker.record_failure()
                    raise AuthenticationError("Companies House API returned 401 Unauthorized")
                if r.status_code == 403:
                    self.circuit_breaker.record_failure()
                    raise AuthenticationError(
                        "Companies House API returned 403 Forbidden after retry."
                    )
                if r.status_code == 429:
                    self.circuit_breaker.record_failure()
                    raise RateLimitError(retry_after)

            r.raise_for_status()
            data = r.json()

            # Record success
            self.circuit_breaker.record_success()

            # Cache response
            if cache_key:
                self.cache.set(cache_key, data)

            return data

        except AuthenticationError:
            # Re-raise auth errors - they're fatal
            raise
        except CircuitBreakerOpen:
            # Re-raise circuit breaker - it's fatal
            raise
        except RateLimitError:
            # Re-raise rate limit errors after recording
            self.circuit_breaker.record_failure()
            raise
        except requests.HTTPError as e:
            # Check if it's really an auth error
            if _is_auth_error(e):
                self.circuit_breaker.record_failure()
                raise AuthenticationError(f"HTTP error indicates auth failure: {e}") from e
            # Record failure and re-raise
            self.circuit_breaker.record_failure()
            raise
        except Exception as e:
            # Record all other failures
            self.circuit_breaker.record_failure()
            raise


@dataclass
class LocalFileSystem:
    """Local filesystem implementation."""

    def read_csv(self, path: Path) -> pd.DataFrame:
        return pd.read_csv(path, dtype=str).fillna("")

    def write_csv(self, df: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)

    def read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def write_json(self, data: dict[str, Any], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def write_text(self, content: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def exists(self, path: Path) -> bool:
        return path.exists()

    def mkdir(self, path: Path, parents: bool = True) -> None:
        path.mkdir(parents=parents, exist_ok=True)

    def list_files(self, path: Path, pattern: str = "*") -> list[Path]:
        return sorted(path.glob(pattern))
