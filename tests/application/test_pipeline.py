"""Tests for application pipeline orchestration."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.fakes import FakeHttpClient, InMemoryFileSystem
from tests.support.scoring_profiles import write_default_scoring_profile_catalog
from uk_sponsor_pipeline.application.pipeline import run_pipeline
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.exceptions import DependencyMissingError


def _write_employee_count_snapshot(
    *,
    fs: InMemoryFileSystem,
    snapshot_root: Path,
    snapshot_date: str = "2026-02-06",
) -> None:
    snapshot_dir = snapshot_root / "employee_count" / snapshot_date
    fs.write_csv(
        pd.DataFrame(
            [
                {
                    "company_number": "12345678",
                    "employee_count": "1200",
                    "employee_count_source": "ons_business_register",
                    "employee_count_snapshot_date": snapshot_date,
                }
            ]
        ),
        snapshot_dir / "clean.csv",
    )
    fs.write_csv(
        pd.DataFrame([{"company_number": "12345678", "employees": "1200"}]),
        snapshot_dir / "raw.csv",
    )
    fs.write_json(
        {
            "dataset": "employee_count",
            "snapshot_date": snapshot_date,
            "source_url": "https://example.com/employee_count.csv",
            "downloaded_at_utc": "2026-02-06T12:00:00+00:00",
            "last_updated_at_utc": "2026-02-06T12:05:00+00:00",
            "schema_version": "employee_count_v1",
            "sha256_hash_raw": "rawhash",
            "sha256_hash_clean": "cleanhash",
            "bytes_raw": 128,
            "row_counts": {"raw": 1, "clean": 1},
            "artefacts": {"raw": "raw.csv", "clean": "clean.csv", "manifest": "manifest.json"},
            "git_sha": "abc123",
            "tool_version": "0.1.0",
            "command_line": "uk-sponsor refresh-employee-count",
        },
        snapshot_dir / "manifest.json",
    )


def test_run_pipeline_cache_only_returns_outputs() -> None:
    fs = InMemoryFileSystem()
    snapshot_root = Path("data/cache/snapshots")
    _write_employee_count_snapshot(fs=fs, snapshot_root=snapshot_root)
    write_default_scoring_profile_catalog(
        fs=fs,
        path=Path("data/reference/scoring_profiles.json"),
    )
    register_path = Path("data/cache/snapshots/sponsor/2026-02-01/clean.csv")
    register_df = pd.DataFrame(
        {
            "Organisation Name": ["Acme Ltd"],
            "org_name_normalised": ["acme"],
            "has_multiple_towns": ["False"],
            "has_multiple_counties": ["False"],
            "Town/City": ["London"],
            "County": ["Greater London"],
            "Type & Rating": ["A rating"],
            "Route": ["Skilled Worker"],
            "raw_name_variants": ["Acme Ltd"],
        }
    )
    fs.write_csv(register_df, register_path)

    fake_http_client = FakeHttpClient()
    fake_http_client.responses = {
        "search/companies": {
            "items": [
                {
                    "company_number": "12345678",
                    "title": "ACME LTD",
                    "company_status": "active",
                    "address": {
                        "locality": "London",
                        "region": "Greater London",
                        "postal_code": "EC1A 1BB",
                    },
                }
            ]
        },
        "/company/": {
            "company_number": "12345678",
            "company_name": "ACME LTD",
            "company_status": "active",
            "type": "ltd",
            "date_of_creation": "2015-01-01",
            "sic_codes": ["62020"],
            "registered_office_address": {
                "locality": "London",
                "region": "Greater London",
                "postal_code": "EC1A 1BB",
            },
        },
    }

    result = run_pipeline(
        config=PipelineConfig(
            ch_api_key="test-key",
            ch_sleep_seconds=0,
            ch_min_match_score=0.0,
            ch_search_limit=5,
            ch_max_rpm=600,
            snapshot_root=str(snapshot_root),
        ),
        register_path=register_path,
        fs=fs,
        http_client=fake_http_client,
    )

    shortlist = fs.read_csv(result.usage["shortlist"])
    assert shortlist["Organisation Name"].tolist() == ["Acme Ltd"]


def test_run_pipeline_requires_filesystem() -> None:
    with pytest.raises(DependencyMissingError) as exc_info:
        run_pipeline(
            config=PipelineConfig(
                ch_api_key="test-key",
                ch_sleep_seconds=0,
                ch_min_match_score=0.0,
                ch_search_limit=5,
                ch_max_rpm=600,
            ),
            register_path=Path("data/cache/snapshots/sponsor/2026-02-01/clean.csv"),
            fs=None,
            http_client=FakeHttpClient(),
        )

    assert "FileSystem" in str(exc_info.value)
