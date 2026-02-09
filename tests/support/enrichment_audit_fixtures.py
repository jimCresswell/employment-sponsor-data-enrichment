"""Fixture builders for enrichment audit scenarios."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from uk_sponsor_pipeline.schemas import (
    TRANSFORM_ENRICH_OUTPUT_COLUMNS,
    TRANSFORM_ENRICH_UNMATCHED_COLUMNS,
)


@dataclass(frozen=True)
class EnrichmentAuditFixture:
    """Fixture rows for enrichment and unmatched outputs."""

    enriched_rows: tuple[dict[str, str], ...]
    unmatched_rows: tuple[dict[str, str], ...]


def fixture_names() -> tuple[str, ...]:
    """Return supported fixture names."""
    return tuple(_FIXTURES.keys())


def write_enrichment_audit_fixture(*, out_dir: Path, fixture_name: str) -> None:
    """Write one named enrichment audit fixture into an output directory."""
    fixture = _FIXTURES.get(fixture_name)
    if fixture is None:
        message = f"Unknown enrichment audit fixture: {fixture_name}"
        raise ValueError(message)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_rows(
        path=out_dir / "sponsor_enriched.csv",
        headers=TRANSFORM_ENRICH_OUTPUT_COLUMNS,
        rows=fixture.enriched_rows,
    )
    _write_rows(
        path=out_dir / "sponsor_unmatched.csv",
        headers=TRANSFORM_ENRICH_UNMATCHED_COLUMNS,
        rows=fixture.unmatched_rows,
    )


def _write_rows(
    *,
    path: Path,
    headers: tuple[str, ...],
    rows: tuple[dict[str, str], ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _enriched_row(
    *,
    organisation_name: str,
    company_number: str,
    company_name: str,
    match_score: str,
    name_similarity: str,
    company_status: str = "active",
) -> dict[str, str]:
    return {
        "Organisation Name": organisation_name,
        "org_name_normalised": organisation_name.lower().replace(" ", ""),
        "has_multiple_towns": "False",
        "has_multiple_counties": "False",
        "Town/City": "London",
        "County": "Greater London",
        "Type & Rating": "Worker (A rating)",
        "Route": "Skilled Worker",
        "raw_name_variants": organisation_name,
        "match_status": "matched",
        "match_score": match_score,
        "match_confidence": "medium",
        "match_query_used": organisation_name,
        "score_name_similarity": name_similarity,
        "score_locality_bonus": "0.08",
        "score_region_bonus": "0.00",
        "score_status_bonus": "0.05" if company_status == "active" else "0.00",
        "ch_company_number": company_number,
        "ch_company_name": company_name,
        "ch_company_status": company_status,
        "ch_company_type": "private-limited-company",
        "ch_date_of_creation": "2015-01-01",
        "ch_sic_codes": "62020",
        "ch_address_locality": "London",
        "ch_address_region": "Greater London",
        "ch_address_postcode": "EC1A 1BB",
    }


def _unmatched_row(
    *,
    organisation_name: str,
    best_candidate_score: str = "",
) -> dict[str, str]:
    return {
        "Organisation Name": organisation_name,
        "org_name_normalised": organisation_name.lower().replace(" ", ""),
        "has_multiple_towns": "False",
        "has_multiple_counties": "False",
        "Town/City": "London",
        "County": "Greater London",
        "Type & Rating": "Worker (A rating)",
        "Route": "Skilled Worker",
        "raw_name_variants": organisation_name,
        "match_status": "unmatched",
        "match_error": "",
        "best_candidate_score": best_candidate_score,
        "best_candidate_title": "Candidate Ltd" if best_candidate_score else "",
        "best_candidate_company_number": "00000000" if best_candidate_score else "",
    }


def _valid_baseline_fixture() -> EnrichmentAuditFixture:
    return EnrichmentAuditFixture(
        enriched_rows=(
            _enriched_row(
                organisation_name="Acme Ltd",
                company_number="10000001",
                company_name="ACME LTD",
                match_score="0.96",
                name_similarity="0.86",
            ),
            _enriched_row(
                organisation_name="Beacon Care Ltd",
                company_number="10000002",
                company_name="BEACON CARE LTD",
                match_score="0.92",
                name_similarity="0.84",
            ),
        ),
        unmatched_rows=(
            _unmatched_row(
                organisation_name="Unmatched Org Ltd",
                best_candidate_score="0.64",
            ),
        ),
    )


def _duplicate_org_fixture() -> EnrichmentAuditFixture:
    return EnrichmentAuditFixture(
        enriched_rows=(
            _enriched_row(
                organisation_name="Duplicate Org Ltd",
                company_number="20000001",
                company_name="DUPLICATE ORG LTD",
                match_score="0.95",
                name_similarity="0.85",
            ),
            _enriched_row(
                organisation_name="Duplicate Org Ltd",
                company_number="20000002",
                company_name="DUPLICATE ORG HOLDINGS LTD",
                match_score="0.93",
                name_similarity="0.83",
            ),
        ),
        unmatched_rows=(),
    )


def _overlap_fixture() -> EnrichmentAuditFixture:
    organisation_name = "Overlap Org Ltd"
    return EnrichmentAuditFixture(
        enriched_rows=(
            _enriched_row(
                organisation_name=organisation_name,
                company_number="30000001",
                company_name="OVERLAP ORG LTD",
                match_score="0.90",
                name_similarity="0.80",
            ),
        ),
        unmatched_rows=(
            _unmatched_row(
                organisation_name=organisation_name,
                best_candidate_score="0.66",
            ),
        ),
    )


def _missing_key_field_fixture() -> EnrichmentAuditFixture:
    return EnrichmentAuditFixture(
        enriched_rows=(
            _enriched_row(
                organisation_name="Missing Number Ltd",
                company_number="",
                company_name="MISSING NUMBER LTD",
                match_score="0.91",
                name_similarity="0.81",
            ),
        ),
        unmatched_rows=(),
    )


def _low_similarity_spike_fixture() -> EnrichmentAuditFixture:
    rows = tuple(
        _enriched_row(
            organisation_name=f"Low Similarity Org {idx}",
            company_number=f"4000000{idx}",
            company_name=f"LOW SIMILARITY COMPANY {idx}",
            match_score="0.74",
            name_similarity="0.55",
        )
        for idx in range(1, 7)
    )
    return EnrichmentAuditFixture(
        enriched_rows=rows,
        unmatched_rows=(),
    )


def _non_active_spike_fixture() -> EnrichmentAuditFixture:
    rows = tuple(
        _enriched_row(
            organisation_name=f"Non Active Org {idx}",
            company_number=f"5000000{idx}",
            company_name=f"NON ACTIVE ORG {idx}",
            match_score="0.89",
            name_similarity="0.84",
            company_status="liquidation",
        )
        for idx in range(1, 7)
    )
    return EnrichmentAuditFixture(
        enriched_rows=rows,
        unmatched_rows=(),
    )


def _shared_company_number_spike_fixture() -> EnrichmentAuditFixture:
    rows = tuple(
        _enriched_row(
            organisation_name=f"Shared Number Org {idx}",
            company_number="60000001",
            company_name="SHARED COMPANY NUMBER LTD",
            match_score="0.78",
            name_similarity="0.73",
        )
        for idx in range(1, 9)
    )
    return EnrichmentAuditFixture(
        enriched_rows=rows,
        unmatched_rows=(),
    )


def _near_threshold_unmatched_spike_fixture() -> EnrichmentAuditFixture:
    rows = tuple(
        _unmatched_row(
            organisation_name=f"Near Threshold Unmatched {idx}",
            best_candidate_score="0.719",
        )
        for idx in range(1, 9)
    )
    return EnrichmentAuditFixture(
        enriched_rows=(),
        unmatched_rows=rows,
    )


_FIXTURES: dict[str, EnrichmentAuditFixture] = {
    "valid_baseline": _valid_baseline_fixture(),
    "duplicate_org_enriched": _duplicate_org_fixture(),
    "overlap_between_sets": _overlap_fixture(),
    "missing_key_field": _missing_key_field_fixture(),
    "low_similarity_spike": _low_similarity_spike_fixture(),
    "non_active_spike": _non_active_spike_fixture(),
    "shared_company_number_spike": _shared_company_number_spike_fixture(),
    "near_threshold_unmatched_spike": _near_threshold_unmatched_spike_fixture(),
}
