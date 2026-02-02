"""Shared enrich row helpers for tests."""

from __future__ import annotations

from uk_sponsor_pipeline.infrastructure.io.validation import validate_as
from uk_sponsor_pipeline.types import TransformEnrichRow


def make_enrich_row(**overrides: str | float) -> TransformEnrichRow:
    """Build a valid TransformEnrichRow with optional overrides."""
    row: TransformEnrichRow = {
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
        "match_score": 2.0,
        "match_confidence": "medium",
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
