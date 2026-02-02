"""Tests for Stage 3 scoring."""

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


def test_stage3_requires_config() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        run_stage3()
    assert "PipelineConfig" in str(exc_info.value)
