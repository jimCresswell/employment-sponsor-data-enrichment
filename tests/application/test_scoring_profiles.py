"""Tests for scoring profile schema validation and loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fakes import InMemoryFileSystem
from uk_sponsor_pipeline.application.scoring_profiles import (
    load_scoring_profile_catalog,
    resolve_scoring_profile,
)
from uk_sponsor_pipeline.exceptions import (
    ScoringProfileFileNotFoundError,
    ScoringProfileSelectionError,
    ScoringProfileValidationError,
)
from uk_sponsor_pipeline.infrastructure import LocalFileSystem
from uk_sponsor_pipeline.io_validation import validate_as


def _valid_catalog_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "default_profile": "tech",
        "profiles": [
            {
                "name": "tech",
                "job_type": "software_engineering",
                "sector_signals": {"technology": 0.0},
                "location_signals": {},
                "size_signals": {},
                "sic_positive_prefixes": {"620": 0.5, "631": 0.4, "711": 0.15},
                "sic_negative_prefixes": {"871": -0.25, "561": -0.2},
                "keyword_positive": ["software", "cloud", "platform"],
                "keyword_negative": ["care", "restaurant"],
                "keyword_weights": {
                    "positive_per_match": 0.05,
                    "positive_cap": 0.15,
                    "negative_per_match": 0.05,
                    "negative_cap": 0.1,
                },
                "company_status_scores": {
                    "active": 0.1,
                    "inactive": 0.0,
                },
                "company_age_scores": {
                    "unknown": 0.05,
                    "bands": [
                        {"min_years": 10.0, "score": 0.12},
                        {"min_years": 5.0, "score": 0.1},
                        {"min_years": 2.0, "score": 0.07},
                        {"min_years": 1.0, "score": 0.04},
                        {"min_years": 0.0, "score": 0.02},
                    ],
                },
                "company_type_weights": {
                    "ltd": 0.08,
                    "private-limited-company": 0.08,
                    "plc": 0.05,
                },
                "bucket_thresholds": {"strong": 0.55, "possible": 0.35},
            }
        ],
    }


def _first_profile(payload: dict[str, object]) -> dict[str, object]:
    profiles = validate_as(list[dict[str, object]], payload.get("profiles", []))
    profile = dict(profiles[0])
    profiles[0] = profile
    payload["profiles"] = profiles
    return profile


def test_load_scoring_profile_catalog_returns_default_profile() -> None:
    fs = InMemoryFileSystem()
    path = Path("data/reference/scoring_profiles.json")
    fs.write_text(json.dumps(_valid_catalog_payload()), path)

    catalog = load_scoring_profile_catalog(path=path, fs=fs)
    default_profile = resolve_scoring_profile(catalog)

    assert catalog.schema_version == 1
    assert catalog.default_profile == "tech"
    assert default_profile.name == "tech"
    assert default_profile.job_type == "software_engineering"
    assert default_profile.bucket_thresholds.strong == 0.55


def test_load_scoring_profile_catalog_fails_when_path_missing() -> None:
    fs = InMemoryFileSystem()

    with pytest.raises(ScoringProfileFileNotFoundError):
        load_scoring_profile_catalog(path=Path("data/reference/missing.json"), fs=fs)


def test_load_scoring_profile_catalog_fails_for_missing_required_fields() -> None:
    fs = InMemoryFileSystem()
    path = Path("data/reference/scoring_profiles.json")
    payload = _valid_catalog_payload()
    profile = _first_profile(payload)
    profile.pop("keyword_weights")
    fs.write_text(json.dumps(payload), path)

    with pytest.raises(ScoringProfileValidationError) as exc_info:
        load_scoring_profile_catalog(path=path, fs=fs)

    assert "keyword_weights" in str(exc_info.value)


def test_load_scoring_profile_catalog_fails_for_unknown_keys() -> None:
    fs = InMemoryFileSystem()
    path = Path("data/reference/scoring_profiles.json")
    payload = _valid_catalog_payload()
    profile = _first_profile(payload)
    profile["unexpected"] = "value"
    fs.write_text(json.dumps(payload), path)

    with pytest.raises(ScoringProfileValidationError) as exc_info:
        load_scoring_profile_catalog(path=path, fs=fs)

    assert "unexpected" in str(exc_info.value)


def test_load_scoring_profile_catalog_fails_for_wrong_types() -> None:
    fs = InMemoryFileSystem()
    path = Path("data/reference/scoring_profiles.json")
    payload = _valid_catalog_payload()
    profile = _first_profile(payload)
    profile["keyword_positive"] = "software"
    fs.write_text(json.dumps(payload), path)

    with pytest.raises(ScoringProfileValidationError) as exc_info:
        load_scoring_profile_catalog(path=path, fs=fs)

    assert "keyword_positive" in str(exc_info.value)


def test_load_scoring_profile_catalog_fails_for_invalid_ranges() -> None:
    fs = InMemoryFileSystem()
    path = Path("data/reference/scoring_profiles.json")
    payload = _valid_catalog_payload()
    profile = _first_profile(payload)
    keyword_weights = profile["keyword_weights"]
    assert isinstance(keyword_weights, dict)
    keyword_weights["positive_cap"] = 1.5
    fs.write_text(json.dumps(payload), path)

    with pytest.raises(ScoringProfileValidationError) as exc_info:
        load_scoring_profile_catalog(path=path, fs=fs)

    assert "positive_cap" in str(exc_info.value)


def test_resolve_scoring_profile_fails_for_unknown_profile_name() -> None:
    fs = InMemoryFileSystem()
    path = Path("data/reference/scoring_profiles.json")
    fs.write_text(json.dumps(_valid_catalog_payload()), path)

    catalog = load_scoring_profile_catalog(path=path, fs=fs)

    with pytest.raises(ScoringProfileSelectionError) as exc_info:
        resolve_scoring_profile(catalog, profile_name="nonexistent")

    assert "nonexistent" in str(exc_info.value)


def test_default_catalog_includes_non_tech_starter_profile() -> None:
    fs = LocalFileSystem()
    catalog = load_scoring_profile_catalog(
        path=Path("data/reference/scoring_profiles.json"),
        fs=fs,
    )

    non_tech_profiles = [
        profile for profile in catalog.profiles if profile.job_type != "software_engineering"
    ]
    assert non_tech_profiles

    starter_profile = resolve_scoring_profile(catalog, profile_name="care_support")
    assert starter_profile.name == "care_support"
    assert starter_profile.job_type == "care_support"
