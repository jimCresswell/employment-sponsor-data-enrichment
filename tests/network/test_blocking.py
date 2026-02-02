"""Test that network access is properly blocked in tests."""

import socket

import pytest

from tests.support.errors import NetworkIsolationError


class TestNetworkBlocking:
    """Verify that the network blocking fixture works."""

    def test_socket_connect_is_blocked(self) -> None:
        """Attempting to connect a socket should raise NetworkIsolationError."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(NetworkIsolationError) as exc_info:
                sock.connect(("httpbin.org", 80))
            assert "Tests must not make network connections" in str(exc_info.value)
        finally:
            sock.close()

    def test_requests_would_fail_without_mock(self) -> None:
        """Importing requests and trying to use it would fail without mocking."""
        import requests

        # This would try to make a real connection if not mocked
        # The socket blocking will prevent it
        with pytest.raises(NetworkIsolationError) as exc_info:
            requests.get("https://httpbin.org/get", timeout=1)
        assert "Tests must not make network connections" in str(exc_info.value)
