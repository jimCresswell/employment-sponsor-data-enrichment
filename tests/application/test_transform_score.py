"""Tests for Transform score scoring."""

import json
from datetime import datetime, tzinfo
from pathlib import Path

import pandas as pd
import pytest

from tests.support.transform_enrich_rows import make_enrich_row
from uk_sponsor_pipeline.application.transform_score import run_transform_score
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.domain import scoring as scoring_domain
from uk_sponsor_pipeline.exceptions import (
    DependencyMissingError,
    InvalidMatchScoreError,
    PipelineConfigMissingError,
    ScoringProfileSelectionError,
)
from uk_sponsor_pipeline.infrastructure import LocalFileSystem
from uk_sponsor_pipeline.schemas import TRANSFORM_SCORE_OUTPUT_COLUMNS


def _write_scoring_profile_catalog(path: Path) -> None:
    payload = {
        "schema_version": 1,
        "default_profile": "tech",
        "profiles": [
            {
                "name": "tech",
                "job_type": "software_engineering",
                "sector_signals": {},
                "location_signals": {},
                "size_signals": {},
                "sic_positive_prefixes": {"620": 0.5},
                "sic_negative_prefixes": {"871": -0.25},
                "keyword_positive": ["software"],
                "keyword_negative": ["care"],
                "keyword_weights": {
                    "positive_per_match": 0.05,
                    "positive_cap": 0.15,
                    "negative_per_match": 0.05,
                    "negative_cap": 0.1,
                },
                "company_status_scores": {"active": 0.1, "inactive": 0.0},
                "company_age_scores": {
                    "unknown": 0.05,
                    "bands": [
                        {"min_years": 1.0, "score": 0.04},
                        {"min_years": 0.0, "score": 0.02},
                    ],
                },
                "company_type_weights": {"ltd": 0.08},
                "bucket_thresholds": {"strong": 0.55, "possible": 0.35},
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_transform_score_sorting_uses_numeric_match_score(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    rows = [
        make_enrich_row(
            **{
                "Organisation Name": "LowMatch",
                "match_score": "2",
            }
        ),
        make_enrich_row(
            **{
                "Organisation Name": "HighMatch",
                "match_score": "10",
            }
        ),
    ]
    df = pd.DataFrame(rows)
    enriched_path = tmp_path / "enriched.csv"
    df.to_csv(enriched_path, index=False)

    outs = run_transform_score(
        enriched_path=enriched_path, out_dir=tmp_path, config=PipelineConfig(), fs=fs
    )
    scored_df = pd.read_csv(outs["scored"], dtype=str).fillna("")

    assert scored_df.loc[0, "Organisation Name"] == "HighMatch"


def test_transform_score_raises_on_non_numeric_match_score(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    row: dict[str, object] = dict(make_enrich_row())
    row["match_score"] = "not-a-number"
    df = pd.DataFrame([row])
    enriched_path = tmp_path / "enriched.csv"
    df.to_csv(enriched_path, index=False)

    with pytest.raises(InvalidMatchScoreError) as exc_info:
        run_transform_score(
            enriched_path=enriched_path, out_dir=tmp_path, config=PipelineConfig(), fs=fs
        )

    message = str(exc_info.value)
    assert "match_score" in message
    assert "numeric" in message


def test_transform_score_requires_config() -> None:
    with pytest.raises(PipelineConfigMissingError) as exc_info:
        run_transform_score()
    assert "PipelineConfig" in str(exc_info.value)


def test_transform_score_requires_filesystem(tmp_path: Path) -> None:
    row: dict[str, object] = dict(make_enrich_row())
    df = pd.DataFrame([row])
    enriched_path = tmp_path / "enriched.csv"
    df.to_csv(enriched_path, index=False)

    with pytest.raises(DependencyMissingError) as exc_info:
        run_transform_score(
            enriched_path=enriched_path,
            out_dir=tmp_path,
            config=PipelineConfig(),
            fs=None,
        )

    assert "FileSystem" in str(exc_info.value)


def test_transform_score_returns_scored_only(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    rows = [make_enrich_row()]
    df = pd.DataFrame(rows)
    enriched_path = tmp_path / "enriched.csv"
    df.to_csv(enriched_path, index=False)

    outs = run_transform_score(
        enriched_path=enriched_path, out_dir=tmp_path, config=PipelineConfig(), fs=fs
    )

    assert set(outs.keys()) == {"scored"}


def test_transform_score_outputs_columns_and_sorting(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    rows = [
        make_enrich_row(
            **{
                "Organisation Name": "Acme Ltd",
                "ch_company_name": "ACME LTD",
                "ch_sic_codes": "62020",
                "match_score": "2",
            }
        ),
        make_enrich_row(
            **{
                "Organisation Name": "Care Services Ltd",
                "org_name_normalised": "care services",
                "ch_company_name": "CARE SERVICES LTD",
                "ch_sic_codes": "87100",
                "match_score": "10",
            }
        ),
    ]
    df = pd.DataFrame(rows)
    enriched_path = tmp_path / "enriched.csv"
    df.to_csv(enriched_path, index=False)

    outs = run_transform_score(
        enriched_path=enriched_path, out_dir=tmp_path, config=PipelineConfig(), fs=fs
    )
    scored_df = pd.read_csv(outs["scored"], dtype=str).fillna("")

    assert list(scored_df.columns) == list(TRANSFORM_SCORE_OUTPUT_COLUMNS)
    assert scored_df.loc[0, "Organisation Name"] == "Acme Ltd"


def test_transform_score_characterises_current_scoring_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fs = LocalFileSystem()

    class FixedDatetime:
        @staticmethod
        def now(tz: tzinfo | None = None) -> datetime:
            return datetime(2026, 2, 10, tzinfo=tz)

    monkeypatch.setattr(scoring_domain, "datetime", FixedDatetime)

    rows = [
        make_enrich_row(
            **{
                "Organisation Name": "Strong Tech Ltd",
                "ch_company_name": "Strong Software Platform Ltd",
                "ch_sic_codes": "62020",
                "ch_company_status": "active",
                "ch_date_of_creation": "2010-01-01",
                "ch_company_type": "ltd",
                "match_score": "0.85",
            }
        ),
        make_enrich_row(
            **{
                "Organisation Name": "Possible Engineering Ltd",
                "ch_company_name": "Engineering Services Ltd",
                "ch_sic_codes": "71100",
                "ch_company_status": "active",
                "ch_date_of_creation": "2023-01-01",
                "ch_company_type": "ltd",
                "match_score": "0.60",
            }
        ),
        make_enrich_row(
            **{
                "Organisation Name": "Unlikely Care Ltd",
                "ch_company_name": "Care Services Ltd",
                "ch_sic_codes": "87100",
                "ch_company_status": "active",
                "ch_date_of_creation": "2024-01-01",
                "ch_company_type": "ltd",
                "match_score": "0.99",
            }
        ),
    ]
    enriched_path = tmp_path / "enriched.csv"
    pd.DataFrame(rows).to_csv(enriched_path, index=False)

    outs = run_transform_score(
        enriched_path=enriched_path, out_dir=tmp_path, config=PipelineConfig(), fs=fs
    )
    scored_df = pd.read_csv(outs["scored"], dtype=str).fillna("")

    assert scored_df["Organisation Name"].tolist() == [
        "Strong Tech Ltd",
        "Possible Engineering Ltd",
        "Unlikely Care Ltd",
    ]

    by_name: dict[str, dict[str, str]] = {}
    for _, row in scored_df.iterrows():
        name = str(row["Organisation Name"])
        by_name[name] = {column: str(row[column]) for column in scored_df.columns}

    def assert_close(actual_text: str, expected: float) -> None:
        actual = float(actual_text)
        assert abs(actual - expected) < 1e-9

    strong = by_name["Strong Tech Ltd"]
    assert_close(strong["sic_tech_score"], 0.5)
    assert_close(strong["is_active_score"], 0.1)
    assert_close(strong["company_age_score"], 0.12)
    assert_close(strong["company_type_score"], 0.08)
    assert_close(strong["name_keyword_score"], 0.1)
    assert_close(strong["role_fit_score"], 0.9)
    assert strong["role_fit_bucket"] == "strong"

    possible = by_name["Possible Engineering Ltd"]
    assert_close(possible["sic_tech_score"], 0.15)
    assert_close(possible["is_active_score"], 0.1)
    assert_close(possible["company_age_score"], 0.07)
    assert_close(possible["company_type_score"], 0.08)
    assert_close(possible["name_keyword_score"], 0.0)
    assert_close(possible["role_fit_score"], 0.4)
    assert possible["role_fit_bucket"] == "possible"

    unlikely = by_name["Unlikely Care Ltd"]
    assert_close(unlikely["sic_tech_score"], 0.0)
    assert_close(unlikely["is_active_score"], 0.1)
    assert_close(unlikely["company_age_score"], 0.07)
    assert_close(unlikely["company_type_score"], 0.08)
    assert_close(unlikely["name_keyword_score"], -0.05)
    assert_close(unlikely["role_fit_score"], 0.2)
    assert unlikely["role_fit_bucket"] == "unlikely"


def test_transform_score_supports_profile_selection_config(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    profile_catalog_path = tmp_path / "scoring_profiles.json"
    _write_scoring_profile_catalog(profile_catalog_path)

    rows = [make_enrich_row()]
    enriched_path = tmp_path / "enriched.csv"
    pd.DataFrame(rows).to_csv(enriched_path, index=False)

    outs = run_transform_score(
        enriched_path=enriched_path,
        out_dir=tmp_path,
        config=PipelineConfig(
            sector_profile_path=str(profile_catalog_path),
            sector_name="tech",
        ),
        fs=fs,
    )

    scored_df = pd.read_csv(outs["scored"], dtype=str).fillna("")
    assert len(scored_df) == 1


def test_transform_score_fails_for_unknown_selected_profile(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    profile_catalog_path = tmp_path / "scoring_profiles.json"
    _write_scoring_profile_catalog(profile_catalog_path)

    rows = [make_enrich_row()]
    enriched_path = tmp_path / "enriched.csv"
    pd.DataFrame(rows).to_csv(enriched_path, index=False)

    with pytest.raises(ScoringProfileSelectionError) as exc_info:
        run_transform_score(
            enriched_path=enriched_path,
            out_dir=tmp_path,
            config=PipelineConfig(
                sector_profile_path=str(profile_catalog_path),
                sector_name="nonexistent",
            ),
            fs=fs,
        )

    assert "nonexistent" in str(exc_info.value)
