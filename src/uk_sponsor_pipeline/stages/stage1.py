"""Stage 1: Filter to Skilled Worker + A-rated and aggregate by organization.

Improvements over original:
- Adds org_name_normalized for matching
- Preserves org_name_raw and all variants
- Outputs stats JSON with counts and distributions
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from rich import print as rprint

from ..normalization import normalize_org_name
from ..infrastructure import LocalFileSystem
from ..protocols import FileSystem
from ..schemas import RAW_REQUIRED_COLUMNS, STAGE1_OUTPUT_COLUMNS, validate_columns


@dataclass
class Stage1Result:
    """Result of Stage 1 processing."""

    output_path: Path
    stats_path: Path
    total_raw_rows: int
    filtered_rows: int
    unique_orgs: int


@dataclass
class Stage1Stats:
    """Statistics from Stage 1 processing."""

    input_file: str
    total_raw_rows: int
    skilled_worker_rows: int
    a_rated_rows: int
    filtered_rows: int  # Both conditions
    unique_orgs_raw: int
    unique_orgs_normalized: int
    duplicates_merged: int
    top_towns: list[tuple[str, int]]
    top_counties: list[tuple[str, int]]
    processed_at_utc: str


def _arr_to_str(a: Any) -> str:
    """Convert array/list to pipe-separated string."""
    if isinstance(a, str):
        return a
    vals = [x for x in list(a) if isinstance(x, str) and x.strip() and x.lower() != "nan"]
    seen: set[str] = set()
    out: list[str] = []
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    if not out:
        return ""
    return out[0] if len(out) == 1 else " | ".join(out)


def _unique_list(values: pd.Series) -> list[str]:
    """Return unique values as a list of strings."""
    return [str(v) for v in values.unique()]


def run_stage1(
    raw_dir: str | Path = "data/raw",
    out_path: str | Path = "data/interim/stage1_skilled_worker_A_rated_aggregated_by_org.csv",
    reports_dir: str | Path = "reports",
    fs: FileSystem | None = None,
) -> Stage1Result:
    """Stage 1: Filter to Skilled Worker + A-rated and aggregate to org level.

    Args:
        raw_dir: Directory containing raw CSV files.
        out_path: Output path for filtered/aggregated CSV.
        reports_dir: Directory for stats report.
        fs: Optional filesystem for testing.

    Returns:
        Stage1Result with paths and counts.
    """
    fs = fs or LocalFileSystem()
    raw_dir = Path(raw_dir)
    out_path = Path(out_path)
    reports_dir = Path(reports_dir)
    fs.mkdir(out_path.parent, parents=True)
    fs.mkdir(reports_dir, parents=True)

    # Find most recent CSV
    if fs.exists(raw_dir) and raw_dir.suffix.lower() == ".csv":
        candidates = [raw_dir]
    else:
        candidates = fs.list_files(raw_dir, "*.csv")
    if not candidates:
        raise RuntimeError(f"No raw CSV found in {raw_dir}. Run `uk-sponsor download` first.")

    in_path = max(candidates, key=fs.mtime)
    rprint(f"[cyan]Reading:[/cyan] {in_path}")

    df = fs.read_csv(in_path).fillna("")
    df.columns = [c.strip() for c in df.columns]

    # Validate schema
    validate_columns(list(df.columns), RAW_REQUIRED_COLUMNS, "Raw CSV")

    total_raw_rows = len(df)

    # Clean columns
    for col in ["Organisation Name", "Town/City", "County", "Type & Rating", "Route"]:
        df[col] = df[col].astype(str).str.strip()

    # Count intermediate steps for stats
    skilled_worker_mask = df["Route"] == "Skilled Worker"
    skilled_worker_count = skilled_worker_mask.sum()

    a_rated_mask = df["Type & Rating"].str.contains("A rating", case=False, na=False)
    a_rated_count = a_rated_mask.sum()

    # Filter: Skilled Worker + A-rated
    mask = skilled_worker_mask & a_rated_mask
    filtered = df.loc[
        mask, ["Organisation Name", "Town/City", "County", "Type & Rating", "Route"]
    ].copy()
    filtered_rows = len(filtered)

    rprint(f"[cyan]Filtered:[/cyan] {filtered_rows:,} rows (Skilled Worker + A-rated)")

    # Add normalized name column
    filtered["org_name_normalized"] = filtered["Organisation Name"].apply(normalize_org_name)

    # Count unique before aggregation
    unique_raw = filtered["Organisation Name"].nunique()
    unique_normalized = filtered["org_name_normalized"].nunique()

    # Aggregate by normalized name, preserving raw name variants
    agg = filtered.groupby("org_name_normalized", sort=True, as_index=False).agg(
        {
            "Organisation Name": _unique_list,  # All raw variants
            "Town/City": "unique",
            "County": "unique",
            "Type & Rating": "unique",
            "Route": "unique",
        }
    )

    # Process aggregated columns
    agg["raw_name_variants"] = agg["Organisation Name"].apply(lambda x: " | ".join(sorted(set(x))))
    agg["Organisation Name"] = agg["Organisation Name"].apply(
        lambda x: x[0] if x else ""
    )  # Primary name

    for col in ["Town/City", "County", "Type & Rating", "Route"]:
        agg[col] = agg[col].apply(_arr_to_str)

    # Add multi-location flags
    agg.insert(2, "has_multiple_towns", agg["Town/City"].str.contains(r"\|", regex=True, na=False))
    agg.insert(3, "has_multiple_counties", agg["County"].str.contains(r"\|", regex=True, na=False))

    # Reorder columns
    cols = [
        "Organisation Name",
        "org_name_normalized",
        "has_multiple_towns",
        "has_multiple_counties",
        "Town/City",
        "County",
        "Type & Rating",
        "Route",
        "raw_name_variants",
    ]
    agg = agg[cols]
    validate_columns(list(agg.columns), frozenset(STAGE1_OUTPUT_COLUMNS), "Stage 1 output")

    fs.write_csv(agg, out_path)
    rprint(f"[green]✓ Output:[/green] {out_path} ({len(agg):,} unique organizations)")

    # Calculate stats
    town_counts = filtered["Town/City"].value_counts().head(10)
    county_counts = filtered["County"].value_counts().head(10)

    stats = Stage1Stats(
        input_file=str(in_path),
        total_raw_rows=total_raw_rows,
        skilled_worker_rows=int(skilled_worker_count),
        a_rated_rows=int(a_rated_count),
        filtered_rows=filtered_rows,
        unique_orgs_raw=unique_raw,
        unique_orgs_normalized=unique_normalized,
        duplicates_merged=unique_raw - unique_normalized,
        top_towns=[(str(k), int(v)) for k, v in town_counts.items()],
        top_counties=[(str(k), int(v)) for k, v in county_counts.items()],
        processed_at_utc=datetime.now(UTC).isoformat(),
    )

    # Write stats
    stats_path = reports_dir / "stage1_stats.json"
    stats_dict = {
        "input_file": stats.input_file,
        "total_raw_rows": stats.total_raw_rows,
        "skilled_worker_rows": stats.skilled_worker_rows,
        "a_rated_rows": stats.a_rated_rows,
        "filtered_rows": stats.filtered_rows,
        "unique_orgs_raw": stats.unique_orgs_raw,
        "unique_orgs_normalized": stats.unique_orgs_normalized,
        "duplicates_merged": stats.duplicates_merged,
        "top_towns": dict(stats.top_towns),
        "top_counties": dict(stats.top_counties),
        "processed_at_utc": stats.processed_at_utc,
    }
    fs.write_json(stats_dict, stats_path)
    rprint(f"[green]✓ Stats:[/green] {stats_path}")

    return Stage1Result(
        output_path=out_path,
        stats_path=stats_path,
        total_raw_rows=total_raw_rows,
        filtered_rows=filtered_rows,
        unique_orgs=len(agg),
    )
