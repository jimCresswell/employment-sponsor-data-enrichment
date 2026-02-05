"""Companies House bulk CSV cleaning helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date

from ..exceptions import CompaniesHouseUriMismatchError, CsvSchemaMissingColumnsError

RAW_HEADERS_TRIMMED = [
    "CompanyName",
    "CompanyNumber",
    "RegAddress.CareOf",
    "RegAddress.POBox",
    "RegAddress.AddressLine1",
    "RegAddress.AddressLine2",
    "RegAddress.PostTown",
    "RegAddress.County",
    "RegAddress.Country",
    "RegAddress.PostCode",
    "CompanyCategory",
    "CompanyStatus",
    "CountryOfOrigin",
    "DissolutionDate",
    "IncorporationDate",
    "Accounts.AccountRefDay",
    "Accounts.AccountRefMonth",
    "Accounts.NextDueDate",
    "Accounts.LastMadeUpDate",
    "Accounts.AccountCategory",
    "Returns.NextDueDate",
    "Returns.LastMadeUpDate",
    "Mortgages.NumMortCharges",
    "Mortgages.NumMortOutstanding",
    "Mortgages.NumMortPartSatisfied",
    "Mortgages.NumMortSatisfied",
    "SICCode.SicText_1",
    "SICCode.SicText_2",
    "SICCode.SicText_3",
    "SICCode.SicText_4",
    "LimitedPartnerships.NumGenPartners",
    "LimitedPartnerships.NumLimPartners",
    "URI",
    "PreviousName_1.CONDATE",
    "PreviousName_1.CompanyName",
    "PreviousName_2.CONDATE",
    "PreviousName_2.CompanyName",
    "PreviousName_3.CONDATE",
    "PreviousName_3.CompanyName",
    "PreviousName_4.CONDATE",
    "PreviousName_4.CompanyName",
    "PreviousName_5.CONDATE",
    "PreviousName_5.CompanyName",
    "PreviousName_6.CONDATE",
    "PreviousName_6.CompanyName",
    "PreviousName_7.CONDATE",
    "PreviousName_7.CompanyName",
    "PreviousName_8.CONDATE",
    "PreviousName_8.CompanyName",
    "PreviousName_9.CONDATE",
    "PreviousName_9.CompanyName",
    "PreviousName_10.CONDATE",
    "PreviousName_10.CompanyName",
    "ConfStmtNextDueDate",
    "ConfStmtLastMadeUpDate",
]

CANONICAL_HEADERS_V1 = [
    "company_number",
    "company_name",
    "company_status",
    "company_type",
    "date_of_creation",
    "sic_codes",
    "address_locality",
    "address_region",
    "address_postcode",
    "uri",
]

_SIC_FIELDS = (
    "SICCode.SicText_1",
    "SICCode.SicText_2",
    "SICCode.SicText_3",
    "SICCode.SicText_4",
)


def normalise_raw_headers(headers: Iterable[str]) -> list[str]:
    return [header.strip() for header in headers]


def validate_raw_headers(headers: Iterable[str]) -> None:
    trimmed = set(normalise_raw_headers(headers))
    missing = set(RAW_HEADERS_TRIMMED) - trimmed
    if missing:
        raise CsvSchemaMissingColumnsError(sorted(missing))


def slugify_company_type(value: str) -> str:
    text = value.strip().lower()
    if not text:
        return ""
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")


def parse_sic_codes(values: Iterable[str]) -> str:
    codes: list[str] = []
    for raw in values:
        text = raw.strip()
        if not text:
            continue
        if " - " in text:
            text = text.split(" - ", 1)[0].strip()
        if text:
            codes.append(text)
    return ";".join(codes)


def _parse_date(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    parsed = date.fromisoformat(text)
    return parsed.isoformat()


def _expected_uri(company_number: str) -> str:
    return f"http://data.companieshouse.gov.uk/doc/company/{company_number}"


def clean_companies_house_row(raw: Mapping[str, str]) -> dict[str, str]:
    company_number = raw.get("CompanyNumber", "").strip()
    uri = raw.get("URI", "").strip()
    expected_uri = _expected_uri(company_number)
    if uri != expected_uri:
        raise CompaniesHouseUriMismatchError(company_number, uri)

    sic_values = [raw.get(field, "") for field in _SIC_FIELDS]

    cleaned = {
        "company_number": company_number,
        "company_name": raw.get("CompanyName", "").strip(),
        "company_status": raw.get("CompanyStatus", "").strip().lower(),
        "company_type": slugify_company_type(raw.get("CompanyCategory", "")),
        "date_of_creation": _parse_date(raw.get("IncorporationDate", "")),
        "sic_codes": parse_sic_codes(sic_values),
        "address_locality": raw.get("RegAddress.PostTown", "").strip(),
        "address_region": raw.get("RegAddress.County", "").strip(),
        "address_postcode": raw.get("RegAddress.PostCode", "").strip(),
        "uri": uri,
    }
    return cleaned
