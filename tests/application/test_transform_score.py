"""Tests for Transform score scoring."""

from pathlib import Path

import pandas as pd
import pytest

from tests.support.transform_enrich_rows import make_enrich_row
from uk_sponsor_pipeline.application.transform_score import run_transform_score
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.schemas import TRANSFORM_SCORE_OUTPUT_COLUMNS


def test_transform_score_sorting_uses_numeric_match_score(tmp_path: Path) -> None:
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
        enriched_path=enriched_path, out_dir=tmp_path, config=PipelineConfig()
    )
    scored_df = pd.read_csv(outs["scored"], dtype=str).fillna("")

    assert scored_df.loc[0, "Organisation Name"] == "HighMatch"


def test_transform_score_requires_config() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        run_transform_score()
    assert "PipelineConfig" in str(exc_info.value)


def test_transform_score_returns_scored_only(tmp_path: Path) -> None:
    rows = [make_enrich_row()]
    df = pd.DataFrame(rows)
    enriched_path = tmp_path / "enriched.csv"
    df.to_csv(enriched_path, index=False)

    outs = run_transform_score(
        enriched_path=enriched_path, out_dir=tmp_path, config=PipelineConfig()
    )

    assert set(outs.keys()) == {"scored"}


def test_transform_score_outputs_columns_and_sorting(tmp_path: Path) -> None:
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
        enriched_path=enriched_path, out_dir=tmp_path, config=PipelineConfig()
    )
    scored_df = pd.read_csv(outs["scored"], dtype=str).fillna("")

    assert list(scored_df.columns) == list(TRANSFORM_SCORE_OUTPUT_COLUMNS)
    assert scored_df.loc[0, "Organisation Name"] == "Acme Ltd"
