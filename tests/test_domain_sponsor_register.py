"""Tests for sponsor register domain logic."""

from uk_sponsor_pipeline.domain.organisation_identity import normalize_org_name
from uk_sponsor_pipeline.domain.sponsor_register import (
    RawSponsorRow,
    build_sponsor_register_snapshot,
)


def test_snapshot_stats_and_variants() -> None:
    rows: list[RawSponsorRow] = [
        {
            "Organisation Name": "ACME Software Ltd",
            "Town/City": "London",
            "County": "Greater London",
            "Type & Rating": "A rating",
            "Route": "Skilled Worker",
        },
        {
            "Organisation Name": "ACME SOFTWARE LIMITED",
            "Town/City": "London",
            "County": "Greater London",
            "Type & Rating": "A rating",
            "Route": "Skilled Worker",
        },
        {
            "Organisation Name": "Tech Corp T/A Digital Solutions",
            "Town/City": "Manchester",
            "County": "Greater Manchester",
            "Type & Rating": "A rating",
            "Route": "Skilled Worker",
        },
        {
            "Organisation Name": "City Hospital NHS Trust",
            "Town/City": "Birmingham",
            "County": "West Midlands",
            "Type & Rating": "A rating",
            "Route": "Skilled Worker",
        },
        {
            "Organisation Name": "Bob's Construction Ltd",
            "Town/City": "Leeds",
            "County": "West Yorkshire",
            "Type & Rating": "A rating",
            "Route": "Skilled Worker",
        },
    ]

    snapshot = build_sponsor_register_snapshot(rows, normalize_fn=normalize_org_name)

    assert snapshot.stats.total_raw_rows == 5
    assert snapshot.stats.filtered_rows == 5
    assert snapshot.stats.unique_orgs_normalized == 4
    assert snapshot.stats.unique_orgs_raw == 5
    assert snapshot.stats.duplicates_merged == 1

    acme = next(row for row in snapshot.aggregated if row.org_name_normalized == "acme software")
    assert acme.organisation_name == "ACME Software Ltd"
    assert acme.raw_name_variants == ("ACME Software Ltd", "ACME SOFTWARE LIMITED")
    assert acme.towns == ("London",)
    assert acme.counties == ("Greater London",)
    assert acme.has_multiple_towns is False
    assert acme.has_multiple_counties is False

    assert snapshot.stats.top_towns[0] == ("London", 2)


def test_snapshot_multi_location_flags() -> None:
    rows: list[RawSponsorRow] = [
        {
            "Organisation Name": "Multi Town Org Ltd",
            "Town/City": "London",
            "County": "Greater London",
            "Type & Rating": "A rating",
            "Route": "Skilled Worker",
        },
        {
            "Organisation Name": "Multi Town Org Limited",
            "Town/City": "Manchester",
            "County": "Greater Manchester",
            "Type & Rating": "A rating",
            "Route": "Skilled Worker",
        },
    ]

    snapshot = build_sponsor_register_snapshot(rows, normalize_fn=normalize_org_name)
    org = snapshot.aggregated[0]

    assert org.has_multiple_towns is True
    assert org.has_multiple_counties is True
    assert org.towns == ("London", "Manchester")
    assert org.counties == ("Greater London", "Greater Manchester")
