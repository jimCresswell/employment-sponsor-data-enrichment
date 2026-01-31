"""Comprehensive tests for infrastructure components.

Tests cover:
- RateLimiter: enforces delays between requests
- CircuitBreaker: opens after threshold failures
- CachedHttpClient: proper error handling for 401/429/failures
"""

import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from uk_sponsor_pipeline.exceptions import (
    AuthenticationError,
    CircuitBreakerOpen,
    RateLimitError,
)
from uk_sponsor_pipeline.infrastructure import (
    CachedHttpClient,
    CircuitBreaker,
    DiskCache,
    RateLimiter,
    RetryPolicy,
    _is_auth_error,
    _is_rate_limit_error,
    _parse_retry_after,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker behavior."""

    def test_starts_closed(self):
        """Circuit breaker starts in closed state."""
        cb = CircuitBreaker(threshold=3)
        assert cb.is_open is False
        assert cb.consecutive_failures == 0

    def test_stays_closed_below_threshold(self):
        """Circuit breaker stays closed when failures < threshold."""
        cb = CircuitBreaker(threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is False
        assert cb.consecutive_failures == 2

    def test_opens_at_threshold(self):
        """Circuit breaker opens when failures reach threshold."""
        cb = CircuitBreaker(threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        assert cb.consecutive_failures == 3

    def test_success_resets_failures(self):
        """Successful request resets failure count."""
        cb = CircuitBreaker(threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.consecutive_failures == 0
        assert cb.is_open is False

    def test_check_raises_when_open(self):
        """check() raises CircuitBreakerOpen when circuit is open."""
        cb = CircuitBreaker(threshold=2)
        cb.record_failure()
        cb.record_failure()
        with pytest.raises(CircuitBreakerOpen) as exc_info:
            cb.check()
        assert exc_info.value.failure_count == 2
        assert exc_info.value.threshold == 2

    def test_check_does_nothing_when_closed(self):
        """check() does not raise when circuit is closed."""
        cb = CircuitBreaker(threshold=3)
        cb.record_failure()
        cb.check()  # Should not raise

    def test_reset_clears_state(self):
        """reset() clears all state."""
        cb = CircuitBreaker(threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        cb.reset()
        assert cb.is_open is False
        assert cb.consecutive_failures == 0

    def test_half_open_allows_probe_after_timeout(self):
        """Half-open allows a probe after cooldown."""
        cb = CircuitBreaker(threshold=1, recovery_timeout_seconds=0)
        cb.record_failure()
        cb.check()  # Should allow probe
        assert cb.state == "half_open"
        cb.record_success()
        assert cb.state == "closed"

    def test_half_open_blocks_multiple_probes(self):
        """Half-open blocks extra probes beyond limit."""
        cb = CircuitBreaker(threshold=1, recovery_timeout_seconds=0, half_open_max_calls=1)
        cb.record_failure()
        cb.check()  # First probe
        with pytest.raises(CircuitBreakerOpen):
            cb.check()


class TestRateLimiter:
    """Tests for RateLimiter behavior."""

    def test_enforces_minimum_delay(self):
        """Rate limiter enforces minimum delay between requests."""
        rl = RateLimiter(max_rpm=600, min_delay_seconds=0.1)

        start = time.time()
        rl.wait_if_needed()
        rl.wait_if_needed()
        elapsed = time.time() - start

        # Second call should have waited at least 0.1s
        assert elapsed >= 0.1

    def test_tracks_requests_per_minute(self):
        """Rate limiter tracks requests in current minute."""
        rl = RateLimiter(max_rpm=5, min_delay_seconds=0)
        for _ in range(3):
            rl.wait_if_needed()
        assert rl.requests_this_minute == 3


class TestIsAuthError:
    """Tests for _is_auth_error helper."""

    def test_detects_401_status_code(self):
        """Detects 401 status code in HTTPError response."""
        response = MagicMock()
        response.status_code = 401
        error = requests.HTTPError()
        error.response = response
        assert _is_auth_error(error) is True

    def test_detects_401_in_string(self):
        """Detects '401' in error message string."""
        error = Exception("401 Client Error: Unauthorized")
        assert _is_auth_error(error) is True

    def test_detects_unauthorized_in_string(self):
        """Detects 'Unauthorized' in error message string."""
        error = Exception("Request was Unauthorized by server")
        assert _is_auth_error(error) is True

    def test_returns_false_for_other_errors(self):
        """Returns False for non-auth errors."""
        error = Exception("Connection timeout")
        assert _is_auth_error(error) is False


class TestIsRateLimitError:
    """Tests for _is_rate_limit_error helper."""

    def test_detects_429_status_code(self):
        """Detects 429 status code in HTTPError response."""
        response = MagicMock()
        response.status_code = 429
        error = requests.HTTPError()
        error.response = response
        assert _is_rate_limit_error(error) is True

    def test_detects_429_in_string(self):
        """Detects '429' in error message string."""
        error = Exception("429 Too Many Requests")
        assert _is_rate_limit_error(error) is True

    def test_returns_false_for_other_errors(self):
        """Returns False for non-rate-limit errors."""
        error = Exception("Connection timeout")
        assert _is_rate_limit_error(error) is False


class TestParseRetryAfter:
    """Tests for Retry-After parsing."""

    def test_numeric_seconds(self):
        assert _parse_retry_after({"Retry-After": "12"}) == 12

    def test_http_date(self):
        future = datetime.now(UTC) + timedelta(seconds=30)
        header = format_datetime(future)
        value = _parse_retry_after({"Retry-After": header})
        assert value is not None
        assert 0 <= value <= 30

    def test_invalid_header_returns_none(self):
        assert _parse_retry_after({"Retry-After": "not-a-date"}) is None


class TestRetryPolicy:
    """Tests for RetryPolicy backoff behavior."""

    def test_retry_after_overrides_backoff(self):
        policy = RetryPolicy(max_retries=1, backoff_factor=0.1, jitter_seconds=0)
        delay = policy.compute_backoff(attempt=0, retry_after=5)
        assert delay >= 5


class TestCachedHttpClient:
    """Tests for CachedHttpClient error handling."""

    def _make_client(self, session=None, cache=None, retry_policy=None) -> CachedHttpClient:
        """Create a CachedHttpClient with mocks."""
        if session is None:
            session = MagicMock(spec=requests.Session)
        if cache is None:
            cache = MagicMock()
            cache.get.return_value = None  # Cache miss by default
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=3)
        retry_policy = retry_policy or RetryPolicy(
            max_retries=0, backoff_factor=0, jitter_seconds=0
        )
        return CachedHttpClient(
            session=session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
        )

    def test_returns_cached_response(self):
        """Returns cached response without making HTTP request."""
        cache = MagicMock()
        cache.get.return_value = {"cached": True}
        session = MagicMock(spec=requests.Session)
        client = self._make_client(session=session, cache=cache)

        result = client.get_json("https://example.com", "cache_key")

        assert result == {"cached": True}
        session.get.assert_not_called()

    def test_raises_auth_error_on_401(self):
        """Raises AuthenticationError immediately on 401 response."""
        session = MagicMock(spec=requests.Session)
        response = MagicMock()
        response.status_code = 401
        session.get.return_value = response

        client = self._make_client(session=session)

        with pytest.raises(AuthenticationError):
            client.get_json("https://example.com", None)

        # Should only make ONE request before failing
        assert session.get.call_count == 1

    def test_raises_auth_error_on_403(self):
        """Raises AuthenticationError immediately on 403 Forbidden (IP ban)."""
        session = MagicMock(spec=requests.Session)
        response = MagicMock()
        response.status_code = 403
        session.get.return_value = response

        client = self._make_client(session=session)

        with pytest.raises(AuthenticationError) as exc_info:
            client.get_json("https://example.com", None)

        # Should only make ONE request before failing
        assert session.get.call_count == 1
        # Error message should mention 403
        assert "403" in str(exc_info.value)

    def test_circuit_breaker_opens_on_repeated_401(self):
        """Circuit breaker opens after repeated 401 errors."""
        session = MagicMock(spec=requests.Session)
        response = MagicMock()
        response.status_code = 401
        session.get.return_value = response

        cache = MagicMock()
        cache.get.return_value = None
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=2)
        client = CachedHttpClient(
            session=session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
            retry_policy=RetryPolicy(max_retries=0, backoff_factor=0, jitter_seconds=0),
        )

        # First 401
        with pytest.raises(AuthenticationError):
            client.get_json("https://example.com/1", None)

        # Second 401 - circuit should open
        with pytest.raises(AuthenticationError):
            client.get_json("https://example.com/2", None)

        # Third call - circuit breaker should block WITHOUT making request
        with pytest.raises(CircuitBreakerOpen):
            client.get_json("https://example.com/3", None)

        # Only 2 requests made - third was blocked by circuit breaker
        assert session.get.call_count == 2

    def test_records_failure_on_http_error(self):
        """Records failure in circuit breaker for HTTP errors."""
        session = MagicMock(spec=requests.Session)
        response = MagicMock()
        response.status_code = 500
        response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        session.get.return_value = response

        cache = MagicMock()
        cache.get.return_value = None
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=3)
        client = CachedHttpClient(
            session=session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
            retry_policy=RetryPolicy(max_retries=0, backoff_factor=0, jitter_seconds=0),
        )

        with pytest.raises(requests.HTTPError):
            client.get_json("https://example.com", None)

        assert circuit_breaker.consecutive_failures == 1

    def test_success_resets_circuit_breaker(self):
        """Successful request resets circuit breaker failures."""
        session = MagicMock(spec=requests.Session)
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"success": True}
        session.get.return_value = response

        cache = MagicMock()
        cache.get.return_value = None
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=3)
        circuit_breaker.consecutive_failures = 2  # Pre-set some failures
        client = CachedHttpClient(
            session=session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
            retry_policy=RetryPolicy(max_retries=0, backoff_factor=0, jitter_seconds=0),
        )

        client.get_json("https://example.com", None)

        assert circuit_breaker.consecutive_failures == 0

    def test_caches_successful_response(self):
        """Caches successful response."""
        session = MagicMock(spec=requests.Session)
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"data": "test"}
        session.get.return_value = response

        cache = MagicMock()
        cache.get.return_value = None
        client = self._make_client(session=session, cache=cache)

        client.get_json("https://example.com", "my_cache_key")

        cache.set.assert_called_once_with("my_cache_key", {"data": "test"})

    def test_retries_on_429_then_success(self):
        """Retries on 429 and succeeds on next attempt."""
        session = MagicMock(spec=requests.Session)
        resp1 = MagicMock()
        resp1.status_code = 429
        resp1.headers = {"Retry-After": "5"}
        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.json.return_value = {"ok": True}
        session.get.side_effect = [resp1, resp2]

        cache = MagicMock()
        cache.get.return_value = None
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=3)
        retry_policy = RetryPolicy(max_retries=1, backoff_factor=0, jitter_seconds=0)

        client = CachedHttpClient(
            session=session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
        )

        with patch("uk_sponsor_pipeline.infrastructure.time.sleep") as sleep_mock:
            result = client.get_json("https://example.com", None)

        assert result == {"ok": True}
        assert session.get.call_count == 2
        sleep_mock.assert_called()

    def test_rate_limit_error_after_retries_exhausted(self):
        """Raises RateLimitError after exhausting retries for 429."""
        session = MagicMock(spec=requests.Session)
        resp1 = MagicMock()
        resp1.status_code = 429
        resp1.headers = {"Retry-After": "3"}
        resp2 = MagicMock()
        resp2.status_code = 429
        resp2.headers = {"Retry-After": "3"}
        session.get.side_effect = [resp1, resp2]

        cache = MagicMock()
        cache.get.return_value = None
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=3)
        retry_policy = RetryPolicy(max_retries=1, backoff_factor=0, jitter_seconds=0)

        client = CachedHttpClient(
            session=session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
        )

        with patch("uk_sponsor_pipeline.infrastructure.time.sleep"):
            with pytest.raises(RateLimitError) as exc_info:
                client.get_json("https://example.com", None)

        assert exc_info.value.retry_after == 3
        assert session.get.call_count == 2

    def test_retries_on_timeout_then_success(self):
        """Retries on timeout exception and succeeds."""
        session = MagicMock(spec=requests.Session)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"ok": True}
        session.get.side_effect = [requests.Timeout("timeout"), resp]

        cache = MagicMock()
        cache.get.return_value = None
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=3)
        retry_policy = RetryPolicy(max_retries=1, backoff_factor=0, jitter_seconds=0)

        client = CachedHttpClient(
            session=session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
        )

        with patch("uk_sponsor_pipeline.infrastructure.time.sleep"):
            result = client.get_json("https://example.com", None)

        assert result == {"ok": True}
        assert session.get.call_count == 2


class TestDiskCache:
    """Tests for DiskCache."""

    def test_get_returns_none_for_missing_key(self, tmp_path):
        """get() returns None for missing key."""
        cache = DiskCache(tmp_path / "cache")
        assert cache.get("nonexistent") is None

    def test_set_and_get_roundtrip(self, tmp_path):
        """set() and get() roundtrip works correctly."""
        cache = DiskCache(tmp_path / "cache")
        cache.set("mykey", {"test": "value", "number": 42})
        result = cache.get("mykey")
        assert result == {"test": "value", "number": 42}

    def test_has_returns_correct_values(self, tmp_path):
        """has() returns correct boolean values."""
        cache = DiskCache(tmp_path / "cache")
        assert cache.has("missing") is False
        cache.set("exists", {"data": True})
        assert cache.has("exists") is True
