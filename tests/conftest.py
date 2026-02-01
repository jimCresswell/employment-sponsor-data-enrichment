"""Pytest fixtures and mock implementations for testing.

All tests are network-isolated - socket connections are blocked by default.
"""

from __future__ import annotations

import socket

import pandas as pd
import pytest

from tests.fakes import FakeHttpClient, InMemoryCache, InMemoryFileSystem

# =============================================================================
# Network Isolation - Block all socket connections in tests
# =============================================================================

_original_socket_connect = socket.socket.connect


def _blocked_socket_connect(self: socket.socket, *args: object, **kwargs: object) -> None:
    """Raise an error if any test tries to make a real network connection."""
    raise RuntimeError(
        "Tests must not make network connections! "
        "Use mocks or FakeHttpClient instead. "
        f"Attempted connection to: {args}"
    )


@pytest.fixture(autouse=True)
def block_network_access(monkeypatch: pytest.MonkeyPatch):
    """Block all network access in tests.

    This fixture runs automatically for all tests and prevents any real
    network connections. Tests that need HTTP should use FakeHttpClient
    or MagicMock.

    All tests must remain fully isolated from real network access.
    """
    monkeypatch.setattr(socket.socket, "connect", _blocked_socket_connect)
    yield


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
def sample_ch_search_response() -> dict[str, object]:
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
def sample_ch_profile_response() -> dict[str, object]:
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
