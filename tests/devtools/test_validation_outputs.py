"""Tests for processed output validation helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from uk_sponsor_pipeline.devtools.validation_outputs import (
    OutputValidationError,
    validate_outputs,
)
from uk_sponsor_pipeline.schemas import (
    TRANSFORM_ENRICH_CANDIDATES_COLUMNS,
    TRANSFORM_ENRICH_OUTPUT_COLUMNS,
    TRANSFORM_ENRICH_UNMATCHED_COLUMNS,
    TRANSFORM_SCORE_EXPLAIN_COLUMNS,
    TRANSFORM_SCORE_OUTPUT_COLUMNS,
)


def _write_csv(path: Path, headers: tuple[str, ...], row: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerow(row)


def _row(headers: tuple[str, ...]) -> list[str]:
    return [f"value_{idx}" for idx in range(len(headers))]


def _resume_report(status: str = "complete") -> dict[str, object]:
    return {
        "status": status,
        "error_message": "",
        "generated_at_utc": "2026-02-06T12:05:00+00:00",
        "run_started_at_utc": "2026-02-06T12:00:00+00:00",
        "run_finished_at_utc": "2026-02-06T12:05:00+00:00",
        "run_duration_seconds": 300.0,
        "register_path": "data/cache/snapshots/sponsor/2026-02-06/clean.csv",
        "out_dir": "data/processed",
        "batch_size": 100,
        "batch_start": 1,
        "batch_count": None,
        "batch_range": {"start": 1, "end": 1},
        "total_register_orgs": 1,
        "total_unprocessed_at_start": 1,
        "total_batches_at_start": 1,
        "total_batches_overall": 1,
        "overall_batch_range": {"start": 1, "end": 1},
        "selected_batches": 1,
        "processed_in_run": 1,
        "processed_total": 1,
        "remaining": 0,
        "resume_command": "uv run uk-sponsor transform-enrich --resume",
    }


def _write_valid_outputs(out_dir: Path) -> None:
    _write_csv(
        out_dir / "sponsor_enriched.csv",
        TRANSFORM_ENRICH_OUTPUT_COLUMNS,
        _row(TRANSFORM_ENRICH_OUTPUT_COLUMNS),
    )
    _write_csv(
        out_dir / "sponsor_unmatched.csv",
        TRANSFORM_ENRICH_UNMATCHED_COLUMNS,
        _row(TRANSFORM_ENRICH_UNMATCHED_COLUMNS),
    )
    _write_csv(
        out_dir / "sponsor_match_candidates_top3.csv",
        TRANSFORM_ENRICH_CANDIDATES_COLUMNS,
        _row(TRANSFORM_ENRICH_CANDIDATES_COLUMNS),
    )
    _write_csv(
        out_dir / "sponsor_enrich_checkpoint.csv",
        ("Organisation Name",),
        ["Acme Ltd"],
    )
    (out_dir / "sponsor_enrich_resume_report.json").write_text(
        json.dumps(_resume_report()),
        encoding="utf-8",
    )
    _write_csv(
        out_dir / "companies_scored.csv",
        TRANSFORM_SCORE_OUTPUT_COLUMNS,
        _row(TRANSFORM_SCORE_OUTPUT_COLUMNS),
    )
    _write_csv(
        out_dir / "companies_shortlist.csv",
        TRANSFORM_SCORE_OUTPUT_COLUMNS,
        _row(TRANSFORM_SCORE_OUTPUT_COLUMNS),
    )
    _write_csv(
        out_dir / "companies_explain.csv",
        TRANSFORM_SCORE_EXPLAIN_COLUMNS,
        _row(TRANSFORM_SCORE_EXPLAIN_COLUMNS),
    )


def test_validate_outputs_accepts_valid_processed_outputs(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    _write_valid_outputs(out_dir)

    result = validate_outputs(out_dir)

    assert result.out_dir == out_dir
    assert result.resume_status == "complete"
    assert len(result.validated_files) == 8


def test_validate_outputs_raises_for_missing_required_file(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    _write_valid_outputs(out_dir)
    (out_dir / "companies_scored.csv").unlink()

    with pytest.raises(OutputValidationError, match="Missing required output file"):
        validate_outputs(out_dir)


def test_validate_outputs_raises_for_missing_required_columns(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    _write_valid_outputs(out_dir)
    _write_csv(out_dir / "companies_scored.csv", ("Organisation Name",), ["Acme Ltd"])

    with pytest.raises(OutputValidationError, match="Missing required columns"):
        validate_outputs(out_dir)


def test_validate_outputs_raises_for_malformed_resume_report(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    _write_valid_outputs(out_dir)
    (out_dir / "sponsor_enrich_resume_report.json").write_text("[]", encoding="utf-8")

    with pytest.raises(OutputValidationError, match="Resume report must be an object"):
        validate_outputs(out_dir)


def test_validate_outputs_raises_for_invalid_resume_status(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    _write_valid_outputs(out_dir)
    (out_dir / "sponsor_enrich_resume_report.json").write_text(
        json.dumps(_resume_report(status="partial")),
        encoding="utf-8",
    )

    with pytest.raises(OutputValidationError, match="Resume report status is invalid"):
        validate_outputs(out_dir)
