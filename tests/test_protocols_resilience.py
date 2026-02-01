"""Protocol conformance tests for resilience primitives."""

from tests.fakes import FakeCircuitBreaker, FakeRateLimiter
from uk_sponsor_pipeline.infrastructure import CircuitBreaker, RateLimiter, RetryPolicy
from uk_sponsor_pipeline.protocols import CircuitBreaker as CircuitBreakerProtocol
from uk_sponsor_pipeline.protocols import RateLimiter as RateLimiterProtocol
from uk_sponsor_pipeline.protocols import RetryPolicy as RetryPolicyProtocol


def test_rate_limiter_conforms_to_protocol() -> None:
    assert isinstance(RateLimiter(), RateLimiterProtocol)
    assert isinstance(FakeRateLimiter(), RateLimiterProtocol)


def test_circuit_breaker_conforms_to_protocol() -> None:
    assert isinstance(CircuitBreaker(), CircuitBreakerProtocol)
    assert isinstance(FakeCircuitBreaker(), CircuitBreakerProtocol)


def test_retry_policy_conforms_to_protocol() -> None:
    assert isinstance(RetryPolicy(), RetryPolicyProtocol)
