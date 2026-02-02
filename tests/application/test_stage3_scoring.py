"""Tests for Stage 3 scoring."""

import json
from pathlib import Path

import pandas as pd
import pytest

from tests.support.stage2_rows import make_stage2_row
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.stages.stage3_scoring import run_stage3


def test_stage3_geographic_filter(tmp_path: Path) -> None:
    rows = [
        make_stage2_row(
            **{
                "Organisation Name": "London Tech",
                "ch_address_region": "Greater London",
                "ch_address_locality": "London",
                "ch_address_postcode": "EC1A 1BB",
            }
        ),
        make_stage2_row(
            **{
                "Organisation Name": "Manchester Tech",
                "ch_address_region": "Greater Manchester",
                "ch_address_locality": "Manchester",
                "ch_address_postcode": "M1 1AA",
            }
        ),
    ]
    df = pd.DataFrame(rows)
    stage2_path = tmp_path / "stage2.csv"
    df.to_csv(stage2_path, index=False)

    config = PipelineConfig(geo_filter_region="London")
    outs = run_stage3(stage2_path=stage2_path, out_dir=tmp_path, config=config)

    shortlist_df = pd.read_csv(outs["shortlist"], dtype=str).fillna("")
    assert shortlist_df["Organisation Name"].tolist() == ["London Tech"]


def test_stage3_sorting_uses_numeric_match_score(tmp_path: Path) -> None:
    rows = [
        make_stage2_row(
            **{
                "Organisation Name": "LowMatch",
                "match_score": "2",
            }
        ),
        make_stage2_row(
            **{
                "Organisation Name": "HighMatch",
                "match_score": "10",
            }
        ),
    ]
    df = pd.DataFrame(rows)
    stage2_path = tmp_path / "stage2.csv"
    df.to_csv(stage2_path, index=False)

    outs = run_stage3(stage2_path=stage2_path, out_dir=tmp_path, config=PipelineConfig())
    scored_df = pd.read_csv(outs["scored"], dtype=str).fillna("")

    assert scored_df.loc[0, "Organisation Name"] == "HighMatch"


def test_stage3_geographic_filter_uses_aliases(tmp_path: Path) -> None:
    rows = [
        make_stage2_row(
            **{
                "Organisation Name": "Salford Tech",
                "ch_address_region": "Lancashire",
                "ch_address_locality": "Salford",
                "ch_address_postcode": "M1 1AA",
            }
        ),
        make_stage2_row(
            **{
                "Organisation Name": "Leeds Tech",
                "ch_address_region": "West Yorkshire",
                "ch_address_locality": "Leeds",
                "ch_address_postcode": "LS1 1AA",
            }
        ),
    ]
    df = pd.DataFrame(rows)
    stage2_path = tmp_path / "stage2.csv"
    df.to_csv(stage2_path, index=False)

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
    outs = run_stage3(stage2_path=stage2_path, out_dir=tmp_path, config=config)

    shortlist_df = pd.read_csv(outs["shortlist"], dtype=str).fillna("")
    assert shortlist_df["Organisation Name"].tolist() == ["Salford Tech"]


def test_stage3_requires_config() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        run_stage3()
    assert "PipelineConfig" in str(exc_info.value)
