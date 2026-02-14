"""Tests for snapshot validation helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from uk_sponsor_pipeline.application.companies_house_bulk import CANONICAL_HEADERS_V1
from uk_sponsor_pipeline.devtools.validation_snapshots import (
    SnapshotValidationError,
    validate_snapshots,
)
from uk_sponsor_pipeline.io_validation import validate_as
from uk_sponsor_pipeline.schemas import TRANSFORM_REGISTER_OUTPUT_COLUMNS

_EMPLOYEE_COUNT_COLUMNS = (
    "company_number",
    "employee_count",
    "employee_count_source",
    "employee_count_snapshot_date",
)


def _write_csv(path: Path, headers: list[str] | tuple[str, ...], row: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerow(row)


def _build_manifest(
    *,
    dataset: str,
    snapshot_date: str,
    schema_version: str,
    artefacts: dict[str, str],
) -> dict[str, object]:
    return {
        "dataset": dataset,
        "snapshot_date": snapshot_date,
        "source_url": "https://example.com/source.csv",
        "downloaded_at_utc": "2026-02-06T12:00:00+00:00",
        "last_updated_at_utc": "2026-02-06T12:05:00+00:00",
        "schema_version": schema_version,
        "sha256_hash_raw": "rawhash",
        "sha256_hash_clean": "cleanhash",
        "bytes_raw": 128,
        "row_counts": {"raw": 2, "clean": 1},
        "artefacts": artefacts,
        "git_sha": "abc123",
        "tool_version": "0.1.0",
        "command_line": "uship admin refresh sponsor",
    }


def _write_valid_sponsor_snapshot(root: Path, snapshot_date: str) -> None:
    snapshot_dir = root / "sponsor" / snapshot_date
    _write_csv(
        snapshot_dir / "clean.csv",
        TRANSFORM_REGISTER_OUTPUT_COLUMNS,
        ["Acme Ltd", "acme", "False", "False", "London", "London", "A", "Worker", "Acme Ltd"],
    )
    _write_csv(snapshot_dir / "raw.csv", ["Organisation Name"], ["Acme Ltd"])
    (snapshot_dir / "register_stats.json").write_text("{}", encoding="utf-8")
    manifest = _build_manifest(
        dataset="sponsor",
        snapshot_date=snapshot_date,
        schema_version="sponsor_clean_v1",
        artefacts={
            "raw": "raw.csv",
            "clean": "clean.csv",
            "register_stats": "register_stats.json",
            "manifest": "manifest.json",
        },
    )
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _write_valid_companies_house_snapshot(root: Path, snapshot_date: str) -> None:
    snapshot_dir = root / "companies_house" / snapshot_date
    _write_csv(
        snapshot_dir / "clean.csv",
        CANONICAL_HEADERS_V1,
        [
            "12345678",
            "ACME LTD",
            "active",
            "private-limited-company",
            "2015-01-01",
            "62020",
            "London",
            "Greater London",
            "EC1A 1BB",
            "http://data.companieshouse.gov.uk/doc/company/12345678",
        ],
    )
    _write_csv(snapshot_dir / "raw.csv", ["CompanyName"], ["ACME LTD"])
    _write_csv(
        snapshot_dir / "index_tokens_a.csv", ["token", "company_number"], ["acme", "12345678"]
    )
    _write_csv(
        snapshot_dir / "profiles_1.csv",
        CANONICAL_HEADERS_V1,
        [
            "12345678",
            "ACME LTD",
            "active",
            "private-limited-company",
            "2015-01-01",
            "62020",
            "London",
            "Greater London",
            "EC1A 1BB",
            "http://data.companieshouse.gov.uk/doc/company/12345678",
        ],
    )
    manifest = _build_manifest(
        dataset="companies_house",
        snapshot_date=snapshot_date,
        schema_version="ch_clean_v1",
        artefacts={
            "raw": "raw.csv",
            "clean": "clean.csv",
            "manifest": "manifest.json",
        },
    )
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _write_valid_employee_count_snapshot(root: Path, snapshot_date: str) -> None:
    snapshot_dir = root / "employee_count" / snapshot_date
    _write_csv(
        snapshot_dir / "clean.csv",
        _EMPLOYEE_COUNT_COLUMNS,
        [
            "12345678",
            "1200",
            "ons_business_register",
            snapshot_date,
        ],
    )
    _write_csv(snapshot_dir / "raw.csv", ("company_number", "employees"), ["12345678", "1200"])
    manifest = _build_manifest(
        dataset="employee_count",
        snapshot_date=snapshot_date,
        schema_version="employee_count_v1",
        artefacts={
            "raw": "raw.csv",
            "clean": "clean.csv",
            "manifest": "manifest.json",
        },
    )
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _write_valid_snapshot_root(root: Path) -> None:
    _write_valid_sponsor_snapshot(root, "2026-02-06")
    _write_valid_companies_house_snapshot(root, "2026-02-06")
    _write_valid_employee_count_snapshot(root, "2026-02-06")


def test_validate_snapshots_accepts_valid_snapshots(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "snapshots"
    _write_valid_snapshot_root(snapshot_root)

    result = validate_snapshots(snapshot_root)

    assert result.snapshot_root == snapshot_root
    assert len(result.datasets) == 3
    assert [dataset.dataset for dataset in result.datasets] == [
        "sponsor",
        "companies_house",
        "employee_count",
    ]


def test_validate_snapshots_accepts_companies_house_manifest_without_manifest_key(
    tmp_path: Path,
) -> None:
    snapshot_root = tmp_path / "snapshots"
    _write_valid_snapshot_root(snapshot_root)
    manifest_path = snapshot_root / "companies_house" / "2026-02-06" / "manifest.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = validate_as(dict[str, object], manifest_data)
    artefacts_data = validate_as(dict[str, object], manifest["artefacts"])
    artefacts = {key: value for key, value in artefacts_data.items() if key != "manifest"}
    manifest["artefacts"] = artefacts
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_snapshots(snapshot_root)

    assert result.snapshot_root == snapshot_root
    assert len(result.datasets) == 3


def test_validate_snapshots_raises_for_missing_employee_count_dataset(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "snapshots"
    _write_valid_sponsor_snapshot(snapshot_root, "2026-02-06")
    _write_valid_companies_house_snapshot(snapshot_root, "2026-02-06")

    with pytest.raises(
        SnapshotValidationError,
        match="Dataset snapshot directory is missing: .*employee_count",
    ):
        validate_snapshots(snapshot_root)


def test_validate_snapshots_raises_for_missing_snapshot_root(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "missing"

    with pytest.raises(SnapshotValidationError, match="Snapshot root directory does not exist"):
        validate_snapshots(snapshot_root)


def test_validate_snapshots_raises_for_missing_required_artefact(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "snapshots"
    _write_valid_snapshot_root(snapshot_root)
    (snapshot_root / "sponsor" / "2026-02-06" / "register_stats.json").unlink()

    with pytest.raises(SnapshotValidationError, match="Missing required artefact"):
        validate_snapshots(snapshot_root)


def test_validate_snapshots_raises_for_missing_manifest_field(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "snapshots"
    _write_valid_snapshot_root(snapshot_root)
    manifest_path = snapshot_root / "sponsor" / "2026-02-06" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["schema_version"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="Manifest missing required field"):
        validate_snapshots(snapshot_root)


def test_validate_snapshots_raises_for_wrong_schema_version(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "snapshots"
    _write_valid_snapshot_root(snapshot_root)
    manifest_path = snapshot_root / "companies_house" / "2026-02-06" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = "ch_clean_v2"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="Unexpected schema_version"):
        validate_snapshots(snapshot_root)


def test_validate_snapshots_raises_for_missing_required_headers(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "snapshots"
    _write_valid_snapshot_root(snapshot_root)
    clean_path = snapshot_root / "sponsor" / "2026-02-06" / "clean.csv"
    _write_csv(clean_path, ["Organisation Name"], ["Acme Ltd"])

    with pytest.raises(SnapshotValidationError, match="Missing required columns"):
        validate_snapshots(snapshot_root)


def test_validate_snapshots_raises_for_missing_employee_count_headers(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "snapshots"
    _write_valid_snapshot_root(snapshot_root)
    clean_path = snapshot_root / "employee_count" / "2026-02-06" / "clean.csv"
    _write_csv(clean_path, ("company_number",), ["12345678"])

    with pytest.raises(SnapshotValidationError, match="employee_count clean.csv"):
        validate_snapshots(snapshot_root)
