"""Pydantic-based validation helpers for inbound IO payloads."""

from __future__ import annotations

from typing import TypedDict

from pydantic import TypeAdapter, ValidationError

from ...io_contracts import CompanyProfileIO, SearchItemIO


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
