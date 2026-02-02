"""Pydantic-based validation helpers for inbound IO payloads."""

from __future__ import annotations

from typing import TypedDict

from pydantic import TypeAdapter, ValidationError

from ...io_contracts import (
    CompaniesHouseFileIO,
    CompaniesHouseProfileEntryIO,
    CompaniesHouseSearchEntryIO,
    CompanyProfileIO,
    LocationProfileIO,
    SearchItemIO,
)


class IncomingDataError(ValueError):
    """Raised when inbound data fails validation."""


class SearchAddressInput(TypedDict, total=False):
    locality: str | None
    region: str | None
    postal_code: str | None


class SearchItemInput(TypedDict, total=False):
    title: str | None
    company_number: str | None
    company_status: str | None
    address: SearchAddressInput | None


class SearchResponseInput(TypedDict, total=False):
    items: list[SearchItemInput]


class RegisteredOfficeAddressInput(TypedDict, total=False):
    locality: str | None
    region: str | None
    postal_code: str | None


class CompanyProfileInput(TypedDict, total=False):
    company_name: str | None
    company_status: str | None
    type: str | None
    date_of_creation: str | None
    sic_codes: list[str] | str | None
    registered_office_address: RegisteredOfficeAddressInput | None


class CompaniesHouseSearchEntryInput(TypedDict, total=False):
    query: str | None
    items: list[object] | None


class CompaniesHouseProfileEntryInput(TypedDict, total=False):
    company_number: str | None
    profile: dict[str, object] | None


class CompaniesHouseFileInput(TypedDict, total=False):
    searches: list[CompaniesHouseSearchEntryInput]
    profiles: list[CompaniesHouseProfileEntryInput]


class LocationProfileInput(TypedDict, total=False):
    canonical_name: str | None
    aliases: list[str] | None
    regions: list[str] | None
    localities: list[str] | None
    postcode_prefixes: list[str] | None
    notes: str | None


class LocationAliasesInput(TypedDict, total=False):
    locations: list[LocationProfileInput]


def validate_as[SchemaT](schema: type[SchemaT], payload: object) -> SchemaT:
    try:
        return TypeAdapter(schema).validate_python(payload)
    except ValidationError as exc:
        message = f"Invalid payload for {schema}."
        raise IncomingDataError(message) from exc


def validate_json_as[SchemaT](schema: type[SchemaT], payload: str | bytes | bytearray) -> SchemaT:
    try:
        return TypeAdapter(schema).validate_json(payload)
    except ValidationError as exc:
        message = f"Invalid JSON payload for {schema}."
        raise IncomingDataError(message) from exc


def _as_str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _as_str_list(value: object) -> list[str]:
    if value is None:
        return []
    try:
        items = validate_as(list[object], value)
    except IncomingDataError:
        return []
    cleaned: list[str] = []
    for item in items:
        text = str(item).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _coerce_sic_codes(value: object) -> list[str]:
    if value is None:
        return []
    try:
        items = validate_as(list[object], value)
    except IncomingDataError:
        items = None
    if items is not None:
        cleaned: list[str] = []
        for item in items:
            text = str(item).strip()
            if text:
                cleaned.append(text)
        return cleaned
    if isinstance(value, str):
        return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]
    return []


def parse_companies_house_search(payload: object) -> list[SearchItemIO]:
    response = validate_as(SearchResponseInput, payload)
    raw_items = response.get("items", [])
    items: list[SearchItemIO] = []
    for raw_item in raw_items:
        item = validate_as(SearchItemInput, raw_item)
        address_input = item.get("address") or {}
        address = validate_as(SearchAddressInput, address_input)
        items.append(
            {
                "title": _as_str(item.get("title")),
                "company_number": _as_str(item.get("company_number")),
                "company_status": _as_str(item.get("company_status")),
                "address": {
                    "locality": _as_str(address.get("locality")),
                    "region": _as_str(address.get("region")),
                    "postal_code": _as_str(address.get("postal_code")),
                },
            }
        )
    return items


def parse_companies_house_profile(payload: object) -> CompanyProfileIO:
    profile = validate_as(CompanyProfileInput, payload)
    address_input = profile.get("registered_office_address") or {}
    address = validate_as(RegisteredOfficeAddressInput, address_input)
    return {
        "company_name": _as_str(profile.get("company_name")),
        "company_status": _as_str(profile.get("company_status")),
        "type": _as_str(profile.get("type")),
        "date_of_creation": _as_str(profile.get("date_of_creation")),
        "sic_codes": _coerce_sic_codes(profile.get("sic_codes")),
        "registered_office_address": {
            "locality": _as_str(address.get("locality")),
            "region": _as_str(address.get("region")),
            "postal_code": _as_str(address.get("postal_code")),
        },
    }


def parse_location_aliases(payload: object) -> list[LocationProfileIO]:
    aliases = validate_as(LocationAliasesInput, payload)
    raw_locations = aliases.get("locations", [])
    locations: list[LocationProfileIO] = []
    for raw_location in raw_locations:
        location = validate_as(LocationProfileInput, raw_location)
        locations.append(
            {
                "canonical_name": _as_str(location.get("canonical_name")),
                "aliases": _as_str_list(location.get("aliases")),
                "regions": _as_str_list(location.get("regions")),
                "localities": _as_str_list(location.get("localities")),
                "postcode_prefixes": _as_str_list(location.get("postcode_prefixes")),
                "notes": _as_str(location.get("notes")),
            }
        )
    return locations


def parse_companies_house_file(payload: object) -> CompaniesHouseFileIO:
    file_payload = validate_as(CompaniesHouseFileInput, payload)
    raw_searches = file_payload.get("searches", [])
    raw_profiles = file_payload.get("profiles", [])
    searches: list[CompaniesHouseSearchEntryIO] = []
    profiles: list[CompaniesHouseProfileEntryIO] = []

    for raw_search in raw_searches:
        entry = validate_as(CompaniesHouseSearchEntryInput, raw_search)
        query = _as_str(entry.get("query"))
        items_payload = {"items": entry.get("items") or []}
        items = parse_companies_house_search(items_payload)
        searches.append({"query": query, "items": items})

    for raw_profile in raw_profiles:
        entry = validate_as(CompaniesHouseProfileEntryInput, raw_profile)
        company_number = _as_str(entry.get("company_number"))
        profile_payload = entry.get("profile") or {}
        profile = parse_companies_house_profile(profile_payload)
        profiles.append({"company_number": company_number, "profile": profile})

    return {"searches": searches, "profiles": profiles}
