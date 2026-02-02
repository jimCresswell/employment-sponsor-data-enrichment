"""Sponsor register domain rules for register filtering and aggregation.

Usage example:
    from uk_sponsor_pipeline.domain.organisation_identity import normalise_org_name
    from uk_sponsor_pipeline.domain.sponsor_register import build_sponsor_register_snapshot

    snapshot = build_sponsor_register_snapshot(rows, normalise_fn=normalise_org_name)
    aggregated = snapshot.aggregated
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypedDict

NormaliseFn = Callable[[str], str]


RawSponsorRow = TypedDict(
    "RawSponsorRow",
    {
        "Organisation Name": str,
        "Town/City": str,
        "County": str,
        "Type & Rating": str,
        "Route": str,
    },
)


@dataclass(frozen=True)
class AggregatedOrganisation:
    """Aggregated organisation record with structured locations."""

    organisation_name: str
    org_name_normalised: str
    raw_name_variants: tuple[str, ...]
    towns: tuple[str, ...]
    counties: tuple[str, ...]
    type_and_rating: tuple[str, ...]
    routes: tuple[str, ...]

    @property
    def has_multiple_towns(self) -> bool:
        return len(self.towns) > 1

    @property
    def has_multiple_counties(self) -> bool:
        return len(self.counties) > 1


@dataclass(frozen=True)
class RegisterStatsData:
    """Register statistics computed from raw and filtered rows."""

    total_raw_rows: int
    skilled_worker_rows: int
    a_rated_rows: int
    filtered_rows: int
    unique_orgs_raw: int
    unique_orgs_normalised: int
    duplicates_merged: int
    top_towns: list[tuple[str, int]]
    top_counties: list[tuple[str, int]]


@dataclass(frozen=True)
class SponsorRegisterSnapshot:
    """Snapshot of register filtering and aggregation."""

    filtered_rows: list[RawSponsorRow]
    aggregated: list[AggregatedOrganisation]
    stats: RegisterStatsData


def _clean_value(value: str) -> str:
    text = value.strip()
    if not text or text.lower() == "nan":
        return ""
    return text


def _unique_preserve_order(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = _clean_value(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return tuple(out)


def _is_skilled_worker(route: str) -> bool:
    return route.strip() == "Skilled Worker"


def _is_a_rated(type_rating: str) -> bool:
    return "a rating" in type_rating.lower()


def build_sponsor_register_snapshot(
    rows: Iterable[RawSponsorRow], *, normalise_fn: NormaliseFn
) -> SponsorRegisterSnapshot:
    """Filter and aggregate sponsor register rows for the register transform.

    Args:
        rows: Raw sponsor register rows.
        normalise_fn: Organisation name normalisation function.

    Returns:
        SponsorRegisterSnapshot with filtered rows, aggregation, and stats.
    """
    raw_rows = list(rows)
    total_raw_rows = len(raw_rows)

    skilled_worker_rows = sum(1 for row in raw_rows if _is_skilled_worker(row["Route"]))
    a_rated_rows = sum(1 for row in raw_rows if _is_a_rated(row["Type & Rating"]))

    filtered_rows = [
        row
        for row in raw_rows
        if _is_skilled_worker(row["Route"]) and _is_a_rated(row["Type & Rating"])
    ]

    unique_orgs_raw = len({row["Organisation Name"] for row in filtered_rows})

    town_counts = Counter(row["Town/City"] for row in filtered_rows)
    county_counts = Counter(row["County"] for row in filtered_rows)

    aggregated_map: dict[str, dict[str, list[str]]] = {}
    order: list[str] = []

    for row in filtered_rows:
        normalised = normalise_fn(row["Organisation Name"])
        if normalised not in aggregated_map:
            aggregated_map[normalised] = {
                "Organisation Name": [],
                "Town/City": [],
                "County": [],
                "Type & Rating": [],
                "Route": [],
            }
            order.append(normalised)

        bucket = aggregated_map[normalised]
        bucket["Organisation Name"].append(row["Organisation Name"])
        bucket["Town/City"].append(row["Town/City"])
        bucket["County"].append(row["County"])
        bucket["Type & Rating"].append(row["Type & Rating"])
        bucket["Route"].append(row["Route"])

    aggregated: list[AggregatedOrganisation] = []
    for normalised in sorted(order):
        bucket = aggregated_map[normalised]
        raw_name_variants = _unique_preserve_order(bucket["Organisation Name"])
        towns = _unique_preserve_order(bucket["Town/City"])
        counties = _unique_preserve_order(bucket["County"])
        type_and_rating = _unique_preserve_order(bucket["Type & Rating"])
        routes = _unique_preserve_order(bucket["Route"])
        organisation_name = raw_name_variants[0] if raw_name_variants else ""
        aggregated.append(
            AggregatedOrganisation(
                organisation_name=organisation_name,
                org_name_normalised=normalised,
                raw_name_variants=raw_name_variants,
                towns=towns,
                counties=counties,
                type_and_rating=type_and_rating,
                routes=routes,
            )
        )

    unique_orgs_normalised = len(aggregated)
    duplicates_merged = unique_orgs_raw - unique_orgs_normalised

    stats = RegisterStatsData(
        total_raw_rows=total_raw_rows,
        skilled_worker_rows=skilled_worker_rows,
        a_rated_rows=a_rated_rows,
        filtered_rows=len(filtered_rows),
        unique_orgs_raw=unique_orgs_raw,
        unique_orgs_normalised=unique_orgs_normalised,
        duplicates_merged=duplicates_merged,
        top_towns=town_counts.most_common(10),
        top_counties=county_counts.most_common(10),
    )

    return SponsorRegisterSnapshot(
        filtered_rows=filtered_rows,
        aggregated=aggregated,
        stats=stats,
    )
