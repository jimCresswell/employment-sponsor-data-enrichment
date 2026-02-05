"""Tests for Companies House bulk cleaning helpers."""

from __future__ import annotations

import pytest

from uk_sponsor_pipeline.application.companies_house_bulk import (
    CANONICAL_HEADERS_V1,
    RAW_HEADERS_TRIMMED,
    clean_companies_house_row,
    normalise_raw_headers,
    parse_sic_codes,
    slugify_company_type,
    validate_raw_headers,
)
from uk_sponsor_pipeline.exceptions import (
    CompaniesHouseUriMismatchError,
    CsvSchemaMissingColumnsError,
)


def test_normalise_raw_headers_trims_whitespace() -> None:
    headers = [" CompanyName ", "CompanyNumber", " RegAddress.PostTown"]
    assert normalise_raw_headers(headers) == ["CompanyName", "CompanyNumber", "RegAddress.PostTown"]


def test_validate_raw_headers_raises_on_missing_columns() -> None:
    headers = ["CompanyName", "CompanyNumber"]
    with pytest.raises(CsvSchemaMissingColumnsError):
        validate_raw_headers(headers)


def test_slugify_company_type_rules() -> None:
    assert slugify_company_type("Public Limited Company") == "public-limited-company"
    assert slugify_company_type("Limited (Private) Company") == "limited-private-company"
    assert slugify_company_type("  Tech--Holdings  ") == "tech-holdings"


def test_parse_sic_codes_extracts_prefixes() -> None:
    sic = parse_sic_codes(
        [
            "62020 - Information technology consultancy activities",
            " 62090 - Other information technology service activities ",
            "",
        ]
    )
    assert sic == "62020;62090"


def test_clean_companies_house_row_maps_fields_and_validates_uri() -> None:
    raw = {header: "" for header in RAW_HEADERS_TRIMMED}
    raw["CompanyNumber"] = "01234567"
    raw["CompanyName"] = " Acme Ltd "
    raw["CompanyStatus"] = "ACTIVE"
    raw["CompanyCategory"] = "Public Limited Company"
    raw["IncorporationDate"] = "2020-01-02"
    raw["SICCode.SicText_1"] = "62020 - Information technology consultancy activities"
    raw["SICCode.SicText_2"] = "62090 - Other information technology service activities"
    raw["RegAddress.PostTown"] = "London"
    raw["RegAddress.County"] = "Greater London"
    raw["RegAddress.PostCode"] = "EC1A 1BB"
    raw["URI"] = "http://data.companieshouse.gov.uk/doc/company/01234567"

    clean = clean_companies_house_row(raw)
    assert list(clean.keys()) == list(CANONICAL_HEADERS_V1)
    assert clean["company_number"] == "01234567"
    assert clean["company_name"] == "Acme Ltd"
    assert clean["company_status"] == "active"
    assert clean["company_type"] == "public-limited-company"
    assert clean["date_of_creation"] == "2020-01-02"
    assert clean["sic_codes"] == "62020;62090"
    assert clean["address_locality"] == "London"
    assert clean["address_region"] == "Greater London"
    assert clean["address_postcode"] == "EC1A 1BB"
    assert clean["uri"] == "http://data.companieshouse.gov.uk/doc/company/01234567"


def test_clean_companies_house_row_raises_on_uri_mismatch() -> None:
    raw = {header: "" for header in RAW_HEADERS_TRIMMED}
    raw["CompanyNumber"] = "01234567"
    raw["CompanyName"] = "Acme Ltd"
    raw["URI"] = "http://data.companieshouse.gov.uk/doc/company/99999999"

    with pytest.raises(CompaniesHouseUriMismatchError):
        clean_companies_house_row(raw)
