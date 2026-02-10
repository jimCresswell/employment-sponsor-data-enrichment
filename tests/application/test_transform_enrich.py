"""Tests for Transform enrich Companies House integration."""

import csv
import io
from datetime import datetime, tzinfo
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from tests.fakes import FakeHttpClient, InMemoryFileSystem
from uk_sponsor_pipeline.application import transform_enrich as s2
from uk_sponsor_pipeline.application.companies_house_bulk import CANONICAL_HEADERS_V1
from uk_sponsor_pipeline.application.transform_enrich import run_transform_enrich
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.domain.companies_house import (
    CandidateMatch,
    MatchScore,
    NormaliseFn,
    SimilarityFn,
)
from uk_sponsor_pipeline.exceptions import (
    AuthenticationError,
    CircuitBreakerOpen,
    CompaniesHouseProfileError,
    DependencyMissingError,
    InvalidSourceTypeError,
    PipelineConfigMissingError,
    RateLimitError,
)
from uk_sponsor_pipeline.infrastructure import LocalFileSystem
from uk_sponsor_pipeline.io_validation import validate_as
from uk_sponsor_pipeline.protocols import FileSystem, HttpClient
from uk_sponsor_pipeline.schemas import (
    TRANSFORM_ENRICH_CANDIDATES_COLUMNS,
    TRANSFORM_ENRICH_OUTPUT_COLUMNS,
)
from uk_sponsor_pipeline.types import CompanyProfile, SearchItem, TransformEnrichResumeReport


class TestTransformEnrichAuthIntegration:
    """Integration tests for Transform enrich authentication."""

    def test_api_key_is_passed_to_session(self, tmp_path: Path) -> None:
        """Verify the API key from config is correctly added to session headers."""
        fs = LocalFileSystem()
        # Create minimal transform_register input
        transform_register_csv = tmp_path / "sponsor_register_filtered.csv"
        transform_register_csv.write_text(
            "Organisation Name,org_name_normalised,has_multiple_towns,has_multiple_counties,"
            "Town/City,County,Type & Rating,Route,raw_name_variants\n"
            "Test Company Ltd,test company,False,False,London,Greater London,"
            "A rating,Skilled Worker,Test Company Ltd\n"
        )

        # Create a config with a known API key
        test_api_key = "test-api-key-for-verification"
        config = PipelineConfig(
            ch_api_key=test_api_key,
            ch_sleep_seconds=0,
            ch_max_rpm=600,
            ch_min_match_score=0.72,
            ch_search_limit=5,
        )

        # Create a mock HTTP client to capture what gets called
        mock_http = MagicMock()
        mock_http.get_json.return_value = {"items": []}

        # Run transform_enrich with our mock
        out_dir = tmp_path / "out"
        cache_dir = tmp_path / "cache"

        run_transform_enrich(
            register_path=transform_register_csv,
            out_dir=out_dir,
            cache_dir=cache_dir,
            config=config,
            http_client=mock_http,
            resume=False,
            fs=fs,
        )

        # Verify http_client.get_json was called (meaning config was used)
        assert mock_http.get_json.called


def test_transform_enrich_outputs_and_resume_report(
    in_memory_fs: InMemoryFileSystem,
    fake_http_client: FakeHttpClient,
    sample_ch_search_response: dict[str, object],
    sample_ch_profile_response: dict[str, object],
) -> None:
    register_path = Path("data/interim/sponsor_register_filtered.csv")
    out_dir = Path("data/processed")
    cache_dir = Path("data/cache")

    in_memory_fs.write_csv(
        pd.DataFrame(
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
        ),
        register_path,
    )

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


class TestTransformEnrichCandidateOrdering:
    """Tests for candidate ranking across multiple query variants."""

    def test_candidates_sorted_across_queries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        transform_register_csv = tmp_path / "sponsor_register_filtered.csv"
        transform_register_csv.write_text(
            "Organisation Name,org_name_normalised,has_multiple_towns,has_multiple_counties,"
            "Town/City,County,Type & Rating,Route,raw_name_variants\n"
            "Acme Ltd,acme,False,False,London,Greater London,A rating,Skilled Worker,Acme Ltd\n"
        )

        config = PipelineConfig(
            ch_api_key="test-key",
            ch_sleep_seconds=0,
            ch_max_rpm=600,
            ch_min_match_score=1.0,  # Force unmatched to avoid profile fetch
            ch_search_limit=5,
        )

        class DummyHttp:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def get_json(self, url: str, cache_key: str | None = None) -> dict[str, object]:
                self.calls.append(url)
                return {"items": []}

        def fake_variants(org: str) -> list[str]:
            return ["q1", "q2"]

        monkeypatch.setattr(s2, "generate_query_variants", fake_variants)

        scores = [
            [
                s2.CandidateMatch(
                    company_number="1",
                    title="Candidate One",
                    status="active",
                    locality="London",
                    region="Greater London",
                    postcode="EC1A 1BB",
                    score=s2.MatchScore(0.6, 0.5, 0.05, 0.03, 0.02),
                    query_used="q1",
                )
            ],
            [
                s2.CandidateMatch(
                    company_number="2",
                    title="Candidate Two",
                    status="active",
                    locality="London",
                    region="Greater London",
                    postcode="EC1A 1BB",
                    score=s2.MatchScore(0.7, 0.6, 0.05, 0.03, 0.02),
                    query_used="q2",
                )
            ],
        ]

        def fake_score_candidates(
            *,
            org_norm: str,
            town_norm: str,
            county_norm: str,
            items: list[SearchItem],
            query_used: str,
            similarity_fn: SimilarityFn,
            normalise_fn: NormaliseFn,
        ) -> list[CandidateMatch]:
            return scores.pop(0)

        monkeypatch.setattr(s2, "score_candidates", fake_score_candidates)

        out_dir = tmp_path / "out"
        outs = run_transform_enrich(
            register_path=transform_register_csv,
            out_dir=out_dir,
            cache_dir=tmp_path / "cache",
            config=config,
            http_client=DummyHttp(),
            resume=False,
            fs=LocalFileSystem(),
        )

        candidates_df = pd.read_csv(outs["candidates"], dtype=str).fillna("")
        top_score = float(str(candidates_df.loc[0, "candidate_score"]))
        assert top_score == 0.7


class TestTransformEnrichResume:
    """Tests for batching, incremental output, and resume logic."""

    def test_resume_skips_processed_orgs(
        self,
        in_memory_fs: InMemoryFileSystem,
        fake_http_client: FakeHttpClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        register_path = Path("data/interim/sponsor_register_filtered.csv")
        out_dir = Path("data/processed")
        cache_dir = Path("data/cache/companies_house")

        df = pd.DataFrame(
            [
                {
                    "Organisation Name": "Alpha Ltd",
                    "org_name_normalised": "alpha ltd",
                    "has_multiple_towns": "False",
                    "has_multiple_counties": "False",
                    "Town/City": "London",
                    "County": "Greater London",
                    "Type & Rating": "A rating",
                    "Route": "Skilled Worker",
                    "raw_name_variants": "Alpha Ltd",
                },
                {
                    "Organisation Name": "Beta Ltd",
                    "org_name_normalised": "beta ltd",
                    "has_multiple_towns": "False",
                    "has_multiple_counties": "False",
                    "Town/City": "Manchester",
                    "County": "Greater Manchester",
                    "Type & Rating": "A rating",
                    "Route": "Skilled Worker",
                    "raw_name_variants": "Beta Ltd",
                },
            ]
        )
        in_memory_fs.write_csv(df, register_path)

        config = PipelineConfig(
            ch_api_key="test-key",
            ch_sleep_seconds=0,
            ch_max_rpm=600,
            ch_min_match_score=0.9,  # Force unmatched path
            ch_search_limit=1,
            ch_batch_size=1,  # Flush per org to exercise append
        )

        fake_http_client.responses = {"search/companies": {"items": []}}

        def fake_variants(org: str) -> list[str]:
            return [org]

        monkeypatch.setattr(s2, "generate_query_variants", fake_variants)

        def fake_score_candidates(
            *,
            org_norm: str,
            town_norm: str,
            county_norm: str,
            items: list[SearchItem],
            query_used: str,
            similarity_fn: SimilarityFn,
            normalise_fn: NormaliseFn,
        ) -> list[CandidateMatch]:
            score = MatchScore(0.5, 0.5, 0.0, 0.0, 0.0)
            return [
                CandidateMatch(
                    company_number="00000001",
                    title=f"{org_norm} Ltd",
                    status="active",
                    locality="",
                    region="",
                    postcode="",
                    score=score,
                    query_used=query_used,
                )
            ]

        monkeypatch.setattr(s2, "score_candidates", fake_score_candidates)

        run_transform_enrich(
            register_path=register_path,
            out_dir=out_dir,
            cache_dir=cache_dir,
            config=config,
            http_client=fake_http_client,
            resume=True,
            fs=in_memory_fs,
        )

        unmatched_df = in_memory_fs.read_csv(out_dir / "sponsor_unmatched.csv")
        checkpoint_df = in_memory_fs.read_csv(out_dir / "sponsor_enrich_checkpoint.csv")
        candidates_df = in_memory_fs.read_csv(out_dir / "sponsor_match_candidates_top3.csv")

        assert len(unmatched_df) == 2
        assert len(checkpoint_df) == 2
        assert len(candidates_df) == 2
        assert sorted(checkpoint_df["Organisation Name"].tolist()) == ["Alpha Ltd", "Beta Ltd"]

        class FailingHttp:
            calls = 0

            def get_json(self, url: str, cache_key: str | None = None) -> dict[str, object]:
                self.calls += 1
                pytest.fail("Should not call HTTP client when resuming")

        failing_http = FailingHttp()

        run_transform_enrich(
            register_path=register_path,
            out_dir=out_dir,
            cache_dir=cache_dir,
            config=config,
            http_client=failing_http,
            resume=True,
            fs=in_memory_fs,
        )

        assert failing_http.calls == 0

    def test_batch_start_and_count_select_subset(
        self,
        in_memory_fs: InMemoryFileSystem,
        fake_http_client: FakeHttpClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        register_path = Path("data/interim/sponsor_register_filtered.csv")
        out_dir = Path("data/processed")
        cache_dir = Path("data/cache/companies_house")

        df = pd.DataFrame(
            [
                {
                    "Organisation Name": "Alpha Ltd",
                    "org_name_normalised": "alpha ltd",
                    "has_multiple_towns": "False",
                    "has_multiple_counties": "False",
                    "Town/City": "London",
                    "County": "Greater London",
                    "Type & Rating": "A rating",
                    "Route": "Skilled Worker",
                    "raw_name_variants": "Alpha Ltd",
                },
                {
                    "Organisation Name": "Beta Ltd",
                    "org_name_normalised": "beta ltd",
                    "has_multiple_towns": "False",
                    "has_multiple_counties": "False",
                    "Town/City": "Manchester",
                    "County": "Greater Manchester",
                    "Type & Rating": "A rating",
                    "Route": "Skilled Worker",
                    "raw_name_variants": "Beta Ltd",
                },
                {
                    "Organisation Name": "Gamma Ltd",
                    "org_name_normalised": "gamma ltd",
                    "has_multiple_towns": "False",
                    "has_multiple_counties": "False",
                    "Town/City": "Leeds",
                    "County": "West Yorkshire",
                    "Type & Rating": "A rating",
                    "Route": "Skilled Worker",
                    "raw_name_variants": "Gamma Ltd",
                },
            ]
        )
        in_memory_fs.write_csv(df, register_path)

        config = PipelineConfig(
            ch_api_key="test-key",
            ch_sleep_seconds=0,
            ch_max_rpm=600,
            ch_min_match_score=0.9,  # Force unmatched path
            ch_search_limit=1,
            ch_batch_size=1,
        )

        fake_http_client.responses = {"search/companies": {"items": []}}

        def fake_variants(org: str) -> list[str]:
            return [org]

        monkeypatch.setattr(s2, "generate_query_variants", fake_variants)

        def fake_score_candidates(
            *,
            org_norm: str,
            town_norm: str,
            county_norm: str,
            items: list[SearchItem],
            query_used: str,
            similarity_fn: SimilarityFn,
            normalise_fn: NormaliseFn,
        ) -> list[CandidateMatch]:
            score = MatchScore(0.5, 0.5, 0.0, 0.0, 0.0)
            return [
                CandidateMatch(
                    company_number="00000001",
                    title=f"{org_norm} Ltd",
                    status="active",
                    locality="",
                    region="",
                    postcode="",
                    score=score,
                    query_used=query_used,
                )
            ]

        monkeypatch.setattr(s2, "score_candidates", fake_score_candidates)

        outs = run_transform_enrich(
            register_path=register_path,
            out_dir=out_dir,
            cache_dir=cache_dir,
            config=config,
            http_client=fake_http_client,
            resume=False,
            fs=in_memory_fs,
            batch_start=2,
            batch_count=1,
        )

        checkpoint_df = in_memory_fs.read_csv(outs["checkpoint"])
        unmatched_df = in_memory_fs.read_csv(outs["unmatched"])
        report = validate_as(
            TransformEnrichResumeReport,
            in_memory_fs.read_json(outs["resume_report"]),
        )

        assert checkpoint_df["Organisation Name"].tolist() == ["Beta Ltd"]
        assert unmatched_df["Organisation Name"].tolist() == ["Beta Ltd"]
        assert report["processed_in_run"] == 1
        assert report["batch_start"] == 2
        assert report["selected_batches"] == 1
        assert report["total_batches_overall"] == 3
        assert report["overall_batch_range"] == {"start": 2, "end": 2}
        assert report["run_started_at_utc"]
        assert report["run_finished_at_utc"]
        assert report["run_duration_seconds"] >= 0


class TestTransformEnrichFailFast:
    """Ensure fatal search errors stop the run and can be resumed later."""

    @pytest.mark.parametrize(
        ("exc_type", "exc_args"),
        [
            (AuthenticationError, ("invalid key",)),
            (RateLimitError, (60,)),
            (CircuitBreakerOpen, (5, 5)),
        ],
    )
    def test_search_errors_fail_fast(
        self,
        in_memory_fs: InMemoryFileSystem,
        exc_type: type[Exception],
        exc_args: tuple[object, ...],
    ) -> None:
        register_path = Path("data/interim/sponsor_register_filtered.csv")
        in_memory_fs.write_csv(
            pd.DataFrame(
                [
                    {
                        "Organisation Name": "Failing Co",
                        "org_name_normalised": "failing co",
                        "has_multiple_towns": "False",
                        "has_multiple_counties": "False",
                        "Town/City": "London",
                        "County": "Greater London",
                        "Type & Rating": "A rating",
                        "Route": "Skilled Worker",
                        "raw_name_variants": "Failing Co",
                    }
                ]
            ),
            register_path,
        )

        class FailingHttp:
            def get_json(self, url: str, cache_key: str | None = None) -> dict[str, object]:
                raise exc_type(*exc_args)

        config = PipelineConfig(
            ch_api_key="test-key",
            ch_sleep_seconds=0,
            ch_max_rpm=600,
            ch_min_match_score=0.0,
            ch_search_limit=1,
        )

        with pytest.raises(exc_type):
            run_transform_enrich(
                register_path=register_path,
                out_dir=Path("data/processed"),
                cache_dir=Path("data/cache"),
                config=config,
                http_client=FailingHttp(),
                resume=False,
                fs=in_memory_fs,
            )


def test_transform_enrich_search_errors_write_resume_report(
    in_memory_fs: InMemoryFileSystem,
) -> None:
    register_path = Path("data/interim/sponsor_register_filtered.csv")
    out_dir = Path("data/processed")
    cache_dir = Path("data/cache")

    in_memory_fs.write_csv(
        pd.DataFrame(
            [
                {
                    "Organisation Name": "Failing Co",
                    "org_name_normalised": "failing co",
                    "has_multiple_towns": "False",
                    "has_multiple_counties": "False",
                    "Town/City": "London",
                    "County": "Greater London",
                    "Type & Rating": "A rating",
                    "Route": "Skilled Worker",
                    "raw_name_variants": "Failing Co",
                }
            ]
        ),
        register_path,
    )

    class FailingHttp:
        def get_json(self, url: str, cache_key: str | None = None) -> dict[str, object]:
            raise AuthenticationError.invalid_key()

    config = PipelineConfig(
        ch_api_key="test-key",
        ch_sleep_seconds=0,
        ch_max_rpm=600,
        ch_min_match_score=0.0,
        ch_search_limit=1,
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
        in_memory_fs.read_json(out_dir / "sponsor_enrich_resume_report.json"),
    )
    assert report["status"] == "error"
    assert "invalid key" in report["error_message"]
    assert report["processed_total"] == 0
    assert report["remaining"] == 1


def test_transform_enrich_requires_config() -> None:
    with pytest.raises(PipelineConfigMissingError) as exc_info:
        run_transform_enrich()
    assert "PipelineConfig" in str(exc_info.value)


def test_transform_enrich_requires_filesystem() -> None:
    config = PipelineConfig(
        ch_api_key="",
        ch_source_type="file",
        ch_clean_path="data/cache/snapshots/companies_house/2026-02-01/clean.csv",
        ch_token_index_dir="data/cache/snapshots/companies_house/2026-02-01",
    )

    with pytest.raises(DependencyMissingError) as exc_info:
        run_transform_enrich(
            register_path=Path("data/interim/sponsor_register_filtered.csv"),
            config=config,
            fs=None,
        )

    assert "FileSystem" in str(exc_info.value)


def test_transform_enrich_requires_http_client_for_api(
    in_memory_fs: InMemoryFileSystem,
) -> None:
    register_path = Path("data/interim/sponsor_register_filtered.csv")
    in_memory_fs.write_csv(
        pd.DataFrame(
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
        ),
        register_path,
    )

    config = PipelineConfig(
        ch_api_key="test-key",
        ch_sleep_seconds=0,
        ch_max_rpm=600,
        ch_min_match_score=0.0,
        ch_search_limit=1,
    )

    with pytest.raises(DependencyMissingError) as exc_info:
        run_transform_enrich(
            register_path=register_path,
            out_dir=Path("data/processed"),
            cache_dir=Path("data/cache"),
            config=config,
            http_client=None,
            resume=False,
            fs=in_memory_fs,
        )

    assert "HttpClient" in str(exc_info.value)


def test_transform_enrich_profile_fetch_errors_fail_fast(
    in_memory_fs: InMemoryFileSystem,
    fake_http_client: FakeHttpClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_path = Path("data/interim/sponsor_register_filtered.csv")
    out_dir = Path("data/processed")
    cache_dir = Path("data/cache")

    in_memory_fs.write_csv(
        pd.DataFrame(
            [
                {
                    "Organisation Name": "Acme Ltd",
                    "org_name_normalised": "acme ltd",
                    "has_multiple_towns": "False",
                    "has_multiple_counties": "False",
                    "Town/City": "London",
                    "County": "Greater London",
                    "Type & Rating": "A rating",
                    "Route": "Skilled Worker",
                    "raw_name_variants": "Acme Ltd",
                }
            ]
        ),
        register_path,
    )

    config = PipelineConfig(
        ch_api_key="test-key",
        ch_sleep_seconds=0,
        ch_max_rpm=600,
        ch_min_match_score=0.0,
        ch_search_limit=1,
    )

    fake_http_client.responses = {
        "search/companies": {
            "items": [
                {
                    "title": "Acme Ltd",
                    "company_number": "12345678",
                    "company_status": "active",
                    "address": {"locality": "London", "region": "Greater London"},
                }
            ]
        }
    }

    def fake_score_candidates(
        *,
        org_norm: str,
        town_norm: str,
        county_norm: str,
        items: list[SearchItem],
        query_used: str,
        similarity_fn: SimilarityFn,
        normalise_fn: NormaliseFn,
    ) -> list[CandidateMatch]:
        score = MatchScore(0.9, 0.8, 0.05, 0.03, 0.02)
        return [
            CandidateMatch(
                company_number="12345678",
                title="Acme Ltd",
                status="active",
                locality="London",
                region="Greater London",
                postcode="EC1A 1BB",
                score=score,
                query_used=query_used,
            )
        ]

    monkeypatch.setattr(s2, "score_candidates", fake_score_candidates)

    with pytest.raises(CompaniesHouseProfileError, match="profile fetch failed"):
        run_transform_enrich(
            register_path=register_path,
            out_dir=out_dir,
            cache_dir=cache_dir,
            config=config,
            http_client=fake_http_client,
            resume=True,
            fs=in_memory_fs,
        )

    assert in_memory_fs.exists(out_dir / "sponsor_enrich_resume_report.json")
    assert not in_memory_fs.exists(out_dir / "sponsor_unmatched.csv")


def test_resume_false_writes_to_new_output_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transform_register_csv = tmp_path / "sponsor_register_filtered.csv"
    transform_register_csv.write_text(
        "Organisation Name,org_name_normalised,has_multiple_towns,has_multiple_counties,"
        "Town/City,County,Type & Rating,Route,raw_name_variants\n"
        "Acme Ltd,acme,False,False,London,Greater London,A rating,Skilled Worker,Acme Ltd\n"
    )

    config = PipelineConfig(
        ch_api_key="test-key",
        ch_sleep_seconds=0,
        ch_max_rpm=600,
        ch_min_match_score=1.0,
        ch_search_limit=1,
    )

    class FixedDatetime:
        @staticmethod
        def now(tz: tzinfo | None = None) -> datetime:
            return datetime(2026, 2, 1, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(s2, "datetime", FixedDatetime)

    class DummyHttp:
        def get_json(self, url: str, cache_key: str | None = None) -> dict[str, object]:
            return {"items": []}

    out_dir = tmp_path / "out"
    outs = run_transform_enrich(
        register_path=transform_register_csv,
        out_dir=out_dir,
        cache_dir=tmp_path / "cache",
        config=config,
        http_client=DummyHttp(),
        resume=False,
        fs=LocalFileSystem(),
    )

    assert outs["enriched"].parent != out_dir
    assert outs["enriched"].parent.name == "run_20260201_120000"


def test_transform_enrich_file_source_uses_local_payload(in_memory_fs: InMemoryFileSystem) -> None:
    register_path = Path("data/interim/sponsor_register_filtered.csv")
    in_memory_fs.write_csv(
        pd.DataFrame(
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
        ),
        register_path,
    )

    snapshot_dir = Path("data/cache/snapshots/companies_house/2026-02-01")
    clean_path = snapshot_dir / "clean.csv"
    in_memory_fs.write_text(",".join(CANONICAL_HEADERS_V1) + "\n", clean_path)

    index_path = snapshot_dir / "index_tokens_a.csv"
    in_memory_fs.write_text("token,company_number\nacme,12345678\n", index_path)

    profiles_path = snapshot_dir / "profiles_0-9.csv"
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CANONICAL_HEADERS_V1)
    writer.writeheader()
    writer.writerow(
        {
            "company_number": "12345678",
            "company_name": "ACME LTD",
            "company_status": "active",
            "company_type": "ltd",
            "date_of_creation": "2015-01-01",
            "sic_codes": "62020",
            "address_locality": "London",
            "address_region": "Greater London",
            "address_postcode": "EC1A 1BB",
            "uri": "http://data.companieshouse.gov.uk/doc/company/12345678",
        }
    )
    in_memory_fs.write_text(buffer.getvalue(), profiles_path)

    config = PipelineConfig(
        ch_api_key="",
        ch_sleep_seconds=0,
        ch_max_rpm=600,
        ch_min_match_score=0.0,
        ch_search_limit=5,
        ch_source_type="file",
        ch_clean_path=str(clean_path),
        ch_token_index_dir=str(snapshot_dir),
    )

    outs = run_transform_enrich(
        register_path=register_path,
        out_dir=Path("data/processed"),
        config=config,
        fs=in_memory_fs,
        resume=False,
    )

    enriched_df = in_memory_fs.read_csv(outs["enriched"]).fillna("")
    assert enriched_df["Organisation Name"].tolist() == ["Acme Ltd"]
    assert enriched_df.loc[0, "ch_company_number"] == "12345678"


def test_transform_enrich_memoises_search_queries_within_run(
    in_memory_fs: InMemoryFileSystem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_path = Path("data/interim/sponsor_register_filtered.csv")
    out_dir = Path("data/processed")
    in_memory_fs.write_csv(
        pd.DataFrame(
            [
                {
                    "Organisation Name": "Alpha Ltd",
                    "org_name_normalised": "alpha",
                    "has_multiple_towns": "False",
                    "has_multiple_counties": "False",
                    "Town/City": "London",
                    "County": "Greater London",
                    "Type & Rating": "A rating",
                    "Route": "Skilled Worker",
                    "raw_name_variants": "Alpha Ltd",
                },
                {
                    "Organisation Name": "Beta Ltd",
                    "org_name_normalised": "beta",
                    "has_multiple_towns": "False",
                    "has_multiple_counties": "False",
                    "Town/City": "London",
                    "County": "Greater London",
                    "Type & Rating": "A rating",
                    "Route": "Skilled Worker",
                    "raw_name_variants": "Beta Ltd",
                },
            ]
        ),
        register_path,
    )

    class CountingSource:
        def __init__(self) -> None:
            self.search_calls: dict[str, int] = {}

        def search(self, query: str) -> list[SearchItem]:
            self.search_calls[query] = self.search_calls.get(query, 0) + 1
            return []

        def profile(self, company_number: str) -> CompanyProfile:
            _ = company_number
            raise AssertionError

    source = CountingSource()

    def fake_build_companies_house_source(
        *,
        config: PipelineConfig,
        fs: FileSystem,
        http_client: HttpClient | None,
        token_set: set[str] | None = None,
    ) -> s2.CompaniesHouseSource:
        _ = (config, fs, http_client, token_set)
        return source

    def fake_variants(org: str) -> list[str]:
        _ = org
        return ["shared-query"]

    monkeypatch.setattr(s2, "build_companies_house_source", fake_build_companies_house_source)
    monkeypatch.setattr(s2, "generate_query_variants", fake_variants)

    config = PipelineConfig(
        ch_source_type="file",
        ch_batch_size=2,
        ch_min_match_score=0.99,
    )

    run_transform_enrich(
        register_path=register_path,
        out_dir=out_dir,
        config=config,
        resume=False,
        fs=in_memory_fs,
    )

    assert source.search_calls == {"shared-query": 1}


def test_transform_enrich_invalid_source_type_raises(in_memory_fs: InMemoryFileSystem) -> None:
    register_path = Path("data/interim/sponsor_register_filtered.csv")
    in_memory_fs.write_csv(
        pd.DataFrame(
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
        ),
        register_path,
    )

    config = PipelineConfig(
        ch_api_key="",
        ch_source_type="invalid",
    )

    with pytest.raises(InvalidSourceTypeError):
        run_transform_enrich(register_path=register_path, config=config, fs=in_memory_fs)
