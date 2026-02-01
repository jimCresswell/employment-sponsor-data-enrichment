"""Characterisation tests for Stage 3 outputs."""

from pathlib import Path

import pandas as pd

from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.schemas import (
    STAGE2_ENRICHED_COLUMNS,
    STAGE3_EXPLAIN_COLUMNS,
    STAGE3_SCORED_COLUMNS,
)
from uk_sponsor_pipeline.stages.stage3_scoring import run_stage3


def _stage2_row(**overrides: str) -> dict[str, str]:
    row = {col: "" for col in STAGE2_ENRICHED_COLUMNS}
    row.update(
        {
            "Organisation Name": "Acme Ltd",
            "org_name_normalized": "acme",
            "has_multiple_towns": "False",
            "has_multiple_counties": "False",
            "Town/City": "London",
            "County": "Greater London",
            "Type & Rating": "A rating",
            "Route": "Skilled Worker",
            "raw_name_variants": "Acme Ltd",
            "match_status": "matched",
            "match_score": "0.9",
            "match_confidence": "high",
            "match_query_used": "Acme Ltd",
            "ch_company_number": "12345678",
            "ch_company_name": "ACME LTD",
            "ch_company_status": "active",
            "ch_company_type": "ltd",
            "ch_date_of_creation": "2015-01-01",
            "ch_sic_codes": "62020",
            "ch_address_locality": "London",
            "ch_address_region": "Greater London",
            "ch_address_postcode": "EC1A 1BB",
        }
    )
    row.update(overrides)
    return row


def test_stage3_outputs_are_deterministic(in_memory_fs) -> None:
    stage2_path = Path("data/processed/stage2_enriched_companies_house.csv")
    out_dir = Path("data/processed")

    df = pd.DataFrame(
        [
            _stage2_row(),
            _stage2_row(
                **{
                    "Organisation Name": "Care Services Ltd",
                    "org_name_normalized": "care services",
                    "match_score": "0.4",
                    "ch_company_name": "CARE SERVICES LTD",
                    "ch_sic_codes": "87100",
                }
            ),
        ]
    )
    in_memory_fs.write_csv(df, stage2_path)

    outputs = run_stage3(
        stage2_path=stage2_path,
        out_dir=out_dir,
        config=PipelineConfig(),
        fs=in_memory_fs,
    )

    scored_df = in_memory_fs.read_csv(outputs["scored"])
    shortlist_df = in_memory_fs.read_csv(outputs["shortlist"])
    explain_df = in_memory_fs.read_csv(outputs["explain"])

    assert list(scored_df.columns) == list(STAGE3_SCORED_COLUMNS)
    assert scored_df.loc[0, "Organisation Name"] == "Acme Ltd"

    assert list(shortlist_df.columns) == list(STAGE3_SCORED_COLUMNS)
    assert shortlist_df["Organisation Name"].tolist() == ["Acme Ltd"]

    assert list(explain_df.columns) == list(STAGE3_EXPLAIN_COLUMNS)
    assert explain_df["Organisation Name"].tolist() == ["Acme Ltd"]
