"""Pytest fixtures and mock implementations for testing.

All tests are network-isolated - socket connections are blocked by default.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

# =============================================================================
# Network Isolation - Block all socket connections in tests
# =============================================================================

_original_socket_connect = socket.socket.connect


def _blocked_socket_connect(self, *args, **kwargs):
    """Raise an error if any test tries to make a real network connection."""
    raise RuntimeError(
        "Tests must not make network connections! "
        "Use mocks or FakeHttpClient instead. "
        f"Attempted connection to: {args}"
    )


@pytest.fixture(autouse=True)
def block_network_access(monkeypatch):
    """Block all network access in tests.

    This fixture runs automatically for all tests and prevents any real
    network connections. Tests that need HTTP should use FakeHttpClient
    or MagicMock.

    If you need E2E tests with real network access, mark them with:
        @pytest.mark.e2e
    and run them separately with: pytest -m e2e
    """
    monkeypatch.setattr(socket.socket, "connect", _blocked_socket_connect)
    yield


@dataclass
class InMemoryCache:
    """In-memory cache for testing."""

    _store: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get(self, key: str) -> dict[str, Any] | None:
        return self._store.get(key)

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._store[key] = value

    def has(self, key: str) -> bool:
        return key in self._store


@dataclass
class FakeHttpClient:
    """Fake HTTP client that returns canned responses."""

    responses: dict[str, dict[str, Any]] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def get_json(self, url: str, cache_key: str | None = None) -> dict[str, Any]:
        self.calls.append(url)
        # Match by URL prefix for flexibility
        for pattern, response in self.responses.items():
            if pattern in url:
                return response
        raise ValueError(f"No canned response for URL: {url}")


@dataclass
class InMemoryFileSystem:
    """In-memory filesystem for testing."""

    _files: dict[str, Any] = field(default_factory=dict)

    def read_csv(self, path: Path) -> pd.DataFrame:
        key = str(path)
        if key not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        data = self._files[key]
        if isinstance(data, pd.DataFrame):
            return data
        raise TypeError(f"Expected DataFrame at {path}")

    def write_csv(self, df: pd.DataFrame, path: Path) -> None:
        self._files[str(path)] = df.copy()

    def read_json(self, path: Path) -> dict[str, Any]:
        key = str(path)
        if key not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        return self._files[key]

    def write_json(self, data: dict[str, Any], path: Path) -> None:
        self._files[str(path)] = data

    def read_text(self, path: Path) -> str:
        key = str(path)
        if key not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        return self._files[key]

    def write_text(self, content: str, path: Path) -> None:
        self._files[str(path)] = content

    def read_bytes(self, path: Path) -> bytes:
        key = str(path)
        if key not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        data = self._files[key]
        if isinstance(data, bytes):
            return data
        raise TypeError(f"Expected bytes at {path}")

    def write_bytes(self, content: bytes, path: Path) -> None:
        self._files[str(path)] = content

    def exists(self, path: Path) -> bool:
        return str(path) in self._files

    def mkdir(self, path: Path, parents: bool = True) -> None:
        # No-op for in-memory filesystem
        pass

    def list_files(self, path: Path, pattern: str = "*") -> list[Path]:
        import fnmatch

        prefix = str(path)
        matches = []
        for key in self._files:
            if key.startswith(prefix):
                relative = key[len(prefix) :].lstrip("/")
                if fnmatch.fnmatch(relative, pattern):
                    matches.append(Path(key))
        return sorted(matches)


@pytest.fixture
def in_memory_cache() -> InMemoryCache:
    """Provide an in-memory cache for tests."""
    return InMemoryCache()


@pytest.fixture
def fake_http_client() -> FakeHttpClient:
    """Provide a fake HTTP client for tests."""
    return FakeHttpClient()


@pytest.fixture
def in_memory_fs() -> InMemoryFileSystem:
    """Provide an in-memory filesystem for tests."""
    return InMemoryFileSystem()


@pytest.fixture
def sample_raw_csv() -> pd.DataFrame:
    """Sample raw sponsor register data for testing."""
    return pd.DataFrame(
        {
            "Organisation Name": [
                "ACME Software Ltd",
                "ACME SOFTWARE LIMITED",  # Duplicate with different casing
                "Tech Corp T/A Digital Solutions",
                "City Hospital NHS Trust",
                "Bob's Construction Ltd",
            ],
            "Town/City": ["London", "London", "Manchester", "Birmingham", "Leeds"],
            "County": [
                "Greater London",
                "Greater London",
                "Greater Manchester",
                "West Midlands",
                "West Yorkshire",
            ],
            "Type & Rating": ["A rating", "A rating", "A rating", "A rating", "A rating"],
            "Route": [
                "Skilled Worker",
                "Skilled Worker",
                "Skilled Worker",
                "Skilled Worker",
                "Skilled Worker",
            ],
        }
    )


@pytest.fixture
def sample_ch_search_response() -> dict[str, Any]:
    """Sample Companies House search response."""
    return {
        "items": [
            {
                "company_number": "12345678",
                "title": "ACME SOFTWARE LTD",
                "company_status": "active",
                "address": {
                    "locality": "London",
                    "region": "Greater London",
                    "postal_code": "EC1A 1BB",
                },
            },
            {
                "company_number": "87654321",
                "title": "ACME SOLUTIONS LTD",
                "company_status": "active",
                "address": {
                    "locality": "London",
                    "region": "Greater London",
                    "postal_code": "SW1A 1AA",
                },
            },
        ]
    }


@pytest.fixture
def sample_ch_profile_response() -> dict[str, Any]:
    """Sample Companies House company profile response."""
    return {
        "company_number": "12345678",
        "company_name": "ACME SOFTWARE LTD",
        "company_status": "active",
        "type": "ltd",
        "date_of_creation": "2015-03-15",
        "sic_codes": ["62020", "62090"],
        "registered_office_address": {
            "locality": "London",
            "region": "Greater London",
            "postal_code": "EC1A 1BB",
        },
    }
