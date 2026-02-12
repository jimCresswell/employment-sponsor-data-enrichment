"""Tests for Transform score scoring."""

import json
from dataclasses import replace
from datetime import datetime, tzinfo
from pathlib import Path

import pandas as pd
import pytest

import uk_sponsor_pipeline.application.transform_score as transform_score_module
from tests.support.transform_enrich_rows import make_enrich_row
from uk_sponsor_pipeline.application.transform_score import run_transform_score
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.domain import scoring as scoring_domain
from uk_sponsor_pipeline.exceptions import (
    DependencyMissingError,
    EmployeeCountSnapshotError,
    InvalidMatchScoreError,
    PipelineConfigMissingError,
    ScoringProfileSelectionError,
    SnapshotNotFoundError,
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


def _write_default_custom_scoring_profile_catalog(path: Path) -> None:
    payload = {
        "schema_version": 1,
        "default_profile": "strict",
        "profiles": [
            {
                "name": "strict",
                "job_type": "software_engineering",
                "sector_signals": {},
                "location_signals": {},
                "size_signals": {},
                "sic_positive_prefixes": {},
                "sic_negative_prefixes": {"620": -0.1},
                "keyword_positive": [],
                "keyword_negative": ["software"],
                "keyword_weights": {
                    "positive_per_match": 0.05,
                    "positive_cap": 0.15,
                    "negative_per_match": 0.3,
                    "negative_cap": 0.3,
                },
                "company_status_scores": {"active": 0.0, "inactive": -0.2},
                "company_age_scores": {
                    "unknown": 0.0,
                    "bands": [
                        {"min_years": 0.0, "score": 0.0},
                    ],
                },
                "company_type_weights": {"ltd": 0.0},
                "bucket_thresholds": {"strong": 0.9, "possible": 0.8},
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_contrast_scoring_profile_catalog(path: Path) -> None:
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
                        {"min_years": 10.0, "score": 0.12},
                        {"min_years": 0.0, "score": 0.02},
                    ],
                },
                "company_type_weights": {"ltd": 0.08},
                "bucket_thresholds": {"strong": 0.55, "possible": 0.35},
            },
            {
                "name": "strict_custom",
                "job_type": "software_engineering",
                "sector_signals": {},
                "location_signals": {},
                "size_signals": {},
                "sic_positive_prefixes": {"620": 0.05},
                "sic_negative_prefixes": {"620": -0.1},
                "keyword_positive": ["care"],
                "keyword_negative": ["software"],
                "keyword_weights": {
                    "positive_per_match": 0.01,
                    "positive_cap": 0.01,
                    "negative_per_match": 0.2,
                    "negative_cap": 0.2,
                },
                "company_status_scores": {"active": 0.0, "inactive": -0.1},
                "company_age_scores": {
                    "unknown": 0.0,
                    "bands": [
                        {"min_years": 10.0, "score": 0.02},
                        {"min_years": 0.0, "score": 0.01},
                    ],
                },
                "company_type_weights": {"ltd": 0.0},
                "bucket_thresholds": {"strong": 0.8, "possible": 0.6},
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_employee_count_snapshot(
    *,
    snapshot_root: Path,
    rows: list[dict[str, str]] | None = None,
    snapshot_date: str = "2026-02-06",
) -> Path:
    snapshot_dir = snapshot_root / "employee_count" / snapshot_date
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    clean_rows = rows or [
        {
            "company_number": "12345678",
            "employee_count": "1200",
            "employee_count_source": "ons_business_register",
            "employee_count_snapshot_date": snapshot_date,
        }
    ]
    pd.DataFrame(clean_rows).to_csv(snapshot_dir / "clean.csv", index=False)
    pd.DataFrame(
        [
            {"company_number": row["company_number"], "employees": row["employee_count"]}
            for row in clean_rows
        ]
    ).to_csv(snapshot_dir / "raw.csv", index=False)
    manifest = {
        "dataset": "employee_count",
        "snapshot_date": snapshot_date,
        "source_url": "https://example.com/employee_count.csv",
        "downloaded_at_utc": "2026-02-06T12:00:00+00:00",
        "last_updated_at_utc": "2026-02-06T12:05:00+00:00",
        "schema_version": "employee_count_v1",
        "sha256_hash_raw": "rawhash",
        "sha256_hash_clean": "cleanhash",
        "bytes_raw": 128,
        "row_counts": {"raw": len(clean_rows), "clean": len(clean_rows)},
        "artefacts": {"raw": "raw.csv", "clean": "clean.csv", "manifest": "manifest.json"},
        "git_sha": "abc123",
        "tool_version": "0.1.0",
        "command_line": "uk-sponsor refresh-employee-count",
    }
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return snapshot_root


def _config_with_employee_count_snapshot(
    *,
    tmp_path: Path,
    base: PipelineConfig | None = None,
) -> PipelineConfig:
    snapshot_root = _write_employee_count_snapshot(snapshot_root=tmp_path / "snapshots")
    config = base or PipelineConfig()
    return replace(config, snapshot_root=str(snapshot_root))


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

    config = _config_with_employee_count_snapshot(tmp_path=tmp_path)
    outs = run_transform_score(enriched_path=enriched_path, out_dir=tmp_path, config=config, fs=fs)
    scored_df = pd.read_csv(outs["scored"], dtype=str).fillna("")

    assert scored_df.loc[0, "Organisation Name"] == "HighMatch"


def test_transform_score_raises_on_non_numeric_match_score(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    row: dict[str, object] = dict(make_enrich_row())
    row["match_score"] = "not-a-number"
    df = pd.DataFrame([row])
    enriched_path = tmp_path / "enriched.csv"
    df.to_csv(enriched_path, index=False)

    config = _config_with_employee_count_snapshot(tmp_path=tmp_path)
    with pytest.raises(InvalidMatchScoreError) as exc_info:
        run_transform_score(enriched_path=enriched_path, out_dir=tmp_path, config=config, fs=fs)

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

    config = _config_with_employee_count_snapshot(tmp_path=tmp_path)
    outs = run_transform_score(enriched_path=enriched_path, out_dir=tmp_path, config=config, fs=fs)

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

    config = _config_with_employee_count_snapshot(tmp_path=tmp_path)
    outs = run_transform_score(enriched_path=enriched_path, out_dir=tmp_path, config=config, fs=fs)
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

    config = _config_with_employee_count_snapshot(tmp_path=tmp_path)
    outs = run_transform_score(enriched_path=enriched_path, out_dir=tmp_path, config=config, fs=fs)
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

    base_config = PipelineConfig(
        sector_profile_path=str(profile_catalog_path),
        sector_name="tech",
    )
    config = _config_with_employee_count_snapshot(tmp_path=tmp_path, base=base_config)
    outs = run_transform_score(
        enriched_path=enriched_path,
        out_dir=tmp_path,
        config=config,
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

    base_config = PipelineConfig(
        sector_profile_path=str(profile_catalog_path),
        sector_name="nonexistent",
    )
    config = _config_with_employee_count_snapshot(tmp_path=tmp_path, base=base_config)
    with pytest.raises(ScoringProfileSelectionError) as exc_info:
        run_transform_score(
            enriched_path=enriched_path,
            out_dir=tmp_path,
            config=config,
            fs=fs,
        )

    assert "nonexistent" in str(exc_info.value)


def test_transform_score_uses_default_profile_catalog_without_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fs = LocalFileSystem()
    default_profile_path = tmp_path / "default_scoring_profiles.json"
    _write_default_custom_scoring_profile_catalog(default_profile_path)
    monkeypatch.setattr(
        transform_score_module, "DEFAULT_SCORING_PROFILE_PATH", default_profile_path
    )

    rows = [
        make_enrich_row(
            **{
                "Organisation Name": "Default Profile Company",
                "ch_company_name": "Software Platform Ltd",
                "ch_sic_codes": "62020",
                "ch_company_status": "active",
                "ch_date_of_creation": "2010-01-01",
                "ch_company_type": "ltd",
                "match_score": "0.8",
            }
        )
    ]
    enriched_path = tmp_path / "enriched.csv"
    pd.DataFrame(rows).to_csv(enriched_path, index=False)

    config = _config_with_employee_count_snapshot(tmp_path=tmp_path)
    outs = run_transform_score(
        enriched_path=enriched_path,
        out_dir=tmp_path,
        config=config,
        fs=fs,
    )

    scored_df = pd.read_csv(outs["scored"], dtype=str).fillna("")
    assert scored_df.loc[0, "role_fit_bucket"] == "unlikely"
    assert float(str(scored_df.loc[0, "role_fit_score"])) == 0.0


def test_transform_score_custom_profile_changes_output_deterministically(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    profile_catalog_path = tmp_path / "scoring_profiles.json"
    _write_contrast_scoring_profile_catalog(profile_catalog_path)

    rows = [
        make_enrich_row(
            **{
                "Organisation Name": "Profile Switch Company",
                "ch_company_name": "Software Platform Ltd",
                "ch_sic_codes": "62020",
                "ch_company_status": "active",
                "ch_date_of_creation": "2010-01-01",
                "ch_company_type": "ltd",
                "match_score": "0.85",
            }
        )
    ]
    enriched_path = tmp_path / "enriched.csv"
    pd.DataFrame(rows).to_csv(enriched_path, index=False)

    tech_config = _config_with_employee_count_snapshot(
        tmp_path=tmp_path / "tech",
        base=PipelineConfig(
            sector_profile_path=str(profile_catalog_path),
            sector_name="tech",
        ),
    )
    custom_config = _config_with_employee_count_snapshot(
        tmp_path=tmp_path / "custom",
        base=PipelineConfig(
            sector_profile_path=str(profile_catalog_path),
            sector_name="strict_custom",
        ),
    )
    tech_out = run_transform_score(
        enriched_path=enriched_path,
        out_dir=tmp_path / "tech_out",
        config=tech_config,
        fs=fs,
    )
    custom_out_first = run_transform_score(
        enriched_path=enriched_path,
        out_dir=tmp_path / "custom_out_first",
        config=custom_config,
        fs=fs,
    )
    custom_out_second = run_transform_score(
        enriched_path=enriched_path,
        out_dir=tmp_path / "custom_out_second",
        config=custom_config,
        fs=fs,
    )

    tech_df = pd.read_csv(tech_out["scored"], dtype=str).fillna("")
    custom_df_first = pd.read_csv(custom_out_first["scored"], dtype=str).fillna("")
    custom_df_second = pd.read_csv(custom_out_second["scored"], dtype=str).fillna("")

    tech_score = float(str(tech_df.loc[0, "role_fit_score"]))
    custom_score_first = float(str(custom_df_first.loc[0, "role_fit_score"]))
    custom_score_second = float(str(custom_df_second.loc[0, "role_fit_score"]))
    tech_bucket = str(tech_df.loc[0, "role_fit_bucket"])
    custom_bucket_first = str(custom_df_first.loc[0, "role_fit_bucket"])
    custom_bucket_second = str(custom_df_second.loc[0, "role_fit_bucket"])

    assert tech_score > custom_score_first
    assert tech_bucket == "strong"
    assert custom_bucket_first == "unlikely"
    assert custom_score_first == custom_score_second
    assert custom_bucket_first == custom_bucket_second


def test_transform_score_non_tech_starter_profile_is_selectable_and_deterministic(
    tmp_path: Path,
) -> None:
    fs = LocalFileSystem()
    rows = [
        make_enrich_row(
            **{
                "Organisation Name": "Care Starter Company",
                "ch_company_name": "Care Nursing Services Ltd",
                "ch_sic_codes": "87100",
                "ch_company_status": "active",
                "ch_date_of_creation": "2010-01-01",
                "ch_company_type": "ltd",
                "match_score": "0.85",
            }
        )
    ]
    enriched_path = tmp_path / "enriched.csv"
    pd.DataFrame(rows).to_csv(enriched_path, index=False)

    tech_config = _config_with_employee_count_snapshot(
        tmp_path=tmp_path / "tech",
        base=PipelineConfig(sector_name="tech"),
    )
    care_config = _config_with_employee_count_snapshot(
        tmp_path=tmp_path / "care",
        base=PipelineConfig(sector_name="care_support"),
    )
    tech_out = run_transform_score(
        enriched_path=enriched_path,
        out_dir=tmp_path / "tech_out",
        config=tech_config,
        fs=fs,
    )
    care_out_first = run_transform_score(
        enriched_path=enriched_path,
        out_dir=tmp_path / "care_out_first",
        config=care_config,
        fs=fs,
    )
    care_out_second = run_transform_score(
        enriched_path=enriched_path,
        out_dir=tmp_path / "care_out_second",
        config=care_config,
        fs=fs,
    )

    tech_df = pd.read_csv(tech_out["scored"], dtype=str).fillna("")
    care_df_first = pd.read_csv(care_out_first["scored"], dtype=str).fillna("")
    care_df_second = pd.read_csv(care_out_second["scored"], dtype=str).fillna("")

    tech_score = float(str(tech_df.loc[0, "role_fit_score"]))
    care_score_first = float(str(care_df_first.loc[0, "role_fit_score"]))
    care_score_second = float(str(care_df_second.loc[0, "role_fit_score"]))
    tech_bucket = str(tech_df.loc[0, "role_fit_bucket"])
    care_bucket_first = str(care_df_first.loc[0, "role_fit_bucket"])
    care_bucket_second = str(care_df_second.loc[0, "role_fit_bucket"])

    assert tech_bucket == "unlikely"
    assert care_bucket_first == "strong"
    assert care_score_first > tech_score
    assert care_score_first == care_score_second
    assert care_bucket_first == care_bucket_second


def test_transform_score_joins_employee_count_fields_by_company_number(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = _write_employee_count_snapshot(
        snapshot_root=tmp_path / "snapshots",
        rows=[
            {
                "company_number": "12345678",
                "employee_count": "1200",
                "employee_count_source": "ons_business_register",
                "employee_count_snapshot_date": "2026-02-06",
            }
        ],
    )
    enriched_path = tmp_path / "enriched.csv"
    pd.DataFrame(
        [
            make_enrich_row(
                **{"Organisation Name": "Matched Company", "ch_company_number": "12345678"}
            ),
            make_enrich_row(
                **{"Organisation Name": "Unknown Company", "ch_company_number": "99999999"}
            ),
        ]
    ).to_csv(enriched_path, index=False)

    outs = run_transform_score(
        enriched_path=enriched_path,
        out_dir=tmp_path,
        config=PipelineConfig(snapshot_root=str(snapshot_root)),
        fs=fs,
    )
    scored_df = pd.read_csv(outs["scored"], dtype=str).fillna("")
    by_name = {
        str(row["Organisation Name"]): {column: str(row[column]) for column in scored_df.columns}
        for _, row in scored_df.iterrows()
    }

    matched = by_name["Matched Company"]
    assert matched["employee_count"] == "1200"
    assert matched["employee_count_source"] == "ons_business_register"
    assert matched["employee_count_snapshot_date"] == "2026-02-06"

    unknown = by_name["Unknown Company"]
    assert unknown["employee_count"] == ""
    assert unknown["employee_count_source"] == ""
    assert unknown["employee_count_snapshot_date"] == ""


def test_transform_score_employee_count_join_is_deterministic(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = _write_employee_count_snapshot(snapshot_root=tmp_path / "snapshots")
    enriched_path = tmp_path / "enriched.csv"
    pd.DataFrame([make_enrich_row()]).to_csv(enriched_path, index=False)
    config = PipelineConfig(snapshot_root=str(snapshot_root))

    first_out = run_transform_score(
        enriched_path=enriched_path,
        out_dir=tmp_path / "first",
        config=config,
        fs=fs,
    )
    second_out = run_transform_score(
        enriched_path=enriched_path,
        out_dir=tmp_path / "second",
        config=config,
        fs=fs,
    )

    first_text = Path(first_out["scored"]).read_text(encoding="utf-8")
    second_text = Path(second_out["scored"]).read_text(encoding="utf-8")
    assert first_text == second_text


def test_transform_score_fails_fast_when_employee_count_snapshot_missing(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    enriched_path = tmp_path / "enriched.csv"
    pd.DataFrame([make_enrich_row()]).to_csv(enriched_path, index=False)
    config = PipelineConfig(snapshot_root=str(tmp_path / "missing_snapshots"))

    with pytest.raises(SnapshotNotFoundError):
        run_transform_score(
            enriched_path=enriched_path,
            out_dir=tmp_path,
            config=config,
            fs=fs,
        )


def test_transform_score_fails_fast_for_invalid_employee_count_value(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    _write_employee_count_snapshot(
        snapshot_root=tmp_path / "snapshots",
        rows=[
            {
                "company_number": "12345678",
                "employee_count": "not-a-number",
                "employee_count_source": "ons_business_register",
                "employee_count_snapshot_date": "2026-02-06",
            }
        ],
    )
    enriched_path = tmp_path / "enriched.csv"
    pd.DataFrame([make_enrich_row()]).to_csv(enriched_path, index=False)
    config = PipelineConfig(snapshot_root=str(tmp_path / "snapshots"))

    with pytest.raises(EmployeeCountSnapshotError, match="employee_count"):
        run_transform_score(
            enriched_path=enriched_path,
            out_dir=tmp_path,
            config=config,
            fs=fs,
        )
