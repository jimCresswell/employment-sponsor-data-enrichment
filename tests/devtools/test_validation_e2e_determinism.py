"""Tests for fixture e2e deterministic rerun helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from uk_sponsor_pipeline.devtools.validation_e2e_determinism import (
    DETERMINISTIC_ENRICH_OUTPUT_FILES,
    assert_deterministic_enrich_outputs,
    assert_resume_rerun_completed,
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_deterministic_output_set(root: Path, *, label: str) -> None:
    for filename in DETERMINISTIC_ENRICH_OUTPUT_FILES:
        _write_text(root / filename, f"{filename}:{label}\n")


def _write_resume_report(path: Path, *, status: str, processed_in_run: int, remaining: int) -> None:
    payload = {
        "status": status,
        "processed_in_run": processed_in_run,
        "remaining": remaining,
    }
    _write_text(path, json.dumps(payload))


def test_assert_deterministic_enrich_outputs_accepts_identical_outputs(tmp_path: Path) -> None:
    first_run = tmp_path / "run_one"
    second_run = tmp_path / "run_two"
    _write_deterministic_output_set(first_run, label="same")
    _write_deterministic_output_set(second_run, label="same")

    assert_deterministic_enrich_outputs(first_run, second_run)


def test_assert_deterministic_enrich_outputs_raises_for_missing_output(tmp_path: Path) -> None:
    first_run = tmp_path / "run_one"
    second_run = tmp_path / "run_two"
    _write_deterministic_output_set(first_run, label="same")
    _write_deterministic_output_set(second_run, label="same")
    (second_run / DETERMINISTIC_ENRICH_OUTPUT_FILES[0]).unlink()

    with pytest.raises(RuntimeError, match="Deterministic output is missing"):
        assert_deterministic_enrich_outputs(first_run, second_run)


def test_assert_deterministic_enrich_outputs_raises_for_content_mismatch(tmp_path: Path) -> None:
    first_run = tmp_path / "run_one"
    second_run = tmp_path / "run_two"
    _write_deterministic_output_set(first_run, label="same")
    _write_deterministic_output_set(second_run, label="same")
    _write_text(
        second_run / "sponsor_unmatched.csv",
        "changed-content\n",
    )

    with pytest.raises(RuntimeError, match="Deterministic output mismatch"):
        assert_deterministic_enrich_outputs(first_run, second_run)


def test_assert_resume_rerun_completed_accepts_complete_zero_remaining(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    _write_resume_report(report_path, status="complete", processed_in_run=0, remaining=0)

    assert_resume_rerun_completed(report_path)


def test_assert_resume_rerun_completed_raises_for_invalid_status(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    _write_resume_report(report_path, status="error", processed_in_run=0, remaining=0)

    with pytest.raises(RuntimeError, match="Resume rerun did not complete successfully"):
        assert_resume_rerun_completed(report_path)


def test_assert_resume_rerun_completed_raises_for_non_zero_processed_in_run(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "report.json"
    _write_resume_report(report_path, status="complete", processed_in_run=1, remaining=0)

    with pytest.raises(RuntimeError, match="processed_in_run=0"):
        assert_resume_rerun_completed(report_path)


def test_assert_resume_rerun_completed_raises_for_non_zero_remaining(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    _write_resume_report(report_path, status="complete", processed_in_run=0, remaining=1)

    with pytest.raises(RuntimeError, match="remaining=0"):
        assert_resume_rerun_completed(report_path)


def test_assert_resume_rerun_completed_raises_for_non_object_json(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    _write_text(report_path, "[]")

    with pytest.raises(RuntimeError, match="must be a JSON object"):
        assert_resume_rerun_completed(report_path)
