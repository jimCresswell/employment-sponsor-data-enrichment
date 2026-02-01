"""Protocol definitions for dependency injection.

These protocols define the abstract interfaces that pipeline components depend on,
enabling isolated unit testing with mock implementations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd


@runtime_checkable
class HttpClient(Protocol):
    """Abstract HTTP client for making JSON API requests."""

    def get_json(self, url: str, cache_key: str | None = None) -> dict[str, Any]:
        """Fetch JSON from URL, optionally using cache.

        Args:
            url: The URL to fetch.
            cache_key: Optional cache key. If provided and cached, return cached value.

        Returns:
            Parsed JSON response as dict.

        Raises:
            RequestError: On network or HTTP errors.
        """
        ...


@runtime_checkable
class Cache(Protocol):
    """Abstract cache for storing/retrieving JSON data."""

    def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve cached value by key, or None if not present."""
        ...

    def set(self, key: str, value: dict[str, Any]) -> None:
        """Store value in cache with given key."""
        ...

    def has(self, key: str) -> bool:
        """Check if key exists in cache."""
        ...


@runtime_checkable
class FileSystem(Protocol):
    """Abstract filesystem for reading/writing pipeline data."""

    def read_csv(self, path: Path) -> pd.DataFrame:
        """Read CSV file into DataFrame."""
        ...

    def write_csv(self, df: pd.DataFrame, path: Path) -> None:
        """Write DataFrame to CSV file."""
        ...

    def append_csv(self, df: pd.DataFrame, path: Path) -> None:
        """Append DataFrame rows to CSV file (create if missing)."""
        ...

    def read_json(self, path: Path) -> dict[str, Any]:
        """Read JSON file."""
        ...

    def write_json(self, data: dict[str, Any], path: Path) -> None:
        """Write JSON file."""
        ...

    def read_text(self, path: Path) -> str:
        """Read text file."""
        ...

    def write_text(self, content: str, path: Path) -> None:
        """Write text file."""
        ...

    def read_bytes(self, path: Path) -> bytes:
        """Read binary file."""
        ...

    def write_bytes(self, content: bytes, path: Path) -> None:
        """Write binary file."""
        ...

    def exists(self, path: Path) -> bool:
        """Check if path exists."""
        ...

    def mkdir(self, path: Path, parents: bool = True) -> None:
        """Create directory."""
        ...

    def list_files(self, path: Path, pattern: str = "*") -> list[Path]:
        """List files matching pattern in directory."""
        ...

    def mtime(self, path: Path) -> float:
        """Return modification time for a path."""
        ...


@runtime_checkable
class RateLimiter(Protocol):
    """Abstract rate limiter for outbound requests."""

    def wait_if_needed(self) -> None:
        """Block until a request is allowed."""
        ...


@runtime_checkable
class CircuitBreaker(Protocol):
    """Abstract circuit breaker for outbound requests."""

    def check(self) -> None:
        """Raise if the circuit is open."""
        ...

    def record_success(self) -> None:
        """Record a successful request."""
        ...

    def record_failure(self) -> None:
        """Record a failed request."""
        ...


@runtime_checkable
class RetryPolicy(Protocol):
    """Abstract retry policy for transient failures."""

    max_retries: int
    retry_statuses: tuple[int, ...]
    retry_exceptions: tuple[type[Exception], ...]

    def compute_backoff(self, attempt: int, retry_after: int | None = None) -> float:
        """Return a delay for the next retry attempt."""
        ...
