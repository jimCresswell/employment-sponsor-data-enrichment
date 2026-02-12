"""Snapshot-backed employee-count lookup boundary for scoring joins."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..exceptions import EmployeeCountSnapshotError, SnapshotArtefactMissingError
from ..io_validation import validate_as
from ..protocols import FileSystem
from ..schemas import validate_columns
from ..types import EmployeeCountCleanRow
from .snapshots import resolve_latest_snapshot_dir

EMPLOYEE_COUNT_DATASET = "employee_count"
EMPLOYEE_COUNT_SCHEMA_VERSION = "employee_count_v1"
EMPLOYEE_COUNT_CLEAN_COLUMNS = (
    "company_number",
    "employee_count",
    "employee_count_source",
    "employee_count_snapshot_date",
)
_SNAPSHOT_DATE_PATTERN = re.compile(r"20\d{2}-\d{2}-\d{2}")
_MANIFEST_REQUIRED_FIELDS = (
    "dataset",
    "snapshot_date",
    "source_url",
    "schema_version",
    "artefacts",
    "row_counts",
)


@dataclass(frozen=True)
class EmployeeCountSignal:
    """Employee-count signal with provenance."""

    employee_count: str
    employee_count_source: str
    employee_count_snapshot_date: str


@dataclass(frozen=True)
class EmployeeCountLookup:
    """Deterministic lookup keyed by Companies House company number."""

    signals_by_company_number: dict[str, EmployeeCountSignal]

    def signal_for_company_number(self, company_number: str) -> EmployeeCountSignal:
        key = company_number.strip()
        if key in self.signals_by_company_number:
            return self.signals_by_company_number[key]
        return EmployeeCountSignal("", "", "")


def _as_str(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _coerce_row(raw: dict[str, object]) -> EmployeeCountCleanRow:
    return {
        "company_number": _as_str(raw.get("company_number")),
        "employee_count": _as_str(raw.get("employee_count")),
        "employee_count_source": _as_str(raw.get("employee_count_source")),
        "employee_count_snapshot_date": _as_str(raw.get("employee_count_snapshot_date")),
    }


def _expect_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise EmployeeCountSnapshotError.manifest_field_must_be_integer(key)
    return value


def _expect_non_empty_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EmployeeCountSnapshotError.manifest_field_must_be_non_empty_string(key)
    return value.strip()


def _validate_artefacts(manifest: dict[str, object]) -> None:
    artefacts = validate_as(dict[str, object], manifest["artefacts"])
    for required_key in ("raw", "clean", "manifest"):
        value = artefacts.get(required_key)
        if not isinstance(value, str) or not value.strip():
            raise EmployeeCountSnapshotError.manifest_artefact_key_must_be_non_empty(required_key)


def _validate_manifest(*, manifest: dict[str, object], snapshot_date: str) -> None:
    for field in _MANIFEST_REQUIRED_FIELDS:
        if field not in manifest:
            raise EmployeeCountSnapshotError.manifest_missing_field(field)
    if _expect_non_empty_str(manifest, "dataset") != EMPLOYEE_COUNT_DATASET:
        raise EmployeeCountSnapshotError.manifest_dataset_mismatch()
    if _expect_non_empty_str(manifest, "snapshot_date") != snapshot_date:
        raise EmployeeCountSnapshotError.manifest_snapshot_date_mismatch()
    if _expect_non_empty_str(manifest, "schema_version") != EMPLOYEE_COUNT_SCHEMA_VERSION:
        raise EmployeeCountSnapshotError.manifest_schema_version_mismatch(
            EMPLOYEE_COUNT_SCHEMA_VERSION
        )
    _ = _expect_non_empty_str(manifest, "source_url")
    row_counts = validate_as(dict[str, object], manifest["row_counts"])
    _expect_int(row_counts, "raw")
    _expect_int(row_counts, "clean")
    _validate_artefacts(manifest)


def _parse_positive_employee_count(value: str, *, company_number: str) -> str:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise EmployeeCountSnapshotError.employee_count_must_be_positive_int(
            company_number
        ) from exc
    if parsed < 1:
        raise EmployeeCountSnapshotError.employee_count_must_be_positive_int(company_number)
    return str(parsed)


def _validate_signal_row(
    *,
    row: EmployeeCountCleanRow,
    snapshot_date: str,
) -> EmployeeCountSignal:
    company_number = row["company_number"]
    if not company_number:
        raise EmployeeCountSnapshotError.company_number_required()
    source = row["employee_count_source"]
    if not source:
        raise EmployeeCountSnapshotError.employee_count_source_required(company_number)
    row_snapshot_date = row["employee_count_snapshot_date"]
    if _SNAPSHOT_DATE_PATTERN.fullmatch(row_snapshot_date) is None:
        raise EmployeeCountSnapshotError.employee_count_snapshot_date_invalid(company_number)
    if row_snapshot_date != snapshot_date:
        raise EmployeeCountSnapshotError.employee_count_snapshot_date_mismatch()
    employee_count = _parse_positive_employee_count(
        row["employee_count"],
        company_number=company_number,
    )
    return EmployeeCountSignal(
        employee_count=employee_count,
        employee_count_source=source,
        employee_count_snapshot_date=row_snapshot_date,
    )


def _build_lookup(*, rows: list[EmployeeCountCleanRow], snapshot_date: str) -> EmployeeCountLookup:
    signals: dict[str, EmployeeCountSignal] = {}
    for row in rows:
        company_number = row["company_number"]
        signal = _validate_signal_row(row=row, snapshot_date=snapshot_date)
        existing = signals.get(company_number)
        if existing is not None and existing != signal:
            raise EmployeeCountSnapshotError.company_number_conflict(company_number)
        signals[company_number] = signal
    return EmployeeCountLookup(signals_by_company_number=signals)


def load_employee_count_lookup(*, snapshot_root: Path, fs: FileSystem) -> EmployeeCountLookup:
    """Load and validate the latest employee-count snapshot lookup."""
    snapshot_dir = resolve_latest_snapshot_dir(
        snapshot_root=snapshot_root,
        dataset=EMPLOYEE_COUNT_DATASET,
        fs=fs,
    )
    clean_path = snapshot_dir / "clean.csv"
    manifest_path = snapshot_dir / "manifest.json"
    if not fs.exists(clean_path):
        raise SnapshotArtefactMissingError(str(clean_path))
    if not fs.exists(manifest_path):
        raise SnapshotArtefactMissingError(str(manifest_path))

    manifest = fs.read_json(manifest_path)
    _validate_manifest(manifest=manifest, snapshot_date=snapshot_dir.name)

    df = fs.read_csv(clean_path).fillna("")
    validate_columns(
        list(df.columns),
        frozenset(EMPLOYEE_COUNT_CLEAN_COLUMNS),
        "employee_count clean.csv",
    )
    raw_rows = validate_as(list[dict[str, object]], df.to_dict(orient="records"))
    rows = [_coerce_row(raw) for raw in raw_rows]
    return _build_lookup(rows=rows, snapshot_date=snapshot_dir.name)
