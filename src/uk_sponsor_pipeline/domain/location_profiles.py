"""Location profile resolution and geographic filter matching.

Usage example:
    from uk_sponsor_pipeline.domain.location_profiles import (
        build_geo_filter,
        build_location_profiles,
        matches_geo_filter,
        resolve_location_profile,
    )

    profiles = build_location_profiles([
        {
            "canonical_name": "London",
            "aliases": ["Greater London"],
            "regions": ["Greater London"],
            "localities": ["Camden"],
            "postcode_prefixes": ["EC", "SW"],
            "notes": "Example only.",
        }
    ])

    geo = build_geo_filter("London", ("NW",), profiles)
    resolved = resolve_location_profile("Greater London", profiles)
    assert resolved is not None
    assert "ec" in geo.postcode_prefixes[1].lower()
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..io_contracts import LocationProfileIO
from ..types import Stage2EnrichedRow


@dataclass(frozen=True)
class LocationProfile:
    """Canonical location definition with aliases and matching hints."""

    canonical_name: str
    aliases: tuple[str, ...]
    regions: tuple[str, ...]
    localities: tuple[str, ...]
    postcode_prefixes: tuple[str, ...]

    def all_match_terms(self) -> tuple[str, ...]:
        terms = [self.canonical_name, *self.aliases, *self.regions, *self.localities]
        return _dedupe_terms(_normalise_terms(terms))


@dataclass(frozen=True)
class GeoFilter:
    """Expanded geographic filter terms for matching."""

    region_terms: tuple[str, ...]
    locality_terms: tuple[str, ...]
    postcode_prefixes: tuple[str, ...]

    @classmethod
    def empty(cls) -> GeoFilter:
        return cls(region_terms=tuple(), locality_terms=tuple(), postcode_prefixes=tuple())

    def is_empty(self) -> bool:
        return not self.region_terms and not self.locality_terms and not self.postcode_prefixes


def build_location_profiles(payloads: Iterable[LocationProfileIO]) -> list[LocationProfile]:
    profiles: list[LocationProfile] = []
    for payload in payloads:
        profiles.append(
            LocationProfile(
                canonical_name=payload["canonical_name"].strip(),
                aliases=_dedupe_terms(_normalise_terms(payload["aliases"])),
                regions=_dedupe_terms(_normalise_terms(payload["regions"])),
                localities=_dedupe_terms(_normalise_terms(payload["localities"])),
                postcode_prefixes=_dedupe_terms(_normalise_postcodes(payload["postcode_prefixes"])),
            )
        )
    return profiles


def resolve_location_profile(
    query: str | None, profiles: Iterable[LocationProfile]
) -> LocationProfile | None:
    if not query:
        return None
    target = _normalise_text(query)
    for profile in profiles:
        if target in profile.all_match_terms():
            return profile
    return None


def build_geo_filter(
    region: str | None, postcodes: tuple[str, ...], profiles: Iterable[LocationProfile]
) -> GeoFilter:
    if not region and not postcodes:
        return GeoFilter.empty()

    profile = resolve_location_profile(region, profiles)
    region_terms: list[str] = []
    locality_terms: list[str] = []
    postcode_terms: list[str] = list(_normalise_postcodes(postcodes))

    if region:
        region_terms.append(_normalise_text(region))

    if profile is not None:
        region_terms.extend(_normalise_terms(profile.regions))
        locality_terms.extend(_normalise_terms(profile.localities))
        postcode_terms.extend(_normalise_postcodes(profile.postcode_prefixes))

    return GeoFilter(
        region_terms=_dedupe_terms(tuple(region_terms)),
        locality_terms=_dedupe_terms(tuple(locality_terms)),
        postcode_prefixes=_dedupe_terms(tuple(postcode_terms)),
    )


def matches_geo_filter(row: Stage2EnrichedRow, geo_filter: GeoFilter) -> bool:
    if geo_filter.is_empty():
        return True

    row_region = row["ch_address_region"].lower()
    locality = row["ch_address_locality"].lower()
    postcode = row["ch_address_postcode"].upper()

    if geo_filter.region_terms:
        if any(term in row_region or term in locality for term in geo_filter.region_terms):
            return True

    if geo_filter.locality_terms:
        if any(term in locality for term in geo_filter.locality_terms):
            return True

    if geo_filter.postcode_prefixes:
        if any(postcode.startswith(prefix) for prefix in geo_filter.postcode_prefixes):
            return True

    return False


def _normalise_text(value: str) -> str:
    return value.strip().lower()


def _normalise_terms(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(_normalise_text(value) for value in values if value.strip())


def _normalise_postcodes(values: Iterable[str]) -> tuple[str, ...]:
    cleaned: list[str] = []
    for value in values:
        text = value.strip().upper()
        if text:
            cleaned.append(text)
    return tuple(cleaned)


def _dedupe_terms(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return tuple(deduped)
