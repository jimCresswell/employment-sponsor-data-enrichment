"""Snapshot validation helpers for file-first protocol checks."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..application.companies_house_bulk import CANONICAL_HEADERS_V1
from ..io_validation import IncomingDataError, validate_as
from ..schemas import TRANSFORM_REGISTER_OUTPUT_COLUMNS

_SNAPSHOT_DATE_PATTERN = re.compile(r"20\d{2}-\d{2}-\d{2}")
_DATASETS = ("sponsor", "companies_house")
_EXPECTED_SCHEMA_VERSION = {
    "sponsor": "sponsor_clean_v1",
    "companies_house": "ch_clean_v1",
}
_REQUIRED_ARTEFACTS = {
    "sponsor": ("raw.csv", "clean.csv", "register_stats.json", "manifest.json"),
    "companies_house": ("raw.csv", "clean.csv", "manifest.json"),
}
_REQUIRED_MANIFEST_FIELDS = (
    "dataset",
    "snapshot_date",
    "source_url",
    "downloaded_at_utc",
    "last_updated_at_utc",
    "schema_version",
    "sha256_hash_raw",
    "sha256_hash_clean",
    "bytes_raw",
    "row_counts",
    "artefacts",
    "git_sha",
    "tool_version",
    "command_line",
)
_REQUIRED_CLEAN_COLUMNS = {
    "sponsor": TRANSFORM_REGISTER_OUTPUT_COLUMNS,
    "companies_house": tuple(CANONICAL_HEADERS_V1),
}


class SnapshotValidationError(ValueError):
    """Raised when snapshot validation fails."""


@dataclass(frozen=True)
class DatasetSnapshotValidation:
    """Validation details for one dataset snapshot."""

    dataset: str
    snapshot_date: str
    snapshot_dir: Path
    manifest_path: Path
    clean_path: Path


@dataclass(frozen=True)
class SnapshotValidationResult:
    """Validation result for the snapshot root."""

    snapshot_root: Path
    datasets: tuple[DatasetSnapshotValidation, ...]


def validate_snapshots(snapshot_root: str | Path) -> SnapshotValidationResult:
    """Validate sponsor and Companies House snapshots under one root."""
    root = Path(snapshot_root)
    if not root.exists() or not root.is_dir():
        message = f"Snapshot root directory does not exist: {root}"
        raise SnapshotValidationError(message)

    validations: list[DatasetSnapshotValidation] = []
    for dataset in _DATASETS:
        dataset_dir = root / dataset
        if not dataset_dir.exists() or not dataset_dir.is_dir():
            message = f"Dataset snapshot directory is missing: {dataset_dir}"
            raise SnapshotValidationError(message)

        snapshot_dir = _resolve_latest_snapshot_dir(dataset_dir)
        snapshot_date = snapshot_dir.name

        _validate_required_artefacts(dataset=dataset, snapshot_dir=snapshot_dir)
        if dataset == "companies_house":
            _validate_companies_house_partition_files(snapshot_dir)

        manifest_path = snapshot_dir / "manifest.json"
        manifest = _read_manifest(manifest_path)
        _validate_manifest(manifest=manifest, dataset=dataset, snapshot_date=snapshot_date)

        clean_path = snapshot_dir / "clean.csv"
        _validate_csv_columns(
            clean_path=clean_path,
            required_columns=_REQUIRED_CLEAN_COLUMNS[dataset],
            label=f"{dataset} clean.csv",
        )

        validations.append(
            DatasetSnapshotValidation(
                dataset=dataset,
                snapshot_date=snapshot_date,
                snapshot_dir=snapshot_dir,
                manifest_path=manifest_path,
                clean_path=clean_path,
            )
        )

    return SnapshotValidationResult(snapshot_root=root, datasets=tuple(validations))


def _resolve_latest_snapshot_dir(dataset_dir: Path) -> Path:
    candidates = [
        child
        for child in dataset_dir.iterdir()
        if child.is_dir() and _SNAPSHOT_DATE_PATTERN.fullmatch(child.name)
    ]
    if not candidates:
        message = f"No dated snapshots found in dataset directory: {dataset_dir}"
        raise SnapshotValidationError(message)
    return sorted(candidates, key=lambda path: path.name, reverse=True)[0]


def _validate_required_artefacts(*, dataset: str, snapshot_dir: Path) -> None:
    required = _REQUIRED_ARTEFACTS[dataset]
    for filename in required:
        path = snapshot_dir / filename
        if not path.exists():
            message = f"Missing required artefact: {path}"
            raise SnapshotValidationError(message)


def _validate_companies_house_partition_files(snapshot_dir: Path) -> None:
    index_paths = sorted(snapshot_dir.glob("index_tokens_*.csv"))
    profile_paths = sorted(snapshot_dir.glob("profiles_*.csv"))
    if not index_paths:
        message = f"Missing Companies House index token artefacts in: {snapshot_dir}"
        raise SnapshotValidationError(message)
    if not profile_paths:
        message = f"Missing Companies House profile artefacts in: {snapshot_dir}"
        raise SnapshotValidationError(message)


def _read_manifest(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        message = f"Manifest is not valid JSON: {path}"
        raise SnapshotValidationError(message) from exc
    try:
        return validate_as(dict[str, object], payload)
    except IncomingDataError as exc:
        message = f"Manifest must be a JSON object: {path}"
        raise SnapshotValidationError(message) from exc


def _validate_manifest(
    *,
    manifest: dict[str, object],
    dataset: str,
    snapshot_date: str,
) -> None:
    for field in _REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            message = f"Manifest missing required field '{field}' for dataset '{dataset}'."
            raise SnapshotValidationError(message)

    manifest_dataset = _expect_non_empty_str(manifest, "dataset")
    if manifest_dataset != dataset:
        message = f"Manifest dataset mismatch for '{dataset}': got '{manifest_dataset}'."
        raise SnapshotValidationError(message)

    manifest_snapshot_date = _expect_non_empty_str(manifest, "snapshot_date")
    if manifest_snapshot_date != snapshot_date:
        message = (
            "Manifest snapshot_date mismatch for "
            f"'{dataset}': expected '{snapshot_date}', got '{manifest_snapshot_date}'."
        )
        raise SnapshotValidationError(message)

    schema_version = _expect_non_empty_str(manifest, "schema_version")
    expected_schema = _EXPECTED_SCHEMA_VERSION[dataset]
    if schema_version != expected_schema:
        message = (
            f"Unexpected schema_version for '{dataset}': expected '{expected_schema}', "
            f"got '{schema_version}'."
        )
        raise SnapshotValidationError(message)

    row_counts_payload = manifest["row_counts"]
    try:
        row_counts = validate_as(dict[str, object], row_counts_payload)
    except IncomingDataError as exc:
        message = f"Manifest row_counts must be an object for dataset '{dataset}'."
        raise SnapshotValidationError(message) from exc
    _expect_int(row_counts, "raw")
    _expect_int(row_counts, "clean")

    artefacts_payload = manifest["artefacts"]
    try:
        artefacts = validate_as(dict[str, object], artefacts_payload)
    except IncomingDataError as exc:
        message = f"Manifest artefacts must be an object for dataset '{dataset}'."
        raise SnapshotValidationError(message) from exc
    for required_artefact in _required_artefact_keys(dataset):
        if required_artefact not in artefacts:
            message = (
                f"Manifest artefacts missing required key '{required_artefact}' "
                f"for dataset '{dataset}'."
            )
            raise SnapshotValidationError(message)
        value = artefacts[required_artefact]
        if not isinstance(value, str) or not value.strip():
            message = (
                f"Manifest artefacts key '{required_artefact}' must be a non-empty string "
                f"for dataset '{dataset}'."
            )
            raise SnapshotValidationError(message)


def _required_artefact_keys(dataset: str) -> tuple[str, ...]:
    if dataset == "sponsor":
        return ("raw", "clean", "register_stats", "manifest")
    return ("raw", "clean")


def _validate_csv_columns(
    *,
    clean_path: Path,
    required_columns: tuple[str, ...],
    label: str,
) -> None:
    with clean_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header_row = next(reader)
        except StopIteration as exc:
            message = f"{label} is empty: {clean_path}"
            raise SnapshotValidationError(message) from exc

    present = {column.strip() for column in header_row}
    required = set(required_columns)
    missing = sorted(required - present)
    if missing:
        message = f"{label}: Missing required columns: {missing} (file: {clean_path})."
        raise SnapshotValidationError(message)


def _expect_non_empty_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        message = f"Manifest field '{key}' must be a non-empty string."
        raise SnapshotValidationError(message)
    return value


def _expect_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        message = f"Manifest field '{key}' must be an integer."
        raise SnapshotValidationError(message)
    return value
