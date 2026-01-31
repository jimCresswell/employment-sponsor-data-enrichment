"""Integration-style test for the full pipeline with in-memory dependencies."""

from pathlib import Path

import pandas as pd

from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.stages.stage1 import run_stage1
from uk_sponsor_pipeline.stages.stage2_companies_house import run_stage2
from uk_sponsor_pipeline.stages.stage3_scoring import run_stage3


def test_pipeline_end_to_end_in_memory(in_memory_fs, fake_http_client):
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

    stage1 = run_stage1(
        raw_dir=raw_dir,
        out_path=Path("interim/stage1.csv"),
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

    stage2 = run_stage2(
        stage1_path=stage1.output_path,
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

    stage3 = run_stage3(
        stage2_path=stage2["enriched"],
        out_dir=Path("processed"),
        config=PipelineConfig(tech_score_threshold=0.0),
        fs=in_memory_fs,
    )

    shortlist = in_memory_fs.read_csv(stage3["shortlist"])
    assert shortlist["Organisation Name"].tolist() == ["Acme Ltd"]
