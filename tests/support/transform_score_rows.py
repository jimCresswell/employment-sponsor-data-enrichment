"""Shared scored row helpers for tests."""

from __future__ import annotations

from tests.support.transform_enrich_rows import make_enrich_row
from uk_sponsor_pipeline.io_validation import validate_as
from uk_sponsor_pipeline.types import TransformScoreRow


def make_scored_row(**overrides: str | float) -> TransformScoreRow:
    """Build a valid TransformScoreRow with optional overrides."""
    base = make_enrich_row()
    row: TransformScoreRow = {
        **base,
        "sic_tech_score": 0.5,
        "is_active_score": 0.1,
        "company_age_score": 0.1,
        "company_type_score": 0.08,
        "name_keyword_score": 0.05,
        "role_fit_score": 0.83,
        "role_fit_bucket": "strong",
    }
    merged = {**row, **overrides}
    return validate_as(TransformScoreRow, merged)
