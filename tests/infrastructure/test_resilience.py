"""Tests for resilience infrastructure components."""

import time

import pytest

from uk_sponsor_pipeline.exceptions import CircuitBreakerOpen
from uk_sponsor_pipeline.infrastructure import CircuitBreaker, RateLimiter, RetryPolicy


class TestCircuitBreaker:
    """Tests for CircuitBreaker behaviour."""

    def test_starts_closed(self) -> None:
        """Circuit breaker starts in closed state."""
        cb = CircuitBreaker(threshold=3)
        assert cb.is_open is False
        assert cb.consecutive_failures == 0

    def test_stays_closed_below_threshold(self) -> None:
        """Circuit breaker stays closed when failures < threshold."""
        cb = CircuitBreaker(threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is False
        assert cb.consecutive_failures == 2

    def test_opens_at_threshold(self) -> None:
        """Circuit breaker opens when failures reach threshold."""
        cb = CircuitBreaker(threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        assert cb.consecutive_failures == 3

    def test_success_resets_failures(self) -> None:
        """Successful request resets failure count."""
        cb = CircuitBreaker(threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.consecutive_failures == 0
        assert cb.is_open is False

    def test_check_raises_when_open(self) -> None:
        """check() raises CircuitBreakerOpen when circuit is open."""
        cb = CircuitBreaker(threshold=2)
        cb.record_failure()
        cb.record_failure()
        with pytest.raises(CircuitBreakerOpen) as exc_info:
            cb.check()
        assert exc_info.value.failure_count == 2
        assert exc_info.value.threshold == 2

    def test_check_does_nothing_when_closed(self) -> None:
        """check() does not raise when circuit is closed."""
        cb = CircuitBreaker(threshold=3)
        cb.record_failure()
        cb.check()  # Should not raise

    def test_reset_clears_state(self) -> None:
        """reset() clears all state."""
        cb = CircuitBreaker(threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        cb.reset()
        assert cb.is_open is False
        assert cb.consecutive_failures == 0

    def test_half_open_allows_probe_after_timeout(self) -> None:
        """Half-open allows a probe after cooldown."""
        cb = CircuitBreaker(threshold=1, recovery_timeout_seconds=0)
        cb.record_failure()
        cb.check()  # Should allow probe
        assert cb.state == "half_open"
        cb.record_success()
        assert cb.state == "closed"

    def test_half_open_blocks_multiple_probes(self) -> None:
        """Half-open blocks extra probes beyond limit."""
        cb = CircuitBreaker(threshold=1, recovery_timeout_seconds=0, half_open_max_calls=1)
        cb.record_failure()
        cb.check()  # First probe
        with pytest.raises(CircuitBreakerOpen):
            cb.check()


class TestRateLimiter:
    """Tests for RateLimiter behaviour."""

    def test_enforces_minimum_delay(self) -> None:
        """Rate limiter enforces minimum delay between requests."""
        rl = RateLimiter(max_rpm=600, min_delay_seconds=0.1)

        start = time.time()
        rl.wait_if_needed()
        rl.wait_if_needed()
        elapsed = time.time() - start

        # Second call should have waited at least 0.1s
        assert elapsed >= 0.1

    def test_tracks_requests_per_minute(self) -> None:
        """Rate limiter tracks requests in current minute."""
        rl = RateLimiter(max_rpm=5, min_delay_seconds=0)
        for _ in range(3):
            rl.wait_if_needed()
        assert rl.requests_this_minute == 3


class TestRetryPolicy:
    """Tests for RetryPolicy backoff behaviour."""

    def test_retry_after_overrides_backoff(self) -> None:
        policy = RetryPolicy(max_retries=1, backoff_factor=0.1, jitter_seconds=0)
        delay = policy.compute_backoff(attempt=0, retry_after=5)
        assert delay >= 5
