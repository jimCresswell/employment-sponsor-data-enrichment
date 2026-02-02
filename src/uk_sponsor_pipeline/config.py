"""Centralized, injectable configuration for the UK Sponsor Pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Self

from dotenv import load_dotenv


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable configuration object for all pipeline stages.

    Load from environment with `PipelineConfig.from_env()` or construct directly for testing.
    """

    # Companies House API
    ch_api_key: str = ""
    ch_sleep_seconds: float = 0.2
    ch_min_match_score: float = 0.72
    ch_search_limit: int = 10
    ch_max_rpm: int = 600  # Companies House rate limit
    ch_timeout_seconds: float = 30.0
    ch_max_retries: int = 3
    ch_backoff_factor: float = 0.5
    ch_backoff_max_seconds: float = 60.0
    ch_backoff_jitter_seconds: float = 0.1
    ch_circuit_breaker_threshold: int = 5
    ch_circuit_breaker_timeout_seconds: float = 60.0
    ch_batch_size: int = 250
    ch_source_type: str = "api"
    ch_source_path: str = ""

    # Stage 3 scoring
    tech_score_threshold: float = 0.55

    # Geographic filters (applied in Stage 3)
    geo_filter_region: str | None = None
    geo_filter_postcodes: tuple[str, ...] = field(default_factory=tuple)
    location_aliases_path: str = "data/reference/location_aliases.json"

    @classmethod
    def from_env(cls, dotenv_path: str | None = None) -> Self:
        """Load configuration from environment variables.

        Args:
            dotenv_path: Optional path to .env file. If None, uses default .env discovery.

        Returns:
            PipelineConfig instance populated from environment.
        """
        load_dotenv(dotenv_path)

        return cls(
            ch_api_key=os.getenv("CH_API_KEY", "").strip(),
            ch_sleep_seconds=float(os.getenv("CH_SLEEP_SECONDS", "0.2")),
            ch_min_match_score=float(os.getenv("CH_MIN_MATCH_SCORE", "0.72")),
            ch_search_limit=int(os.getenv("CH_SEARCH_LIMIT", "10")),
            ch_max_rpm=int(os.getenv("CH_MAX_RPM", "600")),
            ch_timeout_seconds=float(os.getenv("CH_TIMEOUT_SECONDS", "30")),
            ch_max_retries=int(os.getenv("CH_MAX_RETRIES", "3")),
            ch_backoff_factor=float(os.getenv("CH_BACKOFF_FACTOR", "0.5")),
            ch_backoff_max_seconds=float(os.getenv("CH_BACKOFF_MAX_SECONDS", "60")),
            ch_backoff_jitter_seconds=float(os.getenv("CH_BACKOFF_JITTER_SECONDS", "0.1")),
            ch_circuit_breaker_threshold=int(os.getenv("CH_CIRCUIT_BREAKER_THRESHOLD", "5")),
            ch_circuit_breaker_timeout_seconds=float(
                os.getenv("CH_CIRCUIT_BREAKER_TIMEOUT_SECONDS", "60")
            ),
            ch_batch_size=int(os.getenv("CH_BATCH_SIZE", "250")),
            ch_source_type=os.getenv("CH_SOURCE_TYPE", "api").strip().lower(),
            ch_source_path=os.getenv("CH_SOURCE_PATH", "").strip(),
            tech_score_threshold=float(os.getenv("TECH_SCORE_THRESHOLD", "0.55")),
            geo_filter_region=_parse_single_region(os.getenv("GEO_FILTER_REGIONS", "")),
            geo_filter_postcodes=_parse_list(os.getenv("GEO_FILTER_POSTCODES", "")),
            location_aliases_path=os.getenv(
                "LOCATION_ALIASES_PATH", "data/reference/location_aliases.json"
            ).strip()
            or "data/reference/location_aliases.json",
        )

    def with_overrides(
        self,
        *,
        tech_score_threshold: float | None = None,
        geo_filter_region: str | None = None,
        geo_filter_postcodes: tuple[str, ...] | None = None,
        location_aliases_path: str | None = None,
    ) -> Self:
        """Return a new config with specified overrides (for CLI options)."""
        return replace(
            self,
            tech_score_threshold=self.tech_score_threshold
            if tech_score_threshold is None
            else tech_score_threshold,
            geo_filter_region=self.geo_filter_region
            if geo_filter_region is None
            else geo_filter_region,
            geo_filter_postcodes=self.geo_filter_postcodes
            if geo_filter_postcodes is None
            else geo_filter_postcodes,
            location_aliases_path=self.location_aliases_path
            if location_aliases_path is None
            else location_aliases_path,
        )


def _parse_list(s: str) -> tuple[str, ...]:
    """Parse comma-separated string into tuple of stripped values."""
    items = [item.strip() for item in s.split(",") if item.strip()]
    return tuple(items)


def _parse_single_region(s: str) -> str | None:
    """Parse a single region value from comma-separated input."""
    items = _parse_list(s)
    if not items:
        return None
    if len(items) > 1:
        raise ValueError("GEO_FILTER_REGIONS must contain at most one region.")
    for item in items:
        return item
    return None
