"""Centralized, injectable configuration for the UK Sponsor Pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
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

    # Stage 3 scoring
    tech_score_threshold: float = 0.55

    # Geographic filters (applied in Stage 3)
    geo_filter_regions: tuple[str, ...] = field(default_factory=tuple)
    geo_filter_postcodes: tuple[str, ...] = field(default_factory=tuple)

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
            tech_score_threshold=float(os.getenv("TECH_SCORE_THRESHOLD", "0.55")),
            geo_filter_regions=_parse_list(os.getenv("GEO_FILTER_REGIONS", "")),
            geo_filter_postcodes=_parse_list(os.getenv("GEO_FILTER_POSTCODES", "")),
        )

    def with_overrides(
        self,
        *,
        tech_score_threshold: float | None = None,
        geo_filter_regions: tuple[str, ...] | None = None,
        geo_filter_postcodes: tuple[str, ...] | None = None,
    ) -> Self:
        """Return a new config with specified overrides (for CLI options)."""
        return type(self)(
            ch_api_key=self.ch_api_key,
            ch_sleep_seconds=self.ch_sleep_seconds,
            ch_min_match_score=self.ch_min_match_score,
            ch_search_limit=self.ch_search_limit,
            ch_max_rpm=self.ch_max_rpm,
            tech_score_threshold=tech_score_threshold
            if tech_score_threshold is not None
            else self.tech_score_threshold,
            geo_filter_regions=geo_filter_regions
            if geo_filter_regions is not None
            else self.geo_filter_regions,
            geo_filter_postcodes=geo_filter_postcodes
            if geo_filter_postcodes is not None
            else self.geo_filter_postcodes,
        )


def _parse_list(s: str) -> tuple[str, ...]:
    """Parse comma-separated string into tuple of stripped values."""
    if not s.strip():
        return ()
    return tuple(item.strip() for item in s.split(",") if item.strip())
