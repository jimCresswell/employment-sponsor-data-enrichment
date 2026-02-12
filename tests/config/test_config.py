"""Tests for PipelineConfig behaviour."""

import pytest

import uk_sponsor_pipeline.config as config_module
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.exceptions import GeoFilterRegionError


def test_with_overrides_preserves_fields() -> None:
    base = PipelineConfig(
        ch_api_key="key",
        ch_sleep_seconds=1.1,
        ch_min_match_score=0.81,
        ch_search_limit=7,
        ch_max_rpm=321,
        ch_timeout_seconds=12.0,
        ch_max_retries=9,
        ch_backoff_factor=0.9,
        ch_backoff_max_seconds=120.0,
        ch_backoff_jitter_seconds=0.2,
        ch_circuit_breaker_threshold=9,
        ch_circuit_breaker_timeout_seconds=99.0,
        ch_batch_size=42,
        ch_source_type="file",
        snapshot_root="data/cache/snapshots",
        sponsor_clean_path="data/cache/snapshots/sponsor/2026-02-01/clean.csv",
        ch_clean_path="data/cache/snapshots/companies_house/2026-02-01/clean.csv",
        ch_token_index_dir="data/cache/snapshots/companies_house/2026-02-01",
        ch_file_max_candidates=321,
        tech_score_threshold=0.6,
        sector_profile_path="data/reference/scoring_profiles.json",
        sector_name="tech",
        geo_filter_region="London",
        geo_filter_postcodes=("EC",),
        location_aliases_path="data/reference/location_aliases.json",
    )

    updated = base.with_overrides(tech_score_threshold=0.4, geo_filter_region="Leeds")

    assert updated.tech_score_threshold == 0.4
    assert updated.sector_profile_path == "data/reference/scoring_profiles.json"
    assert updated.sector_name == "tech"
    assert updated.geo_filter_region == "Leeds"
    assert updated.geo_filter_postcodes == ("EC",)
    assert updated.location_aliases_path == "data/reference/location_aliases.json"

    assert updated.ch_api_key == base.ch_api_key
    assert updated.ch_timeout_seconds == base.ch_timeout_seconds
    assert updated.ch_max_retries == base.ch_max_retries
    assert updated.ch_backoff_factor == base.ch_backoff_factor
    assert updated.ch_backoff_max_seconds == base.ch_backoff_max_seconds
    assert updated.ch_backoff_jitter_seconds == base.ch_backoff_jitter_seconds
    assert updated.ch_circuit_breaker_threshold == base.ch_circuit_breaker_threshold
    assert updated.ch_circuit_breaker_timeout_seconds == base.ch_circuit_breaker_timeout_seconds
    assert updated.ch_batch_size == base.ch_batch_size
    assert updated.ch_source_type == base.ch_source_type
    assert updated.snapshot_root == base.snapshot_root
    assert updated.sponsor_clean_path == base.sponsor_clean_path
    assert updated.ch_clean_path == base.ch_clean_path
    assert updated.ch_token_index_dir == base.ch_token_index_dir
    assert updated.ch_file_max_candidates == base.ch_file_max_candidates


def test_from_env_reads_sector_profile_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "SECTOR_PROFILE": "data/reference/scoring_profiles.json",
        "SECTOR_NAME": "tech",
    }

    def fake_getenv(key: str, default: str = "") -> str:
        return env.get(key, default)

    def fake_load_dotenv(dotenv_path: str | None = None) -> bool:
        _ = dotenv_path
        return True

    monkeypatch.setattr(config_module.os, "getenv", fake_getenv)
    monkeypatch.setattr(config_module, "load_dotenv", fake_load_dotenv)

    config = PipelineConfig.from_env()

    assert config.sector_profile_path == "data/reference/scoring_profiles.json"
    assert config.sector_name == "tech"


def test_from_env_reads_geo_filter_region_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {"GEO_FILTER_REGION": "London"}

    def fake_getenv(key: str, default: str = "") -> str:
        return env.get(key, default)

    def fake_load_dotenv(dotenv_path: str | None = None) -> bool:
        _ = dotenv_path
        return True

    monkeypatch.setattr(config_module.os, "getenv", fake_getenv)
    monkeypatch.setattr(config_module, "load_dotenv", fake_load_dotenv)

    config = PipelineConfig.from_env()

    assert config.geo_filter_region == "London"


def test_from_env_reads_employee_count_filter_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {
        "MIN_EMPLOYEE_COUNT": "1000",
        "INCLUDE_UNKNOWN_EMPLOYEE_COUNT": "true",
    }

    def fake_getenv(key: str, default: str = "") -> str:
        return env.get(key, default)

    def fake_load_dotenv(dotenv_path: str | None = None) -> bool:
        _ = dotenv_path
        return True

    monkeypatch.setattr(config_module.os, "getenv", fake_getenv)
    monkeypatch.setattr(config_module, "load_dotenv", fake_load_dotenv)

    config = PipelineConfig.from_env()

    assert config.min_employee_count == 1000
    assert config.include_unknown_employee_count is True


def test_from_env_rejects_multi_region_geo_filter_region(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {"GEO_FILTER_REGION": "London,Leeds"}

    def fake_getenv(key: str, default: str = "") -> str:
        return env.get(key, default)

    def fake_load_dotenv(dotenv_path: str | None = None) -> bool:
        _ = dotenv_path
        return True

    monkeypatch.setattr(config_module.os, "getenv", fake_getenv)
    monkeypatch.setattr(config_module, "load_dotenv", fake_load_dotenv)

    with pytest.raises(GeoFilterRegionError):
        PipelineConfig.from_env()


def test_from_env_rejects_non_positive_min_employee_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {"MIN_EMPLOYEE_COUNT": "0"}

    def fake_getenv(key: str, default: str = "") -> str:
        return env.get(key, default)

    def fake_load_dotenv(dotenv_path: str | None = None) -> bool:
        _ = dotenv_path
        return True

    monkeypatch.setattr(config_module.os, "getenv", fake_getenv)
    monkeypatch.setattr(config_module, "load_dotenv", fake_load_dotenv)

    with pytest.raises(ValueError, match="MIN_EMPLOYEE_COUNT"):
        PipelineConfig.from_env()


def test_from_env_rejects_invalid_include_unknown_employee_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {"INCLUDE_UNKNOWN_EMPLOYEE_COUNT": "maybe"}

    def fake_getenv(key: str, default: str = "") -> str:
        return env.get(key, default)

    def fake_load_dotenv(dotenv_path: str | None = None) -> bool:
        _ = dotenv_path
        return True

    monkeypatch.setattr(config_module.os, "getenv", fake_getenv)
    monkeypatch.setattr(config_module, "load_dotenv", fake_load_dotenv)

    with pytest.raises(ValueError, match="INCLUDE_UNKNOWN_EMPLOYEE_COUNT"):
        PipelineConfig.from_env()


def test_from_env_ignores_removed_geo_filter_regions_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {"GEO_FILTER_REGIONS": "Manchester"}

    def fake_getenv(key: str, default: str = "") -> str:
        return env.get(key, default)

    def fake_load_dotenv(dotenv_path: str | None = None) -> bool:
        _ = dotenv_path
        return True

    monkeypatch.setattr(config_module.os, "getenv", fake_getenv)
    monkeypatch.setattr(config_module, "load_dotenv", fake_load_dotenv)

    config = PipelineConfig.from_env()

    assert config.geo_filter_region is None
