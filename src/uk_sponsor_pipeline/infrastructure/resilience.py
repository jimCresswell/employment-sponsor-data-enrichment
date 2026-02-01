"""Resilience utilities for infrastructure.

Usage example:
    from uk_sponsor_pipeline.infrastructure.resilience import CircuitBreaker, RateLimiter

    rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0.2)
    circuit_breaker = CircuitBreaker(threshold=5)
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import override

import requests

from ..exceptions import CircuitBreakerOpen
from ..protocols import CircuitBreaker as CircuitBreakerProtocol
from ..protocols import RateLimiter as RateLimiterProtocol
from ..protocols import RetryPolicy as RetryPolicyProtocol


@dataclass
class RateLimiter(RateLimiterProtocol):
    """Rate limiter with minimum delay between requests.

    Enforces both per-minute limits and minimum inter-request delay.
    """

    max_rpm: int = 600
    min_delay_seconds: float = 0.2
    requests_this_minute: int = field(default=0, init=False)
    minute_start: float = field(default_factory=time.monotonic, init=False)
    last_request_time: float = field(default=0.0, init=False)

    @override
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
class CircuitBreaker(CircuitBreakerProtocol):
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

    @override
    def record_success(self) -> None:
        """Record a successful request - resets failure count."""
        self.consecutive_failures = 0
        self.state = "closed"
        self.opened_at = None
        self.open_until = None
        self.half_open_calls = 0

    @override
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

    @override
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


@dataclass
class RetryPolicy(RetryPolicyProtocol):
    """Retry policy for transient failures."""

    max_retries: int = 3
    backoff_factor: float = 0.5
    max_backoff_seconds: float = 60.0
    jitter_seconds: float = 0.1
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)
    retry_exceptions: tuple[type[Exception], ...] = (requests.Timeout, requests.ConnectionError)

    @override
    def compute_backoff(self, attempt: int, retry_after: int | None = None) -> float:
        """Compute backoff delay with optional Retry-After override."""
        base = min(self.max_backoff_seconds, self.backoff_factor * (2**attempt))
        if retry_after is not None:
            base = max(base, float(retry_after))
        if self.jitter_seconds > 0:
            base += random.uniform(0.0, self.jitter_seconds)
        return float(base)
