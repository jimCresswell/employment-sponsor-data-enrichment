"""Resilience fakes for tests."""

from __future__ import annotations

from dataclasses import dataclass

from uk_sponsor_pipeline.exceptions import CircuitBreakerOpen


@dataclass
class FakeRateLimiter:
    """Fake rate limiter that records calls."""

    calls: int = 0

    def wait_if_needed(self) -> None:
        self.calls += 1


@dataclass
class FakeCircuitBreaker:
    """Fake circuit breaker with optional forced open state."""

    is_open: bool = False
    failure_count: int = 0
    threshold: int = 1
    check_calls: int = 0
    record_success_calls: int = 0
    record_failure_calls: int = 0

    def check(self) -> None:
        self.check_calls += 1
        if self.is_open:
            raise CircuitBreakerOpen(self.failure_count, self.threshold)

    def record_success(self) -> None:
        self.record_success_calls += 1
        self.failure_count = 0

    def record_failure(self) -> None:
        self.record_failure_calls += 1
        self.failure_count += 1
