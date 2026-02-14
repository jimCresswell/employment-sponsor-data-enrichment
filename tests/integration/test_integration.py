"""Integration-style test for the full pipeline with in-memory dependencies."""

from pathlib import Path

import pandas as pd

from tests.fakes import FakeHttpClient, InMemoryFileSystem
from tests.support.scoring_profiles import write_default_scoring_profile_catalog
from uk_sponsor_pipeline.application.transform_enrich import run_transform_enrich
from uk_sponsor_pipeline.application.transform_register import run_transform_register
from uk_sponsor_pipeline.application.transform_score import run_transform_score
from uk_sponsor_pipeline.application.usage import run_usage_shortlist
from uk_sponsor_pipeline.config import PipelineConfig


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
            "command_line": "uship refresh-employee-count",
        },
        snapshot_dir / "manifest.json",
    )


def test_pipeline_end_to_end_in_memory(
    in_memory_fs: InMemoryFileSystem, fake_http_client: FakeHttpClient
) -> None:
    snapshot_root = Path("data/cache/snapshots")
    _write_employee_count_snapshot(
        fs=in_memory_fs,
        snapshot_root=snapshot_root,
    )
    write_default_scoring_profile_catalog(
        fs=in_memory_fs,
        path=Path("data/reference/scoring_profiles.json"),
    )
    raw_dir = Path("raw")
    raw_path = raw_dir / "register.csv"
    raw_df = pd.DataFrame(
        {
            "Organisation Name": ["Acme Ltd"],
            "Town/City": ["London"],
            "County": ["Greater London"],
            "Type & Rating": ["A rating"],
            "Route": ["Skilled Worker"],
        }
    )
    in_memory_fs.write_csv(raw_df, raw_path)

    register_result = run_transform_register(
        raw_dir=raw_dir,
        out_path=Path("interim/sponsor_register_filtered.csv"),
        reports_dir=Path("reports"),
        fs=in_memory_fs,
    )

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

    enrich_outs = run_transform_enrich(
        register_path=register_result.output_path,
        out_dir=Path("processed"),
        cache_dir=Path("cache"),
        config=PipelineConfig(
            ch_api_key="test-key",
            ch_sleep_seconds=0,
            ch_min_match_score=0.0,
            ch_search_limit=5,
            ch_max_rpm=600,
        ),
        http_client=fake_http_client,
        resume=False,
        fs=in_memory_fs,
    )

    score_outs = run_transform_score(
        enriched_path=enrich_outs["enriched"],
        out_dir=Path("processed"),
        config=PipelineConfig(tech_score_threshold=0.0, snapshot_root=str(snapshot_root)),
        fs=in_memory_fs,
    )

    usage_outs = run_usage_shortlist(
        scored_path=score_outs["scored"],
        out_dir=Path("processed"),
        config=PipelineConfig(tech_score_threshold=0.0, snapshot_root=str(snapshot_root)),
        fs=in_memory_fs,
    )

    shortlist = in_memory_fs.read_csv(usage_outs["shortlist"])
    assert shortlist["Organisation Name"].tolist() == ["Acme Ltd"]
