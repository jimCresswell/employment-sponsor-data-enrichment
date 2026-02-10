"""Tests for configuration precedence resolution."""

from __future__ import annotations

from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.config_file import PipelineConfigFile


def test_with_file_overrides_applies_config_file_values() -> None:
    env_config = PipelineConfig(
        ch_source_type="api",
        snapshot_root="env/snapshots",
        ch_batch_size=250,
        ch_search_limit=10,
        ch_min_match_score=0.72,
        tech_score_threshold=0.55,
        geo_filter_region="London",
        geo_filter_postcodes=("EC",),
        sector_profile_path="env/profiles.json",
        sector_name="env-sector",
        location_aliases_path="env/aliases.json",
    )
    file_config = PipelineConfigFile(
        ch_source_type="file",
        snapshot_root="file/snapshots",
        ch_batch_size=300,
        ch_search_limit=15,
        ch_min_match_score=0.81,
        tech_score_threshold=0.61,
        geo_filter_region="Leeds",
        geo_filter_postcodes=("LS", "BD"),
        sector_profile_path="file/profiles.json",
        sector_name="file-sector",
        location_aliases_path="file/aliases.json",
    )

    resolved = env_config.with_file_overrides(file_config)

    assert resolved.ch_source_type == "file"
    assert resolved.snapshot_root == "file/snapshots"
    assert resolved.ch_batch_size == 300
    assert resolved.ch_search_limit == 15
    assert resolved.ch_min_match_score == 0.81
    assert resolved.tech_score_threshold == 0.61
    assert resolved.geo_filter_region == "Leeds"
    assert resolved.geo_filter_postcodes == ("LS", "BD")
    assert resolved.sector_profile_path == "file/profiles.json"
    assert resolved.sector_name == "file-sector"
    assert resolved.location_aliases_path == "file/aliases.json"


def test_with_file_overrides_keeps_env_when_file_value_missing() -> None:
    env_config = PipelineConfig(
        snapshot_root="env/snapshots",
        ch_batch_size=250,
        tech_score_threshold=0.55,
    )
    file_config = PipelineConfigFile(snapshot_root="file/snapshots")

    resolved = env_config.with_file_overrides(file_config)

    assert resolved.snapshot_root == "file/snapshots"
    assert resolved.ch_batch_size == 250
    assert resolved.tech_score_threshold == 0.55


def test_precedence_cli_over_config_file_over_env_over_defaults() -> None:
    base = PipelineConfig(
        snapshot_root="default/snapshots",
        tech_score_threshold=0.55,
        geo_filter_region="London",
        geo_filter_postcodes=("EC",),
        sector_profile_path="env/profiles.json",
        sector_name="env-sector",
    )
    file_config = PipelineConfigFile(
        snapshot_root="file/snapshots",
        tech_score_threshold=0.42,
        geo_filter_region="Manchester",
        geo_filter_postcodes=("M",),
        sector_profile_path="file/profiles.json",
        sector_name="file-sector",
    )

    resolved = base.with_file_overrides(file_config).with_overrides(
        tech_score_threshold=0.33,
        geo_filter_region="Bristol",
        geo_filter_postcodes=("BS",),
        sector_name="cli-sector",
    )

    # CLI wins
    assert resolved.tech_score_threshold == 0.33
    assert resolved.geo_filter_region == "Bristol"
    assert resolved.geo_filter_postcodes == ("BS",)
    assert resolved.sector_name == "cli-sector"

    # Config file wins over env/default
    assert resolved.snapshot_root == "file/snapshots"
    assert resolved.sector_profile_path == "file/profiles.json"
