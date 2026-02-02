"""Stage 1: Filter to Skilled Worker + A-rated and aggregate by organisation.

Improvements over original:
- Adds org_name_normalized for matching
- Preserves org_name_raw and all variants
- Outputs stats JSON with counts and distributions
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ..domain.organisation_identity import normalize_org_name
from ..domain.sponsor_register import RawSponsorRow, build_sponsor_register_snapshot
from ..infrastructure import LocalFileSystem
from ..infrastructure.io.validation import validate_as
from ..observability import get_logger
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


def _as_str(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _coerce_raw_row(raw: dict[str, object]) -> RawSponsorRow:
    return {
        "Organisation Name": _as_str(raw.get("Organisation Name", "")),
        "Town/City": _as_str(raw.get("Town/City", "")),
        "County": _as_str(raw.get("County", "")),
        "Type & Rating": _as_str(raw.get("Type & Rating", "")),
        "Route": _as_str(raw.get("Route", "")),
    }


def _coerce_raw_rows(raw_rows: list[dict[str, object]]) -> list[RawSponsorRow]:
    return [_coerce_raw_row(row) for row in raw_rows]


def _join_unique(values: Iterable[str]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = value.strip()
        if not text or text.lower() == "nan" or text in seen:
            continue
        seen.add(text)
        out.append(text)
    if not out:
        return ""
    return out[0] if len(out) == 1 else " | ".join(out)


def _join_sorted(values: Iterable[str]) -> str:
    cleaned = [value.strip() for value in values if value.strip() and value.lower() != "nan"]
    if not cleaned:
        return ""
    return " | ".join(sorted(set(cleaned)))


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
    logger = get_logger("uk_sponsor_pipeline.stage1")
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
    logger.info("Reading: %s", in_path)

    df = fs.read_csv(in_path).fillna("")
    df.columns = [c.strip() for c in df.columns]

    # Validate schema
    validate_columns(list(df.columns), RAW_REQUIRED_COLUMNS, "Raw CSV")

    # Clean columns
    for col in ["Organisation Name", "Town/City", "County", "Type & Rating", "Route"]:
        df[col] = df[col].astype(str).str.strip()

    raw_rows = validate_as(list[dict[str, object]], df.to_dict(orient="records"))
    rows = _coerce_raw_rows(raw_rows)

    snapshot = build_sponsor_register_snapshot(rows, normalize_fn=normalize_org_name)
    logger.info("Filtered: %s rows (Skilled Worker + A-rated)", f"{snapshot.stats.filtered_rows:,}")

    aggregated_rows: list[dict[str, object]] = []
    for record in snapshot.aggregated:
        aggregated_rows.append(
            {
                "Organisation Name": record.organisation_name,
                "org_name_normalized": record.org_name_normalized,
                "has_multiple_towns": record.has_multiple_towns,
                "has_multiple_counties": record.has_multiple_counties,
                "Town/City": _join_unique(record.towns),
                "County": _join_unique(record.counties),
                "Type & Rating": _join_unique(record.type_and_rating),
                "Route": _join_unique(record.routes),
                "raw_name_variants": _join_sorted(record.raw_name_variants),
            }
        )

    agg = pd.DataFrame(aggregated_rows, columns=STAGE1_OUTPUT_COLUMNS)
    validate_columns(list(agg.columns), frozenset(STAGE1_OUTPUT_COLUMNS), "Stage 1 output")

    fs.write_csv(agg, out_path)
    logger.info("Output: %s (%s unique organisations)", out_path, f"{len(agg):,}")

    stats = Stage1Stats(
        input_file=str(in_path),
        total_raw_rows=snapshot.stats.total_raw_rows,
        skilled_worker_rows=snapshot.stats.skilled_worker_rows,
        a_rated_rows=snapshot.stats.a_rated_rows,
        filtered_rows=snapshot.stats.filtered_rows,
        unique_orgs_raw=snapshot.stats.unique_orgs_raw,
        unique_orgs_normalized=snapshot.stats.unique_orgs_normalized,
        duplicates_merged=snapshot.stats.duplicates_merged,
        top_towns=snapshot.stats.top_towns,
        top_counties=snapshot.stats.top_counties,
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
    logger.info("Stats: %s", stats_path)

    return Stage1Result(
        output_path=out_path,
        stats_path=stats_path,
        total_raw_rows=snapshot.stats.total_raw_rows,
        filtered_rows=snapshot.stats.filtered_rows,
        unique_orgs=len(agg),
    )
