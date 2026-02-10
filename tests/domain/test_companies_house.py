"""Tests for Companies House domain logic."""

from uk_sponsor_pipeline.domain.companies_house import (
    CandidateMatch,
    MatchScore,
    build_candidate_row,
    build_enriched_row,
    build_profile_error_row,
    build_unmatched_row,
    score_candidates,
)
from uk_sponsor_pipeline.io_validation import validate_as
from uk_sponsor_pipeline.types import CompanyProfile, SearchItem, TransformRegisterRow


def _normalise(value: str) -> str:
    return value.lower().strip()


def _similarity(a: str, b: str) -> float:
    return 0.8 if a and b else 0.0


def _transform_register_row(**overrides: str) -> TransformRegisterRow:
    row: TransformRegisterRow = {
        "Organisation Name": "Acme",
        "org_name_normalised": "acme",
        "has_multiple_towns": "False",
        "has_multiple_counties": "False",
        "Town/City": "London",
        "County": "Greater London",
        "Type & Rating": "A rating",
        "Route": "Skilled Worker",
        "raw_name_variants": "Acme",
    }
    merged = {**row, **overrides}
    return validate_as(TransformRegisterRow, merged)


def test_score_candidates_applies_bonuses() -> None:
    items: list[SearchItem] = [
        {
            "title": "Acme Ltd",
            "company_number": "123",
            "company_status": "active",
            "address": {
                "locality": "London",
                "region": "Greater London",
                "postal_code": "EC1A",
            },
        }
    ]

    scored = score_candidates(
        org_norm="acme",
        town_norm="london",
        county_norm="greater london",
        items=items,
        query_used="Acme",
        similarity_fn=_similarity,
        normalise_fn=_normalise,
    )

    assert len(scored) == 1
    assert scored[0].score.total == min(1.0, 0.8 + 0.08 + 0.05 + 0.05)


def test_score_candidates_reuses_normalised_location_values() -> None:
    items: list[SearchItem] = [
        {
            "title": "Acme Ltd",
            "company_number": "123",
            "company_status": "active",
            "address": {
                "locality": "London",
                "region": "Greater London",
                "postal_code": "EC1A",
            },
        }
    ]
    normalise_calls: dict[str, int] = {}

    def counting_normalise(value: str) -> str:
        normalise_calls[value] = normalise_calls.get(value, 0) + 1
        return value.lower().strip()

    score_candidates(
        org_norm="acme",
        town_norm="manchester",
        county_norm="greater london",
        items=items,
        query_used="Acme",
        similarity_fn=_similarity,
        normalise_fn=counting_normalise,
    )

    assert normalise_calls["London"] == 1
    assert normalise_calls["Greater London"] == 1


def test_build_candidate_row_rounds_scores() -> None:
    score = MatchScore(0.87654, 0.5, 0.1, 0.2, 0.05)
    cand = CandidateMatch("123", "Acme", "active", "London", "Greater London", "EC1", score, "Acme")

    row = build_candidate_row(org="Acme", cand=cand, rank=1)

    assert row["candidate_score"] == 0.8765
    assert row["score_region_bonus"] == 0.2


def test_build_rows_for_unmatched_and_profile_error() -> None:
    score = MatchScore(0.6, 0.5, 0.05, 0.03, 0.02)
    cand = CandidateMatch("123", "Acme", "active", "London", "Greater London", "EC1", score, "Acme")
    base = _transform_register_row()

    unmatched = build_unmatched_row(row=base, best_match=cand)
    assert unmatched["match_status"] == "unmatched"
    assert unmatched["best_candidate_company_number"] == "123"

    error_row = build_profile_error_row(row=base, best_match=cand, error=RuntimeError("boom"))
    assert error_row["match_status"] == "profile_error"
    assert "boom" in error_row["match_error"]


def test_build_enriched_row_maps_profile() -> None:
    score = MatchScore(0.9, 0.6, 0.1, 0.1, 0.1)
    cand = CandidateMatch("123", "Acme", "active", "London", "Greater London", "EC1", score, "Acme")
    row = _transform_register_row()
    profile: CompanyProfile = {
        "company_name": "ACME LTD",
        "company_status": "active",
        "type": "ltd",
        "date_of_creation": "2010-01-01",
        "sic_codes": ["62020"],
        "registered_office_address": {
            "locality": "London",
            "region": "Greater London",
            "postal_code": "EC1A 1BB",
        },
    }

    enriched = build_enriched_row(row=row, best_match=cand, profile=profile)

    assert enriched["match_status"] == "matched"
    assert enriched["ch_company_name"] == "ACME LTD"
    assert enriched["ch_sic_codes"] == "62020"
