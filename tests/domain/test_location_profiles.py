"""Tests for location profile matching and expansion."""

from tests.support.transform_enrich_rows import make_enrich_row
from uk_sponsor_pipeline.domain.location_profiles import (
    GeoFilter,
    LocationProfile,
    build_geo_filter,
    matches_geo_filter,
    resolve_location_profile,
)


def test_resolve_location_profile_matches_aliases_case_insensitive() -> None:
    profiles = [
        LocationProfile(
            canonical_name="Manchester",
            aliases=("Greater Manchester", "City of Manchester"),
            regions=("Greater Manchester",),
            localities=("Salford",),
            postcode_prefixes=("M",),
        )
    ]

    resolved = resolve_location_profile("greater manchester", profiles)

    assert resolved is not None
    assert resolved.canonical_name == "Manchester"


def test_build_geo_filter_includes_profile_terms_and_postcodes() -> None:
    profiles = [
        LocationProfile(
            canonical_name="London",
            aliases=("Greater London",),
            regions=("Greater London",),
            localities=("Camden",),
            postcode_prefixes=("EC", "SW"),
        )
    ]

    geo = build_geo_filter("London", ("NW",), profiles)

    assert geo.region_terms == ("london", "greater london")
    assert geo.locality_terms == ("camden",)
    assert geo.postcode_prefixes == ("NW", "EC", "SW")


def test_matches_geo_filter_uses_locality_alias() -> None:
    profiles = [
        LocationProfile(
            canonical_name="Manchester",
            aliases=("Manchester",),
            regions=("Greater Manchester",),
            localities=("Salford",),
            postcode_prefixes=("M",),
        )
    ]
    geo = build_geo_filter("Manchester", tuple(), profiles)
    row = make_enrich_row(
        **{
            "Organisation Name": "Salford Tech",
            "ch_address_locality": "Salford",
            "ch_address_region": "Lancashire",
            "ch_address_postcode": "M1 1AA",
        }
    )

    assert matches_geo_filter(row, geo) is True
    assert matches_geo_filter(row, GeoFilter.empty()) is True
