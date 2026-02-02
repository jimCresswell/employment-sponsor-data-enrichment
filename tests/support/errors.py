"""Test-only exceptions for enforcing constraints."""

from __future__ import annotations


class NetworkIsolationError(RuntimeError):
    """Raised when a test attempts a real network connection."""

    def __init__(self, attempted: str) -> None:
        super().__init__(
            "Tests must not make network connections! "
            "Use mocks or FakeHttpClient instead. "
            f"Attempted connection to: {attempted}"
        )


class FakeResponseMissingError(ValueError):
    """Raised when a fake HTTP client has no canned response configured."""

    def __init__(self, url: str) -> None:
        super().__init__(f"No canned response for URL: {url}")


class FakeFileNotFoundError(FileNotFoundError):
    """Raised when a fake filesystem path is missing."""

    def __init__(self, path: str) -> None:
        super().__init__(f"No such file: {path}")


class FakeFileTypeError(TypeError):
    """Raised when a fake filesystem payload has the wrong type."""

    def __init__(self, expected: str, path: str) -> None:
        super().__init__(f"Expected {expected} at {path}")
