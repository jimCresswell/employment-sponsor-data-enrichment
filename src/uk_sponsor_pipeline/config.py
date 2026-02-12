"""Centralised, injectable configuration for the UK Sponsor Pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Self

from dotenv import load_dotenv

from .config_file import PipelineConfigFile
from .exceptions import GeoFilterRegionError


class PositiveIntegerEnvVarError(ValueError):
    """Raised when an environment variable must be a positive integer."""

    def __init__(self, env_name: str) -> None:
        super().__init__(f"{env_name} must be a positive integer.")


class BooleanEnvVarError(ValueError):
    """Raised when an environment variable must be a supported boolean."""

    def __init__(self, env_name: str) -> None:
        super().__init__(f"{env_name} must be a boolean value (true/false, 1/0, yes/no, on/off).")


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable configuration object for all pipeline steps.

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
    snapshot_root: str = "data/cache/snapshots"
    sponsor_clean_path: str = ""
    ch_clean_path: str = ""
    ch_token_index_dir: str = ""
    ch_file_max_candidates: int = 500

    # Scoring
    tech_score_threshold: float = 0.55
    sector_profile_path: str = ""
    sector_name: str = ""

    # Geographic filters (applied during usage)
    geo_filter_region: str | None = None
    geo_filter_postcodes: tuple[str, ...] = field(default_factory=tuple)
    location_aliases_path: str = "data/reference/location_aliases.json"

    # Size filters (applied during usage)
    min_employee_count: int | None = None
    include_unknown_employee_count: bool = False

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
            snapshot_root=os.getenv("SNAPSHOT_ROOT", "data/cache/snapshots").strip()
            or "data/cache/snapshots",
            sponsor_clean_path=os.getenv("SPONSOR_CLEAN_PATH", "").strip(),
            ch_clean_path=os.getenv("CH_CLEAN_PATH", "").strip(),
            ch_token_index_dir=os.getenv("CH_TOKEN_INDEX_DIR", "").strip(),
            ch_file_max_candidates=int(os.getenv("CH_FILE_MAX_CANDIDATES", "500")),
            tech_score_threshold=float(os.getenv("TECH_SCORE_THRESHOLD", "0.55")),
            sector_profile_path=os.getenv("SECTOR_PROFILE", "").strip(),
            sector_name=os.getenv("SECTOR_NAME", "").strip(),
            geo_filter_region=_parse_single_region(os.getenv("GEO_FILTER_REGION", "")),
            geo_filter_postcodes=_parse_list(os.getenv("GEO_FILTER_POSTCODES", "")),
            location_aliases_path=os.getenv(
                "LOCATION_ALIASES_PATH", "data/reference/location_aliases.json"
            ).strip()
            or "data/reference/location_aliases.json",
            min_employee_count=_parse_optional_positive_int(
                os.getenv("MIN_EMPLOYEE_COUNT", ""),
                env_name="MIN_EMPLOYEE_COUNT",
            ),
            include_unknown_employee_count=_parse_optional_bool(
                os.getenv("INCLUDE_UNKNOWN_EMPLOYEE_COUNT", ""),
                env_name="INCLUDE_UNKNOWN_EMPLOYEE_COUNT",
            )
            or False,
        )

    def with_overrides(
        self,
        *,
        tech_score_threshold: float | None = None,
        sector_profile_path: str | None = None,
        sector_name: str | None = None,
        geo_filter_region: str | None = None,
        geo_filter_postcodes: tuple[str, ...] | None = None,
        location_aliases_path: str | None = None,
        min_employee_count: int | None = None,
        include_unknown_employee_count: bool | None = None,
    ) -> Self:
        """Return a new config with specified overrides (for CLI options)."""
        return replace(
            self,
            tech_score_threshold=self.tech_score_threshold
            if tech_score_threshold is None
            else tech_score_threshold,
            sector_profile_path=self.sector_profile_path
            if sector_profile_path is None
            else sector_profile_path.strip(),
            sector_name=self.sector_name if sector_name is None else sector_name.strip(),
            geo_filter_region=self.geo_filter_region
            if geo_filter_region is None
            else geo_filter_region,
            geo_filter_postcodes=self.geo_filter_postcodes
            if geo_filter_postcodes is None
            else geo_filter_postcodes,
            location_aliases_path=self.location_aliases_path
            if location_aliases_path is None
            else location_aliases_path,
            min_employee_count=self.min_employee_count
            if min_employee_count is None
            else min_employee_count,
            include_unknown_employee_count=self.include_unknown_employee_count
            if include_unknown_employee_count is None
            else include_unknown_employee_count,
        )

    def with_file_overrides(self, file_config: PipelineConfigFile) -> Self:
        """Return a new config with config-file values overriding env/default values."""
        return replace(
            self,
            ch_source_type=self.ch_source_type
            if file_config.ch_source_type is None
            else file_config.ch_source_type,
            snapshot_root=self.snapshot_root
            if file_config.snapshot_root is None
            else file_config.snapshot_root,
            sponsor_clean_path=self.sponsor_clean_path
            if file_config.sponsor_clean_path is None
            else file_config.sponsor_clean_path,
            ch_clean_path=self.ch_clean_path
            if file_config.ch_clean_path is None
            else file_config.ch_clean_path,
            ch_token_index_dir=self.ch_token_index_dir
            if file_config.ch_token_index_dir is None
            else file_config.ch_token_index_dir,
            ch_file_max_candidates=self.ch_file_max_candidates
            if file_config.ch_file_max_candidates is None
            else file_config.ch_file_max_candidates,
            ch_batch_size=self.ch_batch_size
            if file_config.ch_batch_size is None
            else file_config.ch_batch_size,
            ch_min_match_score=self.ch_min_match_score
            if file_config.ch_min_match_score is None
            else file_config.ch_min_match_score,
            ch_search_limit=self.ch_search_limit
            if file_config.ch_search_limit is None
            else file_config.ch_search_limit,
            tech_score_threshold=self.tech_score_threshold
            if file_config.tech_score_threshold is None
            else file_config.tech_score_threshold,
            sector_profile_path=self.sector_profile_path
            if file_config.sector_profile_path is None
            else file_config.sector_profile_path,
            sector_name=self.sector_name
            if file_config.sector_name is None
            else file_config.sector_name,
            geo_filter_region=self.geo_filter_region
            if file_config.geo_filter_region is None
            else file_config.geo_filter_region,
            geo_filter_postcodes=self.geo_filter_postcodes
            if file_config.geo_filter_postcodes is None
            else file_config.geo_filter_postcodes,
            location_aliases_path=self.location_aliases_path
            if file_config.location_aliases_path is None
            else file_config.location_aliases_path,
            min_employee_count=self.min_employee_count
            if file_config.min_employee_count is None
            else file_config.min_employee_count,
            include_unknown_employee_count=self.include_unknown_employee_count
            if file_config.include_unknown_employee_count is None
            else file_config.include_unknown_employee_count,
        )


def _parse_list(s: str) -> tuple[str, ...]:
    """Parse comma-separated string into tuple of stripped values."""
    items = [item.strip() for item in s.split(",") if item.strip()]
    return tuple(items)


def _parse_single_region(s: str) -> str | None:
    """Parse an optional single region value."""
    item = s.strip()
    if not item:
        return None
    if "," in item:
        raise GeoFilterRegionError()
    return item


def _parse_optional_positive_int(value: str, *, env_name: str) -> int | None:
    """Parse an optional positive integer from an environment variable."""
    text = value.strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except ValueError as exc:
        raise PositiveIntegerEnvVarError(env_name) from exc
    if parsed < 1:
        raise PositiveIntegerEnvVarError(env_name)
    return parsed


def _parse_optional_bool(value: str, *, env_name: str) -> bool | None:
    """Parse an optional boolean from an environment variable."""
    text = value.strip().lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise BooleanEnvVarError(env_name)
