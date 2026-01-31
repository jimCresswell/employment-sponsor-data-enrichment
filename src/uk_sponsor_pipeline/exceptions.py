"""Custom exceptions for the UK Sponsor Pipeline.

These exceptions provide clear error handling and enable testing of error paths.
"""

from __future__ import annotations


class PipelineError(Exception):
    """Base exception for all pipeline errors."""

    pass


class AuthenticationError(PipelineError):
    """Raised when API authentication fails (401 Unauthorized).

    This is a fatal error - the pipeline should stop immediately.
    """

    def __init__(self, message: str = "API authentication failed") -> None:
        super().__init__(
            f"{message}\n"
            "Please check your CH_API_KEY in .env is correct and not expired.\n"
            "Get a new key at: https://developer.company-information.service.gov.uk/"
        )


class RateLimitError(PipelineError):
    """Raised when API rate limit is exceeded (429 Too Many Requests).

    The pipeline should back off and retry.
    """

    def __init__(self, retry_after: int = 60) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")


class CircuitBreakerOpen(PipelineError):
    """Raised when circuit breaker trips due to repeated failures.

    The pipeline should stop to prevent further damage.
    """

    def __init__(self, failure_count: int, threshold: int) -> None:
        self.failure_count = failure_count
        self.threshold = threshold
        super().__init__(
            f"Circuit breaker tripped: {failure_count} consecutive failures "
            f"(threshold: {threshold}). Stopping to prevent API ban."
        )
