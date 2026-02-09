"""Processed output validation helpers for protocol checks."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from ..io_validation import IncomingDataError, validate_as
from ..schemas import (
    TRANSFORM_ENRICH_CANDIDATES_COLUMNS,
    TRANSFORM_ENRICH_OUTPUT_COLUMNS,
    TRANSFORM_ENRICH_UNMATCHED_COLUMNS,
    TRANSFORM_SCORE_EXPLAIN_COLUMNS,
    TRANSFORM_SCORE_OUTPUT_COLUMNS,
)
from ..types import TransformEnrichResumeReport

_ALLOWED_RESUME_STATUS = {"complete", "error", "interrupted"}


class OutputValidationError(ValueError):
    """Raised when output validation fails."""


@dataclass(frozen=True)
class OutputValidationResult:
    """Validation result for processed outputs."""

    out_dir: Path
    validated_files: tuple[Path, ...]
    resume_status: str


def validate_outputs(out_dir: str | Path) -> OutputValidationResult:
    """Validate required processed outputs and resume metadata."""
    root = Path(out_dir)
    if not root.exists() or not root.is_dir():
        message = f"Output directory does not exist: {root}"
        raise OutputValidationError(message)

    required_csv_outputs = (
        ("sponsor_enriched.csv", TRANSFORM_ENRICH_OUTPUT_COLUMNS),
        ("sponsor_unmatched.csv", TRANSFORM_ENRICH_UNMATCHED_COLUMNS),
        ("sponsor_match_candidates_top3.csv", TRANSFORM_ENRICH_CANDIDATES_COLUMNS),
        ("sponsor_enrich_checkpoint.csv", ("Organisation Name",)),
        ("companies_scored.csv", TRANSFORM_SCORE_OUTPUT_COLUMNS),
        ("companies_shortlist.csv", TRANSFORM_SCORE_OUTPUT_COLUMNS),
        ("companies_explain.csv", TRANSFORM_SCORE_EXPLAIN_COLUMNS),
    )

    validated_paths: list[Path] = []
    for filename, required_columns in required_csv_outputs:
        path = root / filename
        if not path.exists():
            message = f"Missing required output file: {path}"
            raise OutputValidationError(message)
        _validate_csv_columns(path=path, required_columns=required_columns)
        validated_paths.append(path)

    report_path = root / "sponsor_enrich_resume_report.json"
    if not report_path.exists():
        message = f"Missing required output file: {report_path}"
        raise OutputValidationError(message)
    resume_status = _validate_resume_report(report_path)
    validated_paths.append(report_path)

    return OutputValidationResult(
        out_dir=root,
        validated_files=tuple(validated_paths),
        resume_status=resume_status,
    )


def _validate_csv_columns(*, path: Path, required_columns: tuple[str, ...]) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header_row = next(reader)
        except StopIteration as exc:
            message = f"CSV output is empty: {path}"
            raise OutputValidationError(message) from exc

    present = {column.strip() for column in header_row}
    required = set(required_columns)
    missing = sorted(required - present)
    if missing:
        message = f"{path.name}: Missing required columns: {missing} (file: {path})."
        raise OutputValidationError(message)


def _validate_resume_report(path: Path) -> str:
    try:
        payload_raw: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        message = f"Resume report is not valid JSON: {path}"
        raise OutputValidationError(message) from exc
    try:
        payload = validate_as(dict[str, object], payload_raw)
    except IncomingDataError as exc:
        message = f"Resume report must be an object: {path}"
        raise OutputValidationError(message) from exc
    payload_obj: object = payload
    try:
        report = validate_as(TransformEnrichResumeReport, payload_obj)
    except IncomingDataError as exc:
        message = f"Resume report is malformed: {path}"
        raise OutputValidationError(message) from exc

    status = report["status"]
    if status not in _ALLOWED_RESUME_STATUS:
        message = (
            f"Resume report status is invalid: '{status}' (allowed: {_allowed_status_list()})."
        )
        raise OutputValidationError(message)
    return status


def _allowed_status_list() -> str:
    return ", ".join(sorted(_ALLOWED_RESUME_STATUS))
