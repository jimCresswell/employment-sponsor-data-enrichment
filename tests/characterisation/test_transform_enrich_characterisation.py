"""Characterisation tests for Transform enrich outputs and error reporting."""

from pathlib import Path

import pandas as pd
import pytest

from tests.fakes import FakeHttpClient, InMemoryFileSystem
from uk_sponsor_pipeline.application.transform_enrich import run_transform_enrich
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.exceptions import AuthenticationError
from uk_sponsor_pipeline.infrastructure.io.validation import validate_as
from uk_sponsor_pipeline.schemas import (
    TRANSFORM_ENRICH_CANDIDATES_COLUMNS,
    TRANSFORM_ENRICH_OUTPUT_COLUMNS,
)
from uk_sponsor_pipeline.types import TransformEnrichResumeReport


def _transform_register_input_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Organisation Name": "Acme Ltd",
                "org_name_normalised": "acme",
                "has_multiple_towns": "False",
                "has_multiple_counties": "False",
                "Town/City": "London",
                "County": "Greater London",
                "Type & Rating": "A rating",
                "Route": "Skilled Worker",
                "raw_name_variants": "Acme Ltd",
            }
        ]
    )


def test_transform_enrich_outputs_are_deterministic(
    in_memory_fs: InMemoryFileSystem,
    fake_http_client: FakeHttpClient,
    sample_ch_search_response: dict[str, object],
    sample_ch_profile_response: dict[str, object],
) -> None:
    register_path = Path("data/interim/sponsor_register_filtered.csv")
    out_dir = Path("data/processed")
    cache_dir = Path("data/cache")

    in_memory_fs.write_csv(_transform_register_input_df(), register_path)

    fake_http_client.responses = {
        "search/companies": sample_ch_search_response,
        "company/12345678": sample_ch_profile_response,
    }

    config = PipelineConfig(
        ch_api_key="test-key",
        ch_sleep_seconds=0,
        ch_max_rpm=600,
        ch_min_match_score=0.0,
        ch_search_limit=5,
        ch_batch_size=1,
    )

    outs = run_transform_enrich(
        register_path=register_path,
        out_dir=out_dir,
        cache_dir=cache_dir,
        config=config,
        http_client=fake_http_client,
        resume=False,
        fs=in_memory_fs,
    )

    enriched_df = in_memory_fs.read_csv(outs["enriched"])
    candidates_df = in_memory_fs.read_csv(outs["candidates"])
    report = validate_as(
        TransformEnrichResumeReport,
        in_memory_fs.read_json(outs["resume_report"]),
    )

    assert list(enriched_df.columns) == list(TRANSFORM_ENRICH_OUTPUT_COLUMNS)
    assert enriched_df.loc[0, "match_status"] == "matched"
    assert enriched_df.loc[0, "ch_company_number"] == "12345678"
    assert enriched_df.loc[0, "ch_sic_codes"] == "62020;62090"

    assert list(candidates_df.columns) == list(TRANSFORM_ENRICH_CANDIDATES_COLUMNS)
    assert candidates_df.loc[0, "candidate_company_number"] == "12345678"

    assert report["status"] == "complete"
    assert report["processed_in_run"] == 1
    assert report["processed_total"] == 1
    assert report["batch_size"] == 1
    assert report["batch_start"] == 1
    assert report["batch_range"] == {"start": 1, "end": 1}
    assert report["resume_command"]
    assert report["run_started_at_utc"]
    assert report["run_finished_at_utc"]


def test_transform_enrich_search_errors_write_resume_report(
    in_memory_fs: InMemoryFileSystem,
) -> None:
    register_path = Path("data/interim/sponsor_register_filtered.csv")
    out_dir = Path("data/processed")
    cache_dir = Path("data/cache")

    in_memory_fs.write_csv(_transform_register_input_df(), register_path)

    class FailingHttp:
        def get_json(self, url: str, cache_key: str | None = None) -> dict[str, object]:
            raise AuthenticationError("invalid key")

    config = PipelineConfig(
        ch_api_key="test-key",
        ch_sleep_seconds=0,
        ch_max_rpm=600,
        ch_min_match_score=0.0,
        ch_search_limit=5,
    )

    with pytest.raises(AuthenticationError):
        run_transform_enrich(
            register_path=register_path,
            out_dir=out_dir,
            cache_dir=cache_dir,
            config=config,
            http_client=FailingHttp(),
            resume=True,
            fs=in_memory_fs,
        )

    report = validate_as(
        TransformEnrichResumeReport,
        in_memory_fs.read_json(out_dir / "companies_house_resume_report.json"),
    )
    assert report["status"] == "error"
    assert "invalid key" in report["error_message"]
    assert report["processed_total"] == 0
    assert report["remaining"] == 1
