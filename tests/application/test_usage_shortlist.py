"""Tests for usage shortlist filtering."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tests.support.transform_score_rows import make_scored_row
from uk_sponsor_pipeline.application.usage import run_usage_shortlist
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.exceptions import (
    DependencyMissingError,
    InvalidEmployeeCountError,
    PipelineConfigMissingError,
)
from uk_sponsor_pipeline.infrastructure import LocalFileSystem


def test_usage_shortlist_filters_by_threshold_and_bucket(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    rows = [
        make_scored_row(
            **{
                "Organisation Name": "Strong Co",
                "role_fit_score": 0.7,
                "role_fit_bucket": "strong",
            }
        ),
        make_scored_row(
            **{
                "Organisation Name": "Possible Low",
                "role_fit_score": 0.4,
                "role_fit_bucket": "possible",
            }
        ),
        make_scored_row(
            **{
                "Organisation Name": "Possible High",
                "role_fit_score": 0.6,
                "role_fit_bucket": "possible",
            }
        ),
        make_scored_row(
            **{
                "Organisation Name": "Unlikely High",
                "role_fit_score": 0.9,
                "role_fit_bucket": "unlikely",
            }
        ),
    ]
    df = pd.DataFrame(rows)
    scored_path = tmp_path / "scored.csv"
    df.to_csv(scored_path, index=False)

    config = PipelineConfig(tech_score_threshold=0.5)
    outs = run_usage_shortlist(scored_path=scored_path, out_dir=tmp_path, config=config, fs=fs)

    shortlist_df = pd.read_csv(outs["shortlist"], dtype=str).fillna("")
    assert shortlist_df["Organisation Name"].tolist() == ["Strong Co", "Possible High"]


def test_usage_shortlist_filters_by_employee_count_excluding_unknown_by_default(
    tmp_path: Path,
) -> None:
    fs = LocalFileSystem()
    rows = [
        make_scored_row(
            **{
                "Organisation Name": "Large Co",
                "role_fit_score": 0.8,
                "role_fit_bucket": "strong",
                "employee_count": "1200",
            }
        ),
        make_scored_row(
            **{
                "Organisation Name": "Small Co",
                "role_fit_score": 0.8,
                "role_fit_bucket": "strong",
                "employee_count": "200",
            }
        ),
        make_scored_row(
            **{
                "Organisation Name": "Unknown Co",
                "role_fit_score": 0.8,
                "role_fit_bucket": "strong",
                "employee_count": "",
            }
        ),
    ]
    scored_path = tmp_path / "scored.csv"
    pd.DataFrame(rows).to_csv(scored_path, index=False)

    config = PipelineConfig(tech_score_threshold=0.5, min_employee_count=1000)
    outs = run_usage_shortlist(scored_path=scored_path, out_dir=tmp_path, config=config, fs=fs)

    shortlist_df = pd.read_csv(outs["shortlist"], dtype=str).fillna("")
    assert shortlist_df["Organisation Name"].tolist() == ["Large Co"]


def test_usage_shortlist_filters_by_employee_count_can_include_unknown(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    rows = [
        make_scored_row(
            **{
                "Organisation Name": "Large Co",
                "role_fit_score": 0.8,
                "role_fit_bucket": "strong",
                "employee_count": "1200",
            }
        ),
        make_scored_row(
            **{
                "Organisation Name": "Unknown Co",
                "role_fit_score": 0.8,
                "role_fit_bucket": "strong",
                "employee_count": "",
            }
        ),
        make_scored_row(
            **{
                "Organisation Name": "Small Co",
                "role_fit_score": 0.8,
                "role_fit_bucket": "strong",
                "employee_count": "200",
            }
        ),
    ]
    scored_path = tmp_path / "scored.csv"
    pd.DataFrame(rows).to_csv(scored_path, index=False)

    config = PipelineConfig(
        tech_score_threshold=0.5,
        min_employee_count=1000,
        include_unknown_employee_count=True,
    )
    outs = run_usage_shortlist(scored_path=scored_path, out_dir=tmp_path, config=config, fs=fs)

    shortlist_df = pd.read_csv(outs["shortlist"], dtype=str).fillna("")
    assert shortlist_df["Organisation Name"].tolist() == ["Large Co", "Unknown Co"]


def test_usage_shortlist_employee_count_filter_fails_for_invalid_values(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    rows = [
        make_scored_row(
            **{
                "Organisation Name": "Invalid Count Co",
                "role_fit_score": 0.8,
                "role_fit_bucket": "strong",
                "employee_count": "abc",
            }
        )
    ]
    scored_path = tmp_path / "scored.csv"
    pd.DataFrame(rows).to_csv(scored_path, index=False)
    config = PipelineConfig(tech_score_threshold=0.5, min_employee_count=1000)

    with pytest.raises(InvalidEmployeeCountError) as exc_info:
        run_usage_shortlist(scored_path=scored_path, out_dir=tmp_path, config=config, fs=fs)

    assert "employee_count" in str(exc_info.value)
    assert "abc" in str(exc_info.value)


def test_usage_shortlist_employee_count_filter_is_deterministic(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    rows = [
        make_scored_row(
            **{
                "Organisation Name": "Large B",
                "role_fit_score": 0.8,
                "role_fit_bucket": "strong",
                "employee_count": "2500",
            }
        ),
        make_scored_row(
            **{
                "Organisation Name": "Unknown Co",
                "role_fit_score": 0.8,
                "role_fit_bucket": "strong",
                "employee_count": "",
            }
        ),
        make_scored_row(
            **{
                "Organisation Name": "Large A",
                "role_fit_score": 0.8,
                "role_fit_bucket": "strong",
                "employee_count": "1100",
            }
        ),
        make_scored_row(
            **{
                "Organisation Name": "Small Co",
                "role_fit_score": 0.8,
                "role_fit_bucket": "strong",
                "employee_count": "80",
            }
        ),
    ]
    scored_path = tmp_path / "scored.csv"
    pd.DataFrame(rows).to_csv(scored_path, index=False)
    config = PipelineConfig(
        tech_score_threshold=0.5,
        min_employee_count=1000,
        include_unknown_employee_count=True,
    )

    first_outs = run_usage_shortlist(
        scored_path=scored_path,
        out_dir=tmp_path / "run1",
        config=config,
        fs=fs,
    )
    second_outs = run_usage_shortlist(
        scored_path=scored_path,
        out_dir=tmp_path / "run2",
        config=config,
        fs=fs,
    )

    first_names = (
        pd.read_csv(first_outs["shortlist"], dtype=str).fillna("")["Organisation Name"].tolist()
    )
    second_names = (
        pd.read_csv(second_outs["shortlist"], dtype=str).fillna("")["Organisation Name"].tolist()
    )
    assert first_names == ["Large B", "Unknown Co", "Large A"]
    assert second_names == first_names


def test_usage_shortlist_explain_includes_employee_count_provenance(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    rows = [
        make_scored_row(
            **{
                "Organisation Name": "Large Co",
                "role_fit_score": 0.8,
                "role_fit_bucket": "strong",
                "employee_count": "1200",
                "employee_count_source": "ons_bres_2024",
                "employee_count_snapshot_date": "2026-02-06",
            }
        )
    ]
    scored_path = tmp_path / "scored.csv"
    pd.DataFrame(rows).to_csv(scored_path, index=False)

    outs = run_usage_shortlist(
        scored_path=scored_path,
        out_dir=tmp_path,
        config=PipelineConfig(tech_score_threshold=0.5),
        fs=fs,
    )

    explain_df = pd.read_csv(outs["explain"], dtype=str).fillna("")
    assert "employee_count" in explain_df.columns
    assert "employee_count_source" in explain_df.columns
    assert "employee_count_snapshot_date" in explain_df.columns
    assert explain_df["employee_count"].tolist() == ["1200"]
    assert explain_df["employee_count_source"].tolist() == ["ons_bres_2024"]
    assert explain_df["employee_count_snapshot_date"].tolist() == ["2026-02-06"]


def test_usage_shortlist_geographic_filter_uses_aliases(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    rows = [
        make_scored_row(
            **{
                "Organisation Name": "Salford Tech",
                "ch_address_region": "Lancashire",
                "ch_address_locality": "Salford",
                "ch_address_postcode": "M1 1AA",
            }
        ),
        make_scored_row(
            **{
                "Organisation Name": "Leeds Tech",
                "ch_address_region": "West Yorkshire",
                "ch_address_locality": "Leeds",
                "ch_address_postcode": "LS1 1AA",
            }
        ),
    ]
    df = pd.DataFrame(rows)
    scored_path = tmp_path / "scored.csv"
    df.to_csv(scored_path, index=False)

    aliases_path = tmp_path / "data" / "reference" / "location_aliases.json"
    aliases_path.parent.mkdir(parents=True, exist_ok=True)
    aliases_path.write_text(
        json.dumps(
            {
                "locations": [
                    {
                        "canonical_name": "Manchester",
                        "aliases": ["Manchester", "Greater Manchester"],
                        "regions": ["Greater Manchester"],
                        "localities": ["Salford"],
                        "postcode_prefixes": ["M"],
                        "notes": "Test profile.",
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    config = PipelineConfig(
        geo_filter_region="Manchester",
        location_aliases_path=str(aliases_path),
    )
    outs = run_usage_shortlist(scored_path=scored_path, out_dir=tmp_path, config=config, fs=fs)

    shortlist_df = pd.read_csv(outs["shortlist"], dtype=str).fillna("")
    assert shortlist_df["Organisation Name"].tolist() == ["Salford Tech"]


def test_usage_shortlist_requires_config() -> None:
    with pytest.raises(PipelineConfigMissingError) as exc_info:
        run_usage_shortlist()
    assert "PipelineConfig" in str(exc_info.value)


def test_usage_shortlist_requires_filesystem(tmp_path: Path) -> None:
    rows = [make_scored_row()]
    df = pd.DataFrame(rows)
    scored_path = tmp_path / "scored.csv"
    df.to_csv(scored_path, index=False)

    with pytest.raises(DependencyMissingError) as exc_info:
        run_usage_shortlist(
            scored_path=scored_path,
            out_dir=tmp_path,
            config=PipelineConfig(),
            fs=None,
        )

    assert "FileSystem" in str(exc_info.value)
