"""Tests for infrastructure IO validation helpers."""

from __future__ import annotations

from uk_sponsor_pipeline.infrastructure.io.validation import (
    parse_companies_house_profile,
    parse_companies_house_search,
)


def test_parse_companies_house_search_defaults_missing_fields() -> None:
    payload: dict[str, object] = {
        "items": [
            {
                "title": "Acme Ltd",
                "company_number": "12345678",
                "company_status": "active",
                "address": {"locality": "London"},
            },
            {},
        ]
    }

    items = parse_companies_house_search(payload)

    assert items == [
        {
            "title": "Acme Ltd",
            "company_number": "12345678",
            "company_status": "active",
            "address": {"locality": "London", "region": "", "postal_code": ""},
        },
        {
            "title": "",
            "company_number": "",
            "company_status": "",
            "address": {"locality": "", "region": "", "postal_code": ""},
        },
    ]


def test_parse_companies_house_profile_coerces_sic_codes() -> None:
    payload: dict[str, object] = {
        "company_name": "ACME LTD",
        "company_status": "active",
        "type": "ltd",
        "date_of_creation": "2015-01-01",
        "sic_codes": "62020;63110",
        "registered_office_address": {"region": "Greater London", "postal_code": "EC1A 1BB"},
    }

    profile = parse_companies_house_profile(payload)

    assert profile == {
        "company_name": "ACME LTD",
        "company_status": "active",
        "type": "ltd",
        "date_of_creation": "2015-01-01",
        "sic_codes": ["62020", "63110"],
        "registered_office_address": {
            "locality": "",
            "region": "Greater London",
            "postal_code": "EC1A 1BB",
        },
    }
