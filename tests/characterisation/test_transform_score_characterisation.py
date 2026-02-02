"""Characterisation tests for Transform score outputs."""

from pathlib import Path

import pandas as pd

from tests.fakes import InMemoryFileSystem
from uk_sponsor_pipeline.application.transform_score import run_transform_score
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.infrastructure.io.validation import validate_as
from uk_sponsor_pipeline.schemas import (
    TRANSFORM_SCORE_EXPLAIN_COLUMNS,
    TRANSFORM_SCORE_OUTPUT_COLUMNS,
)
from uk_sponsor_pipeline.types import TransformEnrichRow


def _transform_enrich_row(**overrides: str | float) -> TransformEnrichRow:
    row: TransformEnrichRow = {
        "Organisation Name": "Acme Ltd",
        "org_name_normalised": "acme",
        "has_multiple_towns": "False",
        "has_multiple_counties": "False",
        "Town/City": "London",
        "County": "Greater London",
        "Type & Rating": "A rating",
        "Route": "Skilled Worker",
        "raw_name_variants": "Acme Ltd",
        "match_status": "matched",
        "match_score": 0.9,
        "match_confidence": "high",
        "match_query_used": "Acme Ltd",
        "score_name_similarity": 0.8,
        "score_locality_bonus": 0.1,
        "score_region_bonus": 0.05,
        "score_status_bonus": 0.1,
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
    merged = {**row, **overrides}
    return validate_as(TransformEnrichRow, merged)


def test_transform_score_outputs_are_deterministic(in_memory_fs: InMemoryFileSystem) -> None:
    enriched_path = Path("data/processed/companies_house_enriched.csv")
    out_dir = Path("data/processed")

    df = pd.DataFrame(
        [
            _transform_enrich_row(),
            _transform_enrich_row(
                **{
                    "Organisation Name": "Care Services Ltd",
                    "org_name_normalised": "care services",
                    "match_score": 0.4,
                    "ch_company_name": "CARE SERVICES LTD",
                    "ch_sic_codes": "87100",
                }
            ),
        ]
    )
    in_memory_fs.write_csv(df, enriched_path)

    outputs = run_transform_score(
        enriched_path=enriched_path,
        out_dir=out_dir,
        config=PipelineConfig(),
        fs=in_memory_fs,
    )

    scored_df = in_memory_fs.read_csv(outputs["scored"])
    shortlist_df = in_memory_fs.read_csv(outputs["shortlist"])
    explain_df = in_memory_fs.read_csv(outputs["explain"])

    assert list(scored_df.columns) == list(TRANSFORM_SCORE_OUTPUT_COLUMNS)
    assert scored_df.loc[0, "Organisation Name"] == "Acme Ltd"

    assert list(shortlist_df.columns) == list(TRANSFORM_SCORE_OUTPUT_COLUMNS)
    assert shortlist_df["Organisation Name"].tolist() == ["Acme Ltd"]

    assert list(explain_df.columns) == list(TRANSFORM_SCORE_EXPLAIN_COLUMNS)
    assert explain_df["Organisation Name"].tolist() == ["Acme Ltd"]
