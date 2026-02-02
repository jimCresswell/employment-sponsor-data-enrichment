"""Composition root for wiring CLI dependencies."""

from __future__ import annotations

from pathlib import Path

from .cli import CliDependencies, create_app
from .config import PipelineConfig
from .infrastructure import LocalFileSystem, RequestsSession, build_companies_house_client
from .protocols import HttpClient


def build_cli_dependencies(
    *,
    config: PipelineConfig,
    cache_dir: str | Path,
    build_http_client: bool,
) -> CliDependencies:
    """Build concrete dependencies for CLI commands.

    Args:
        config: Pipeline configuration (used for API client wiring).
        cache_dir: Cache directory for Companies House API responses.
        build_http_client: Whether to construct the HTTP client when configuration permits.
    """
    fs = LocalFileSystem()
    http_session = RequestsSession()
    http_client: HttpClient | None = None
    if build_http_client and config.ch_source_type == "api" and config.ch_api_key:
        http_client = build_companies_house_client(
            api_key=config.ch_api_key,
            cache_dir=cache_dir,
            max_rpm=config.ch_max_rpm,
            min_delay_seconds=config.ch_sleep_seconds,
            circuit_breaker_threshold=config.ch_circuit_breaker_threshold,
            circuit_breaker_timeout_seconds=config.ch_circuit_breaker_timeout_seconds,
            max_retries=config.ch_max_retries,
            backoff_factor=config.ch_backoff_factor,
            max_backoff_seconds=config.ch_backoff_max_seconds,
            jitter_seconds=config.ch_backoff_jitter_seconds,
            timeout_seconds=config.ch_timeout_seconds,
        )
    return CliDependencies(fs=fs, http_session=http_session, http_client=http_client)


app = create_app(build_cli_dependencies)
