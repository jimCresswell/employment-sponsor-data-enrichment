"""Deterministic rerun checks for fixture-driven e2e validation."""

from __future__ import annotations

import json
from pathlib import Path

from ..io_validation import IncomingDataError, validate_as

DETERMINISTIC_ENRICH_OUTPUT_FILES: tuple[str, ...] = (
    "sponsor_enriched.csv",
    "sponsor_unmatched.csv",
    "sponsor_match_candidates_top3.csv",
    "sponsor_enrich_checkpoint.csv",
)


def assert_deterministic_enrich_outputs(first_run_dir: Path, second_run_dir: Path) -> None:
    """Assert that deterministic enrich artefacts are byte-identical across reruns."""
    for filename in DETERMINISTIC_ENRICH_OUTPUT_FILES:
        first_path = first_run_dir / filename
        second_path = second_run_dir / filename
        _require_file(first_path)
        _require_file(second_path)
        first_bytes = first_path.read_bytes()
        second_bytes = second_path.read_bytes()
        if first_bytes != second_bytes:
            message = f"Deterministic output mismatch for {filename}: {first_path} != {second_path}"
            raise RuntimeError(message)


def assert_resume_rerun_completed(report_path: Path) -> None:
    """Assert that a resume rerun completed with no additional work remaining."""
    _require_file(report_path)
    try:
        raw_payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        message = f"Resume report is not valid JSON: {report_path}"
        raise RuntimeError(message) from exc
    try:
        payload = validate_as(dict[str, object], raw_payload)
    except IncomingDataError as exc:
        message = f"Resume report must be a JSON object: {report_path}"
        raise RuntimeError(message) from exc
    status = payload.get("status")
    if not isinstance(status, str) or status != "complete":
        message = f"Resume rerun did not complete successfully: status={status!r} ({report_path})"
        raise RuntimeError(message)

    try:
        processed_in_run = _require_int_field(
            payload=payload,
            key="processed_in_run",
            path=report_path,
        )
        remaining = _require_int_field(
            payload=payload,
            key="remaining",
            path=report_path,
        )
    except TypeError as exc:
        raise RuntimeError(str(exc)) from exc
    if processed_in_run != 0:
        message = (
            "Resume rerun must report processed_in_run=0 after completion: "
            f"got {processed_in_run} ({report_path})"
        )
        raise RuntimeError(message)
    if remaining != 0:
        message = (
            "Resume rerun must report remaining=0 after completion: "
            f"got {remaining} ({report_path})"
        )
        raise RuntimeError(message)


def _require_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        message = f"Deterministic output is missing: {path}"
        raise RuntimeError(message)


def _require_int_field(*, payload: dict[str, object], key: str, path: Path) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        message = f"Resume report field must be an integer: {key} ({path})"
        raise TypeError(message)
    return value
