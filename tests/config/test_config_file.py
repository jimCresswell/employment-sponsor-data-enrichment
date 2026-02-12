"""Tests for config-file schema parsing and fail-fast validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fakes import InMemoryFileSystem
from uk_sponsor_pipeline.config_file import load_pipeline_config_file
from uk_sponsor_pipeline.exceptions import (
    ConfigFileNotFoundError,
    ConfigFileParseError,
    ConfigFileValidationError,
)


def _write(fs: InMemoryFileSystem, path: Path, content: str) -> None:
    fs.write_text(content, path)


def test_load_pipeline_config_file_parses_valid_toml() -> None:
    fs = InMemoryFileSystem()
    path = Path("config/pipeline.toml")
    _write(
        fs,
        path,
        """
schema_version = 1

[pipeline]
ch_source_type = "file"
snapshot_root = "data/cache/snapshots"
sponsor_clean_path = "data/cache/snapshots/sponsor/2026-02-01/clean.csv"
ch_clean_path = "data/cache/snapshots/companies_house/2026-02-01/clean.csv"
ch_token_index_dir = "data/cache/snapshots/companies_house/2026-02-01"
ch_file_max_candidates = 600
ch_batch_size = 300
ch_min_match_score = 0.81
ch_search_limit = 12
tech_score_threshold = 0.61
sector_profile_path = "data/reference/scoring_profiles.json"
sector_name = "tech"
geo_filter_region = "London"
geo_filter_postcodes = ["EC", " SW ", "", "N1"]
location_aliases_path = "data/reference/location_aliases.json"
min_employee_count = 1000
include_unknown_employee_count = true
""".strip(),
    )

    parsed = load_pipeline_config_file(path=path, fs=fs)

    assert parsed.ch_source_type == "file"
    assert parsed.snapshot_root == "data/cache/snapshots"
    assert parsed.sponsor_clean_path is not None
    assert parsed.ch_clean_path is not None
    assert parsed.ch_token_index_dir is not None
    assert parsed.sponsor_clean_path.endswith("/sponsor/2026-02-01/clean.csv")
    assert parsed.ch_clean_path.endswith("/companies_house/2026-02-01/clean.csv")
    assert parsed.ch_token_index_dir.endswith("/companies_house/2026-02-01")
    assert parsed.ch_file_max_candidates == 600
    assert parsed.ch_batch_size == 300
    assert parsed.ch_min_match_score == 0.81
    assert parsed.ch_search_limit == 12
    assert parsed.tech_score_threshold == 0.61
    assert parsed.sector_profile_path == "data/reference/scoring_profiles.json"
    assert parsed.sector_name == "tech"
    assert parsed.geo_filter_region == "London"
    assert parsed.geo_filter_postcodes == ("EC", "SW", "N1")
    assert parsed.location_aliases_path == "data/reference/location_aliases.json"
    assert parsed.min_employee_count == 1000
    assert parsed.include_unknown_employee_count is True


def test_load_pipeline_config_file_fails_when_file_missing() -> None:
    fs = InMemoryFileSystem()

    with pytest.raises(ConfigFileNotFoundError):
        load_pipeline_config_file(path=Path("missing.toml"), fs=fs)


def test_load_pipeline_config_file_fails_for_invalid_toml() -> None:
    fs = InMemoryFileSystem()
    path = Path("config/pipeline.toml")
    _write(fs, path, "schema_version = 1\n[pipeline\nch_source_type = 'file'")

    with pytest.raises(ConfigFileParseError):
        load_pipeline_config_file(path=path, fs=fs)


def test_load_pipeline_config_file_fails_when_pipeline_section_missing() -> None:
    fs = InMemoryFileSystem()
    path = Path("config/pipeline.toml")
    _write(fs, path, "schema_version = 1")

    with pytest.raises(ConfigFileValidationError) as exc_info:
        load_pipeline_config_file(path=path, fs=fs)

    assert "pipeline" in str(exc_info.value)


def test_load_pipeline_config_file_fails_for_unsupported_schema_version() -> None:
    fs = InMemoryFileSystem()
    path = Path("config/pipeline.toml")
    _write(
        fs,
        path,
        """
schema_version = 2
[pipeline]
ch_source_type = "file"
""".strip(),
    )

    with pytest.raises(ConfigFileValidationError) as exc_info:
        load_pipeline_config_file(path=path, fs=fs)

    assert "schema_version" in str(exc_info.value)


def test_load_pipeline_config_file_fails_for_unknown_pipeline_key() -> None:
    fs = InMemoryFileSystem()
    path = Path("config/pipeline.toml")
    _write(
        fs,
        path,
        """
schema_version = 1
[pipeline]
unexpected = "value"
""".strip(),
    )

    with pytest.raises(ConfigFileValidationError) as exc_info:
        load_pipeline_config_file(path=path, fs=fs)

    assert "unexpected" in str(exc_info.value)


def test_load_pipeline_config_file_fails_for_invalid_source_type() -> None:
    fs = InMemoryFileSystem()
    path = Path("config/pipeline.toml")
    _write(
        fs,
        path,
        """
schema_version = 1
[pipeline]
ch_source_type = "invalid"
""".strip(),
    )

    with pytest.raises(ConfigFileValidationError) as exc_info:
        load_pipeline_config_file(path=path, fs=fs)

    assert "ch_source_type" in str(exc_info.value)


def test_load_pipeline_config_file_fails_for_multi_region_value() -> None:
    fs = InMemoryFileSystem()
    path = Path("config/pipeline.toml")
    _write(
        fs,
        path,
        """
schema_version = 1
[pipeline]
geo_filter_region = "London,Leeds"
""".strip(),
    )

    with pytest.raises(ConfigFileValidationError) as exc_info:
        load_pipeline_config_file(path=path, fs=fs)

    assert "geo_filter_region" in str(exc_info.value)


def test_load_pipeline_config_file_fails_for_invalid_numeric_ranges() -> None:
    fs = InMemoryFileSystem()
    path = Path("config/pipeline.toml")
    _write(
        fs,
        path,
        """
schema_version = 1
[pipeline]
ch_batch_size = 0
""".strip(),
    )

    with pytest.raises(ConfigFileValidationError) as exc_info:
        load_pipeline_config_file(path=path, fs=fs)

    assert "ch_batch_size" in str(exc_info.value)


def test_load_pipeline_config_file_fails_for_non_positive_min_employee_count() -> None:
    fs = InMemoryFileSystem()
    path = Path("config/pipeline.toml")
    _write(
        fs,
        path,
        """
schema_version = 1
[pipeline]
min_employee_count = 0
""".strip(),
    )

    with pytest.raises(ConfigFileValidationError) as exc_info:
        load_pipeline_config_file(path=path, fs=fs)

    assert "min_employee_count" in str(exc_info.value)


def test_load_pipeline_config_file_fails_for_invalid_include_unknown_value() -> None:
    fs = InMemoryFileSystem()
    path = Path("config/pipeline.toml")
    _write(
        fs,
        path,
        """
schema_version = 1
[pipeline]
include_unknown_employee_count = "sometimes"
""".strip(),
    )

    with pytest.raises(ConfigFileValidationError) as exc_info:
        load_pipeline_config_file(path=path, fs=fs)

    assert "include_unknown_employee_count" in str(exc_info.value)
