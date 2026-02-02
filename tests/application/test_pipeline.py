"""Tests for application pipeline orchestration."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tests.fakes import FakeHttpClient, InMemoryFileSystem
from uk_sponsor_pipeline.application.pipeline import run_pipeline
from uk_sponsor_pipeline.config import PipelineConfig


def test_run_pipeline_skips_download_and_returns_outputs() -> None:
    fs = InMemoryFileSystem()
    raw_dir = Path("data/raw")
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
    fs.write_csv(raw_df, raw_path)

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
        ),
        skip_download=True,
        fs=fs,
        http_client=fake_http_client,
    )

    assert result.extract is None
    shortlist = fs.read_csv(result.score["shortlist"])
    assert shortlist["Organisation Name"].tolist() == ["Acme Ltd"]
