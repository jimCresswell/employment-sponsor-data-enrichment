"""Protocol definitions for dependency injection.

These protocols define the abstract interfaces that pipeline components depend on,
enabling isolated unit testing with mock implementations.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Literal, Protocol, TextIO, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd

TextOpenMode = Literal[
    "r",
    "r+",
    "w",
    "w+",
    "a",
    "a+",
    "x",
    "x+",
]
BinaryOpenMode = Literal[
    "rb",
    "rb+",
    "wb",
    "wb+",
    "ab",
    "ab+",
    "xb",
    "xb+",
]


@runtime_checkable
class HttpClient(Protocol):
    """Abstract HTTP client for making JSON API requests."""

    def get_json(self, url: str, cache_key: str | None = None) -> dict[str, object]:
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
class HttpSession(Protocol):
    """Abstract HTTP session for non-JSON requests."""

    def get_text(self, url: str, *, timeout_seconds: float) -> str:
        """Fetch text content from a URL."""
        ...

    def get_bytes(self, url: str, *, timeout_seconds: float) -> bytes:
        """Fetch binary content from a URL."""
        ...

    def iter_bytes(
        self,
        url: str,
        *,
        timeout_seconds: float,
        chunk_size: int,
    ) -> Iterable[bytes]:
        """Stream binary content from a URL in chunks."""
        ...


@runtime_checkable
class Cache(Protocol):
    """Abstract cache for storing/retrieving JSON data."""

    def get(self, key: str) -> dict[str, object] | None:
        """Retrieve cached value by key, or None if not present."""
        ...

    def set(self, key: str, value: dict[str, object]) -> None:
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

    def read_json(self, path: Path) -> dict[str, object]:
        """Read JSON file."""
        ...

    def write_json(self, data: Mapping[str, object], path: Path) -> None:
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

    def write_bytes_stream(self, path: Path, chunks: Iterable[bytes]) -> None:
        """Write binary file from a stream of chunks."""
        ...

    def open_text(
        self,
        path: Path,
        *,
        mode: TextOpenMode,
        encoding: str,
        newline: str | None = None,
    ) -> TextIO:
        """Open a text file handle."""
        ...

    def open_binary(self, path: Path, *, mode: BinaryOpenMode) -> BinaryIO:
        """Open a binary file handle."""
        ...

    def exists(self, path: Path) -> bool:
        """Check if path exists."""
        ...

    def rename(self, src: Path, dest: Path) -> None:
        """Rename a file or directory."""
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


@runtime_checkable
class ProgressReporter(Protocol):
    """CLI-owned progress reporting interface."""

    def start(self, label: str, total: int | None) -> None:
        """Start a progress session."""
        ...

    def advance(self, count: int) -> None:
        """Advance progress by count."""
        ...

    def finish(self) -> None:
        """Finish a progress session."""
        ...
