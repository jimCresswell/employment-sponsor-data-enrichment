"""Schema definitions for pipeline step inputs and outputs.

These define the expected columns at each step boundary, enabling validation
and clear documentation of data contracts.
"""

from __future__ import annotations

# Raw sponsor register CSV (downloaded from GOV.UK)
RAW_REQUIRED_COLUMNS = frozenset(
    [
        "Organisation Name",
        "Town/City",
        "County",
        "Type & Rating",
        "Route",
    ]
)

# Transform register output: filtered and aggregated sponsors
TRANSFORM_REGISTER_OUTPUT_COLUMNS = (
    "Organisation Name",
    "org_name_normalised",
    "has_multiple_towns",
    "has_multiple_counties",
    "Town/City",
    "County",
    "Type & Rating",
    "Route",
    "raw_name_variants",  # pipe-separated list of original name variants
)

# Transform enrich output: enriched with Companies House data
TRANSFORM_ENRICH_OUTPUT_COLUMNS = (
    *TRANSFORM_REGISTER_OUTPUT_COLUMNS,
    "match_status",
    "match_score",
    "match_confidence",  # high | medium | low
    "match_query_used",  # which query variant matched
    "score_name_similarity",
    "score_locality_bonus",
    "score_region_bonus",
    "score_status_bonus",
    "ch_company_number",
    "ch_company_name",
    "ch_company_status",
    "ch_company_type",
    "ch_date_of_creation",
    "ch_sic_codes",
    "ch_address_locality",
    "ch_address_region",
    "ch_address_postcode",
)

TRANSFORM_ENRICH_UNMATCHED_COLUMNS = (
    *TRANSFORM_REGISTER_OUTPUT_COLUMNS,
    "match_status",
    "match_error",
    "best_candidate_score",
    "best_candidate_title",
    "best_candidate_company_number",
)

TRANSFORM_ENRICH_CANDIDATES_COLUMNS = (
    "Organisation Name",
    "rank",
    "candidate_company_number",
    "candidate_title",
    "candidate_status",
    "candidate_locality",
    "candidate_region",
    "candidate_postcode",
    "candidate_score",
    "score_name_similarity",
    "score_locality_bonus",
    "score_region_bonus",
    "score_status_bonus",
    "query_used",
)

# Transform score output: scored for tech-likelihood
TRANSFORM_SCORE_OUTPUT_COLUMNS = (
    *TRANSFORM_ENRICH_OUTPUT_COLUMNS,
    "sic_tech_score",
    "is_active_score",
    "company_age_score",
    "company_type_score",
    "name_keyword_score",
    "role_fit_score",
    "role_fit_bucket",  # strong | possible | unlikely
)

TRANSFORM_SCORE_EXPLAIN_COLUMNS = (
    "Organisation Name",
    "ch_company_number",
    "ch_company_name",
    "ch_sic_codes",
    "sic_tech_score",
    "is_active_score",
    "company_age_score",
    "company_type_score",
    "name_keyword_score",
    "role_fit_score",
    "role_fit_bucket",
)


def validate_columns(df_columns: list[str], required: frozenset[str], step_name: str) -> None:
    """Validate that DataFrame has required columns.

    Args:
        df_columns: List of column names from DataFrame.
        required: Set of required column names.
        step_name: Name of step for error messages.

    Raises:
        ValueError: If required columns are missing.
    """
    missing = required - set(df_columns)
    if missing:
        raise ValueError(f"{step_name}: Missing required columns: {sorted(missing)}")
