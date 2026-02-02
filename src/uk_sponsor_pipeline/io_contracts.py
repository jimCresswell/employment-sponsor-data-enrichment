"""Boundary-neutral IO contracts for infrastructure validation.

Usage example:
    from uk_sponsor_pipeline.io_contracts import CompanyProfileIO

    profile: CompanyProfileIO = {
        "company_name": "ACME LTD",
        "company_status": "active",
        "type": "ltd",
        "date_of_creation": "2015-01-01",
        "sic_codes": ["62020"],
        "registered_office_address": {
            "locality": "London",
            "region": "Greater London",
            "postal_code": "EC1A 1BB",
        },
    }
"""

from __future__ import annotations

from typing import TypedDict


class SearchAddressIO(TypedDict):
    """Companies House search address payload shape."""

    locality: str
    region: str
    postal_code: str


class SearchItemIO(TypedDict):
    """Companies House search item payload shape."""

    title: str
    company_number: str
    company_status: str
    address: SearchAddressIO


class SearchResponseIO(TypedDict):
    """Companies House search response payload shape."""

    items: list[SearchItemIO]


class RegisteredOfficeAddressIO(TypedDict):
    """Companies House registered office address payload shape."""

    locality: str
    region: str
    postal_code: str


class CompanyProfileIO(TypedDict):
    """Companies House company profile payload shape."""

    company_name: str
    company_status: str
    type: str
    date_of_creation: str
    sic_codes: list[str]
    registered_office_address: RegisteredOfficeAddressIO


class LocationProfileIO(TypedDict):
    """Location alias payload shape."""

    canonical_name: str
    aliases: list[str]
    regions: list[str]
    localities: list[str]
    postcode_prefixes: list[str]
    notes: str


class LocationAliasesIO(TypedDict):
    """Location aliases file payload shape."""

    locations: list[LocationProfileIO]
