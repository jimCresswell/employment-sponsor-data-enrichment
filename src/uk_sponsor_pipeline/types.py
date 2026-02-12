"""Typed data contracts used inside the pipeline after IO validation."""

from __future__ import annotations

from typing import TypedDict

TransformRegisterRow = TypedDict(
    "TransformRegisterRow",
    {
        "Organisation Name": str,
        "org_name_normalised": str,
        "has_multiple_towns": str,
        "has_multiple_counties": str,
        "Town/City": str,
        "County": str,
        "Type & Rating": str,
        "Route": str,
        "raw_name_variants": str,
    },
)


class SearchAddress(TypedDict):
    """Companies House search address shape."""

    locality: str
    region: str
    postal_code: str


class SearchItem(TypedDict):
    """Companies House search item shape."""

    title: str
    company_number: str
    company_status: str
    address: SearchAddress


class RegisteredOfficeAddress(TypedDict):
    """Companies House registered office address shape."""

    locality: str
    region: str
    postal_code: str


class CompanyProfile(TypedDict):
    """Companies House company profile shape."""

    company_name: str
    company_status: str
    type: str
    date_of_creation: str
    sic_codes: list[str]
    registered_office_address: RegisteredOfficeAddress


class CompaniesHouseCleanRow(TypedDict):
    """Companies House canonical clean row shape."""

    company_number: str
    company_name: str
    company_status: str
    company_type: str
    date_of_creation: str
    sic_codes: str
    address_locality: str
    address_region: str
    address_postcode: str
    uri: str


class EmployeeCountCleanRow(TypedDict):
    """Employee-count canonical clean row shape."""

    company_number: str
    employee_count: str
    employee_count_source: str
    employee_count_snapshot_date: str


TransformEnrichCandidateRow = TypedDict(
    "TransformEnrichCandidateRow",
    {
        "Organisation Name": str,
        "rank": int,
        "candidate_company_number": str,
        "candidate_title": str,
        "candidate_status": str,
        "candidate_locality": str,
        "candidate_region": str,
        "candidate_postcode": str,
        "candidate_score": float,
        "score_name_similarity": float,
        "score_locality_bonus": float,
        "score_region_bonus": float,
        "score_status_bonus": float,
        "query_used": str,
    },
)

TransformEnrichUnmatchedRow = TypedDict(
    "TransformEnrichUnmatchedRow",
    {
        "Organisation Name": str,
        "org_name_normalised": str,
        "has_multiple_towns": str,
        "has_multiple_counties": str,
        "Town/City": str,
        "County": str,
        "Type & Rating": str,
        "Route": str,
        "raw_name_variants": str,
        "match_status": str,
        "best_candidate_score": float | str,
        "best_candidate_title": str,
        "best_candidate_company_number": str,
        "match_error": str,
    },
)

TransformEnrichRow = TypedDict(
    "TransformEnrichRow",
    {
        "Organisation Name": str,
        "org_name_normalised": str,
        "has_multiple_towns": str,
        "has_multiple_counties": str,
        "Town/City": str,
        "County": str,
        "Type & Rating": str,
        "Route": str,
        "raw_name_variants": str,
        "match_status": str,
        "match_score": float,
        "match_confidence": str,
        "match_query_used": str,
        "score_name_similarity": float,
        "score_locality_bonus": float,
        "score_region_bonus": float,
        "score_status_bonus": float,
        "ch_company_number": str,
        "ch_company_name": str,
        "ch_company_status": str,
        "ch_company_type": str,
        "ch_date_of_creation": str,
        "ch_sic_codes": str,
        "ch_address_locality": str,
        "ch_address_region": str,
        "ch_address_postcode": str,
    },
)


class BatchRange(TypedDict):
    """Batch range representation for resume reporting."""

    start: int
    end: int


class TransformEnrichResumeReport(TypedDict):
    """Transform enrich resume report shape."""

    status: str
    error_message: str
    generated_at_utc: str
    run_started_at_utc: str
    run_finished_at_utc: str
    run_duration_seconds: float
    register_path: str
    out_dir: str
    batch_size: int
    batch_start: int
    batch_count: int | None
    batch_range: BatchRange | None
    total_register_orgs: int
    total_unprocessed_at_start: int
    total_batches_at_start: int
    total_batches_overall: int
    overall_batch_range: BatchRange | None
    selected_batches: int
    processed_in_run: int
    processed_total: int
    remaining: int
    resume_command: str


TransformScoreRow = TypedDict(
    "TransformScoreRow",
    {
        "Organisation Name": str,
        "org_name_normalised": str,
        "has_multiple_towns": str,
        "has_multiple_counties": str,
        "Town/City": str,
        "County": str,
        "Type & Rating": str,
        "Route": str,
        "raw_name_variants": str,
        "match_status": str,
        "match_score": float,
        "match_confidence": str,
        "match_query_used": str,
        "score_name_similarity": float,
        "score_locality_bonus": float,
        "score_region_bonus": float,
        "score_status_bonus": float,
        "ch_company_number": str,
        "ch_company_name": str,
        "ch_company_status": str,
        "ch_company_type": str,
        "ch_date_of_creation": str,
        "ch_sic_codes": str,
        "ch_address_locality": str,
        "ch_address_region": str,
        "ch_address_postcode": str,
        "employee_count": str,
        "employee_count_source": str,
        "employee_count_snapshot_date": str,
        "sic_tech_score": float,
        "is_active_score": float,
        "company_age_score": float,
        "company_type_score": float,
        "name_keyword_score": float,
        "role_fit_score": float,
        "role_fit_bucket": str,
    },
)

TransformScoreExplainRow = TypedDict(
    "TransformScoreExplainRow",
    {
        "Organisation Name": str,
        "ch_company_number": str,
        "ch_company_name": str,
        "ch_sic_codes": str,
        "employee_count": str,
        "employee_count_source": str,
        "employee_count_snapshot_date": str,
        "sic_tech_score": float,
        "is_active_score": float,
        "company_age_score": float,
        "company_type_score": float,
        "name_keyword_score": float,
        "role_fit_score": float,
        "role_fit_bucket": str,
    },
)

TransformScoreShortlistRow = TransformScoreRow
