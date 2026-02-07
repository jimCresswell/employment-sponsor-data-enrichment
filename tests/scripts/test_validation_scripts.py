"""Tests for validation script entrypoints."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from uk_sponsor_pipeline.application.companies_house_bulk import CANONICAL_HEADERS_V1
from uk_sponsor_pipeline.schemas import (
    TRANSFORM_ENRICH_CANDIDATES_COLUMNS,
    TRANSFORM_ENRICH_OUTPUT_COLUMNS,
    TRANSFORM_ENRICH_UNMATCHED_COLUMNS,
    TRANSFORM_REGISTER_OUTPUT_COLUMNS,
    TRANSFORM_SCORE_EXPLAIN_COLUMNS,
    TRANSFORM_SCORE_OUTPUT_COLUMNS,
)


def _write_csv(path: Path, headers: tuple[str, ...], row: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerow(row)


def _row(columns: tuple[str, ...]) -> list[str]:
    return [f"v{idx}" for idx in range(len(columns))]


def _run_script(script: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _write_valid_snapshot_root(root: Path) -> None:
    sponsor_dir = root / "sponsor" / "2026-02-06"
    _write_csv(
        sponsor_dir / "clean.csv",
        TRANSFORM_REGISTER_OUTPUT_COLUMNS,
        ["Acme Ltd", "acme", "False", "False", "London", "London", "A", "Worker", "Acme Ltd"],
    )
    _write_csv(sponsor_dir / "raw.csv", ("Organisation Name",), ["Acme Ltd"])
    (sponsor_dir / "register_stats.json").write_text("{}", encoding="utf-8")
    sponsor_manifest = {
        "dataset": "sponsor",
        "snapshot_date": "2026-02-06",
        "source_url": "https://example.com/sponsor.csv",
        "downloaded_at_utc": "2026-02-06T12:00:00+00:00",
        "last_updated_at_utc": "2026-02-06T12:01:00+00:00",
        "schema_version": "sponsor_clean_v1",
        "sha256_hash_raw": "raw",
        "sha256_hash_clean": "clean",
        "bytes_raw": 1,
        "row_counts": {"raw": 1, "clean": 1},
        "artefacts": {
            "raw": "raw.csv",
            "clean": "clean.csv",
            "register_stats": "register_stats.json",
            "manifest": "manifest.json",
        },
        "git_sha": "abc",
        "tool_version": "0.1.0",
        "command_line": "uk-sponsor refresh-sponsor",
    }
    (sponsor_dir / "manifest.json").write_text(json.dumps(sponsor_manifest), encoding="utf-8")

    companies_house_dir = root / "companies_house" / "2026-02-06"
    _write_csv(
        companies_house_dir / "clean.csv",
        tuple(CANONICAL_HEADERS_V1),
        _row(tuple(CANONICAL_HEADERS_V1)),
    )
    _write_csv(companies_house_dir / "raw.csv", ("CompanyName",), ["ACME LTD"])
    _write_csv(
        companies_house_dir / "index_tokens_a.csv",
        ("token", "company_number"),
        ["acme", "12345678"],
    )
    _write_csv(
        companies_house_dir / "profiles_1.csv",
        tuple(CANONICAL_HEADERS_V1),
        _row(tuple(CANONICAL_HEADERS_V1)),
    )
    companies_house_manifest = {
        "dataset": "companies_house",
        "snapshot_date": "2026-02-06",
        "source_url": "https://example.com/ch.zip",
        "downloaded_at_utc": "2026-02-06T12:00:00+00:00",
        "last_updated_at_utc": "2026-02-06T12:01:00+00:00",
        "schema_version": "ch_clean_v1",
        "sha256_hash_raw": "raw",
        "sha256_hash_clean": "clean",
        "bytes_raw": 1,
        "row_counts": {"raw": 1, "clean": 1},
        "artefacts": {
            "raw": "raw.csv",
            "clean": "clean.csv",
            "manifest": "manifest.json",
        },
        "git_sha": "abc",
        "tool_version": "0.1.0",
        "command_line": "uk-sponsor refresh-companies-house",
    }
    (companies_house_dir / "manifest.json").write_text(
        json.dumps(companies_house_manifest),
        encoding="utf-8",
    )


def _write_valid_output_dir(root: Path) -> None:
    _write_csv(
        root / "companies_house_enriched.csv",
        TRANSFORM_ENRICH_OUTPUT_COLUMNS,
        _row(TRANSFORM_ENRICH_OUTPUT_COLUMNS),
    )
    _write_csv(
        root / "companies_house_unmatched.csv",
        TRANSFORM_ENRICH_UNMATCHED_COLUMNS,
        _row(TRANSFORM_ENRICH_UNMATCHED_COLUMNS),
    )
    _write_csv(
        root / "companies_house_candidates_top3.csv",
        TRANSFORM_ENRICH_CANDIDATES_COLUMNS,
        _row(TRANSFORM_ENRICH_CANDIDATES_COLUMNS),
    )
    _write_csv(root / "companies_house_checkpoint.csv", ("Organisation Name",), ["Acme Ltd"])
    _write_csv(
        root / "companies_scored.csv",
        TRANSFORM_SCORE_OUTPUT_COLUMNS,
        _row(TRANSFORM_SCORE_OUTPUT_COLUMNS),
    )
    _write_csv(
        root / "companies_shortlist.csv",
        TRANSFORM_SCORE_OUTPUT_COLUMNS,
        _row(TRANSFORM_SCORE_OUTPUT_COLUMNS),
    )
    _write_csv(
        root / "companies_explain.csv",
        TRANSFORM_SCORE_EXPLAIN_COLUMNS,
        _row(TRANSFORM_SCORE_EXPLAIN_COLUMNS),
    )
    report = {
        "status": "complete",
        "error_message": "",
        "generated_at_utc": "2026-02-06T12:05:00+00:00",
        "run_started_at_utc": "2026-02-06T12:00:00+00:00",
        "run_finished_at_utc": "2026-02-06T12:05:00+00:00",
        "run_duration_seconds": 300.0,
        "register_path": "register.csv",
        "out_dir": "processed",
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
    (root / "companies_house_resume_report.json").write_text(json.dumps(report), encoding="utf-8")


def test_validation_check_snapshots_script_passes_for_valid_snapshots(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "snapshots"
    _write_valid_snapshot_root(snapshot_root)

    result = _run_script(
        Path("scripts/validation_check_snapshots.py"),
        ["--snapshot-root", str(snapshot_root)],
    )

    assert result.returncode == 0
    assert "PASS snapshot validation" in result.stdout


def test_validation_check_snapshots_script_fails_for_missing_root(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "missing"

    result = _run_script(
        Path("scripts/validation_check_snapshots.py"),
        ["--snapshot-root", str(snapshot_root)],
    )

    assert result.returncode != 0
    assert "FAIL snapshot validation" in result.stderr


def test_validation_check_outputs_script_passes_for_valid_outputs(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    _write_valid_output_dir(out_dir)

    result = _run_script(
        Path("scripts/validation_check_outputs.py"),
        ["--out-dir", str(out_dir)],
    )

    assert result.returncode == 0
    assert "PASS output validation" in result.stdout


def test_validation_check_outputs_script_fails_for_missing_dir(tmp_path: Path) -> None:
    out_dir = tmp_path / "missing"

    result = _run_script(
        Path("scripts/validation_check_outputs.py"),
        ["--out-dir", str(out_dir)],
    )

    assert result.returncode != 0
    assert "FAIL output validation" in result.stderr
