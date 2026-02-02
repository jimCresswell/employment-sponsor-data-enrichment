"""Tests for usage shortlist filtering."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tests.support.transform_score_rows import make_scored_row
from uk_sponsor_pipeline.application.usage import run_usage_shortlist
from uk_sponsor_pipeline.config import PipelineConfig
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
    with pytest.raises(RuntimeError) as exc_info:
        run_usage_shortlist()
    assert "PipelineConfig" in str(exc_info.value)


def test_usage_shortlist_requires_filesystem(tmp_path: Path) -> None:
    rows = [make_scored_row()]
    df = pd.DataFrame(rows)
    scored_path = tmp_path / "scored.csv"
    df.to_csv(scored_path, index=False)

    with pytest.raises(RuntimeError) as exc_info:
        run_usage_shortlist(
            scored_path=scored_path,
            out_dir=tmp_path,
            config=PipelineConfig(),
            fs=None,
        )

    assert "FileSystem" in str(exc_info.value)
