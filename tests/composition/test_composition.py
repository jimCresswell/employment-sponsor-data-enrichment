"""Tests for CLI composition root wiring."""

from __future__ import annotations

from pathlib import Path
from typing import override

import pytest

from uk_sponsor_pipeline import composition
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.infrastructure import LocalFileSystem, RequestsSession
from uk_sponsor_pipeline.protocols import HttpClient


class DummyHttpClient(HttpClient):
    """HTTP client stub for composition tests."""

    @override
    def get_json(self, url: str, cache_key: str | None = None) -> dict[str, object]:
        return {}


def test_build_cli_dependencies_builds_http_client_for_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = PipelineConfig(ch_api_key="abc123", ch_source_type="api")
    cache_dir = Path("data/cache/companies_house")
    client = DummyHttpClient()
    captured: dict[str, object] = {}

    def fake_build_companies_house_client(
        *,
        api_key: str,
        cache_dir: str | Path,
        max_rpm: int,
        min_delay_seconds: float,
        circuit_breaker_threshold: int,
        circuit_breaker_timeout_seconds: float,
        max_retries: int,
        backoff_factor: float,
        max_backoff_seconds: float,
        jitter_seconds: float,
        timeout_seconds: float,
    ) -> HttpClient:
        captured["api_key"] = api_key
        captured["cache_dir"] = cache_dir
        captured["max_rpm"] = max_rpm
        captured["min_delay_seconds"] = min_delay_seconds
        captured["circuit_breaker_threshold"] = circuit_breaker_threshold
        captured["circuit_breaker_timeout_seconds"] = circuit_breaker_timeout_seconds
        captured["max_retries"] = max_retries
        captured["backoff_factor"] = backoff_factor
        captured["max_backoff_seconds"] = max_backoff_seconds
        captured["jitter_seconds"] = jitter_seconds
        captured["timeout_seconds"] = timeout_seconds
        return client

    monkeypatch.setattr(
        composition, "build_companies_house_client", fake_build_companies_house_client
    )

    deps = composition.build_cli_dependencies(
        config=config,
        cache_dir=cache_dir,
        build_http_client=True,
    )

    assert isinstance(deps.fs, LocalFileSystem)
    assert isinstance(deps.http_session, RequestsSession)
    assert deps.http_client is client
    assert captured["api_key"] == config.ch_api_key
    assert captured["cache_dir"] == cache_dir
    assert captured["max_rpm"] == config.ch_max_rpm
    assert captured["min_delay_seconds"] == config.ch_sleep_seconds
    assert captured["circuit_breaker_threshold"] == config.ch_circuit_breaker_threshold
    assert captured["circuit_breaker_timeout_seconds"] == config.ch_circuit_breaker_timeout_seconds
    assert captured["max_retries"] == config.ch_max_retries
    assert captured["backoff_factor"] == config.ch_backoff_factor
    assert captured["max_backoff_seconds"] == config.ch_backoff_max_seconds
    assert captured["jitter_seconds"] == config.ch_backoff_jitter_seconds
    assert captured["timeout_seconds"] == config.ch_timeout_seconds


def test_build_cli_dependencies_skips_http_client_for_file_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = PipelineConfig(ch_source_type="file")
    cache_dir = Path("data/cache/companies_house")

    def fail_build_companies_house_client(**_: object) -> HttpClient:
        pytest.fail("HTTP client should not be built for file source.")

    monkeypatch.setattr(
        composition, "build_companies_house_client", fail_build_companies_house_client
    )

    deps = composition.build_cli_dependencies(
        config=config,
        cache_dir=cache_dir,
        build_http_client=True,
    )

    assert isinstance(deps.fs, LocalFileSystem)
    assert isinstance(deps.http_session, RequestsSession)
    assert deps.http_client is None


def test_build_cli_dependencies_skips_http_client_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = PipelineConfig(ch_source_type="api", ch_api_key="")
    cache_dir = Path("data/cache/companies_house")

    def fail_build_companies_house_client(**_: object) -> HttpClient:
        pytest.fail("HTTP client should not be built without an API key.")

    monkeypatch.setattr(
        composition, "build_companies_house_client", fail_build_companies_house_client
    )

    deps = composition.build_cli_dependencies(
        config=config,
        cache_dir=cache_dir,
        build_http_client=True,
    )

    assert isinstance(deps.fs, LocalFileSystem)
    assert isinstance(deps.http_session, RequestsSession)
    assert deps.http_client is None
