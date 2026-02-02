"""Tests for HTTP infrastructure components."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import MagicMock, patch

import pytest
import requests
from requests.auth import HTTPBasicAuth

from uk_sponsor_pipeline.exceptions import (
    AuthenticationError,
    CircuitBreakerOpen,
    RateLimitError,
)
from uk_sponsor_pipeline.infrastructure import (
    CachedHttpClient,
    CircuitBreaker,
    RateLimiter,
    RetryPolicy,
    is_auth_error,
    is_rate_limit_error,
    parse_retry_after,
)
from uk_sponsor_pipeline.protocols import Cache


class TestCachedHttpClientAuth:
    """Tests for CachedHttpClient auth header passing."""

    def test_session_headers_are_used(self) -> None:
        """Verify that session.get is invoked when using CachedHttpClient."""
        # Create a mock session
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_session.get.return_value = mock_response

        # Add auth to session
        api_key = "test-key-123"
        mock_session.auth = HTTPBasicAuth(api_key, "")

        # Create cache, rate limiter, and circuit breaker
        cache = MagicMock()
        cache.get.return_value = None  # Cache miss
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=5)

        client = CachedHttpClient(
            session=mock_session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
        )

        # Make a request
        client.get_json("https://api.example.com/test", "cache_key")

        # Verify session.get was called (which uses session headers)
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args
        assert call_args[0][0] == "https://api.example.com/test"


class TestHttpClientWithErrors:
    """Tests for HTTP client error handling."""

    def test_401_raises_auth_error_immediately(self) -> None:
        """Verify that 401 errors raise AuthenticationError immediately."""
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_session.get.return_value = mock_response

        cache = MagicMock()
        cache.get.return_value = None
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=5)

        client = CachedHttpClient(
            session=mock_session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
        )

        # Should raise AuthenticationError, not HTTPError
        with pytest.raises(AuthenticationError):
            client.get_json("https://api.example.com/test", "cache_key")

        # Should only make ONE request
        assert mock_session.get.call_count == 1

    def test_403_raises_auth_error_immediately(self) -> None:
        """Verify that 403 Forbidden (IP ban) raises AuthenticationError immediately."""
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_session.get.return_value = mock_response

        cache = MagicMock()
        cache.get.return_value = None
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=5)

        client = CachedHttpClient(
            session=mock_session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
        )

        # Should raise AuthenticationError, not HTTPError
        with pytest.raises(AuthenticationError) as exc_info:
            client.get_json("https://api.example.com/test", "cache_key")

        # Should only make ONE request
        assert mock_session.get.call_count == 1
        # Error message should mention 403
        assert "403" in str(exc_info.value)


class TestIsAuthError:
    """Tests for is_auth_error helper."""

    def test_detects_401_status_code(self) -> None:
        """Detects 401 status code in HTTPError response."""
        response = MagicMock()
        response.status_code = 401
        error = requests.HTTPError()
        error.response = response
        assert is_auth_error(error) is True

    def test_detects_401_in_string(self) -> None:
        """Detects '401' in error message string."""
        error = Exception("401 Client Error: Unauthorized")
        assert is_auth_error(error) is True

    def test_detects_unauthorised_in_string(self) -> None:
        """Detects 'Unauthorised' in error message string."""
        error = Exception("Request was Unauthorized by server")
        assert is_auth_error(error) is True

    def test_returns_false_for_other_errors(self) -> None:
        """Returns False for non-auth errors."""
        error = Exception("Connection timeout")
        assert is_auth_error(error) is False


class TestIsRateLimitError:
    """Tests for is_rate_limit_error helper."""

    def test_detects_429_status_code(self) -> None:
        """Detects 429 status code in HTTPError response."""
        response = MagicMock()
        response.status_code = 429
        error = requests.HTTPError()
        error.response = response
        assert is_rate_limit_error(error) is True

    def test_detects_429_in_string(self) -> None:
        """Detects '429' in error message string."""
        error = Exception("429 Too Many Requests")
        assert is_rate_limit_error(error) is True

    def test_returns_false_for_other_errors(self) -> None:
        """Returns False for non-rate-limit errors."""
        error = Exception("Connection timeout")
        assert is_rate_limit_error(error) is False


class TestParseRetryAfter:
    """Tests for Retry-After parsing."""

    def test_numeric_seconds(self) -> None:
        assert parse_retry_after({"Retry-After": "12"}) == 12

    def test_http_date(self) -> None:
        future = datetime.now(UTC) + timedelta(seconds=30)
        header = format_datetime(future)
        value = parse_retry_after({"Retry-After": header})
        assert value is not None
        assert 0 <= value <= 30

    def test_invalid_header_returns_none(self) -> None:
        assert parse_retry_after({"Retry-After": "not-a-date"}) is None


class TestCachedHttpClient:
    """Tests for CachedHttpClient error handling."""

    def _make_client(
        self,
        session: requests.Session | None = None,
        cache: Cache | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> CachedHttpClient:
        """Create a CachedHttpClient with mocks."""
        if session is None:
            session = MagicMock(spec=requests.Session)
        if cache is None:
            cache = MagicMock(spec=Cache)
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

    def test_returns_cached_response(self) -> None:
        """Returns cached response without making HTTP request."""
        cache = MagicMock()
        cache.get.return_value = {"cached": True}
        session = MagicMock(spec=requests.Session)
        client = self._make_client(session=session, cache=cache)

        result = client.get_json("https://example.com", "cache_key")

        assert result == {"cached": True}
        session.get.assert_not_called()

    def test_raises_auth_error_on_401(self) -> None:
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

    def test_raises_auth_error_on_403(self) -> None:
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

    def test_circuit_breaker_opens_on_repeated_401(self) -> None:
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

    def test_records_failure_on_http_error(self) -> None:
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

    def test_non_network_error_does_not_record_failure(self) -> None:
        """Does not record circuit breaker failures for non-network errors."""
        session = MagicMock(spec=requests.Session)
        response = MagicMock()
        response.status_code = 200
        response.text = "not-json"
        response.raise_for_status.return_value = None
        response.json.return_value = ["not", "an", "object"]
        session.get.return_value = response

        cache = MagicMock()
        cache.get.return_value = None
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=3)
        retry_policy = RetryPolicy(max_retries=0, backoff_factor=0, jitter_seconds=0)
        client = CachedHttpClient(
            session=session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
        )

        with pytest.raises(RuntimeError):
            client.get_json("https://example.com", None)

        assert circuit_breaker.consecutive_failures == 0

    def test_success_resets_circuit_breaker(self) -> None:
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

    def test_caches_successful_response(self) -> None:
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

    def test_retries_on_429_then_success(self) -> None:
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

        with patch("uk_sponsor_pipeline.infrastructure.io.http.time.sleep") as sleep_mock:
            result = client.get_json("https://example.com", None)

        assert result == {"ok": True}
        assert session.get.call_count == 2
        sleep_mock.assert_called()

    def test_rate_limit_error_after_retries_exhausted(self) -> None:
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

        with patch("uk_sponsor_pipeline.infrastructure.io.http.time.sleep"):
            with pytest.raises(RateLimitError) as exc_info:
                client.get_json("https://example.com", None)

        assert exc_info.value.retry_after == 3
        assert session.get.call_count == 2

    def test_retries_on_timeout_then_success(self) -> None:
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

        with patch("uk_sponsor_pipeline.infrastructure.io.http.time.sleep"):
            result = client.get_json("https://example.com", None)

        assert result == {"ok": True}
        assert session.get.call_count == 2
