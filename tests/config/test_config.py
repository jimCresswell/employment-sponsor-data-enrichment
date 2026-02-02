"""Tests for PipelineConfig behaviour."""

from uk_sponsor_pipeline.config import PipelineConfig


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
        tech_score_threshold=0.6,
        geo_filter_region="London",
        geo_filter_postcodes=("EC",),
        location_aliases_path="data/reference/location_aliases.json",
    )

    updated = base.with_overrides(tech_score_threshold=0.4, geo_filter_region="Leeds")

    assert updated.tech_score_threshold == 0.4
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
