"""Tests for Companies House token index generation."""

from __future__ import annotations

from uk_sponsor_pipeline.application.companies_house_index import (
    bucket_for_token,
    build_token_index,
)
from uk_sponsor_pipeline.types import CompaniesHouseCleanRow


def test_bucket_for_token_groups_non_letters() -> None:
    assert bucket_for_token("1st") == "0-9"
    assert bucket_for_token("alpha") == "a"
    assert bucket_for_token("?") == "_"


def test_build_token_index_buckets_tokens() -> None:
    rows: list[CompaniesHouseCleanRow] = [
        {
            "company_number": "01234567",
            "company_name": "Acme Ltd",
            "company_status": "active",
            "company_type": "ltd",
            "date_of_creation": "2020-01-02",
            "sic_codes": "62020",
            "address_locality": "London",
            "address_region": "Greater London",
            "address_postcode": "EC1A 1BB",
            "uri": "http://data.companieshouse.gov.uk/doc/company/01234567",
        },
        {
            "company_number": "00000001",
            "company_name": "1st Alpha Limited",
            "company_status": "active",
            "company_type": "ltd",
            "date_of_creation": "2020-01-02",
            "sic_codes": "62020",
            "address_locality": "London",
            "address_region": "Greater London",
            "address_postcode": "EC1A 1BB",
            "uri": "http://data.companieshouse.gov.uk/doc/company/00000001",
        },
    ]

    index = build_token_index(rows)

    assert ("acme", "01234567") in index["a"]
    assert ("alpha", "00000001") in index["a"]
    assert ("1st", "00000001") in index["0-9"]
