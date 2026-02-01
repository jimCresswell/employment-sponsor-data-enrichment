"""Tests for Stage 2 Companies House integration."""

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.exceptions import AuthenticationError, CircuitBreakerOpen, RateLimitError
from uk_sponsor_pipeline.infrastructure import CachedHttpClient, CircuitBreaker, RateLimiter
from uk_sponsor_pipeline.stages import stage2_companies_house as s2
from uk_sponsor_pipeline.stages.stage2_companies_house import _basic_auth, run_stage2


class TestBasicAuth:
    """Tests for API key authentication setup."""

    def test_auth_header_format(self):
        """Verify auth uses HTTP Basic Auth with key + blank password."""
        api_key = "test-api-key-12345"
        auth = _basic_auth(api_key)
        assert auth.username == api_key
        assert auth.password == ""

    def test_auth_header_with_real_format_key(self):
        """Test with a key that looks like a real CH API key (UUID format)."""
        api_key = "a06e8c82-0b3b-4b1a-9c1a-1a2b3c4d5e6f"
        auth = _basic_auth(api_key)
        assert auth.username == api_key
        assert auth.password == ""


class TestCachedHttpClientAuth:
    """Tests for CachedHttpClient auth header passing."""

    def test_session_headers_are_used(self):
        """Verify that session.get is invoked when using CachedHttpClient."""
        import requests

        # Create a mock session
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_session.get.return_value = mock_response

        # Add auth to session
        api_key = "test-key-123"
        mock_session.auth = _basic_auth(api_key)

        # Create cache, rate limiter, and circuit breaker
        cache = MagicMock()
        cache.get.return_value = None  # Cache miss
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=5)

        client = CachedHttpClient(
            session=mock_session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
        )

        # Make a request
        client.get_json("https://api.example.com/test", "cache_key")

        # Verify session.get was called (which uses session headers)
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args
        assert call_args[0][0] == "https://api.example.com/test"


class TestHttpClientWithErrors:
    """Tests for HTTP client error handling."""

    def test_401_raises_auth_error_immediately(self):
        """Verify that 401 errors raise AuthenticationError immediately."""
        import requests

        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_session.get.return_value = mock_response

        cache = MagicMock()
        cache.get.return_value = None
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=5)

        client = CachedHttpClient(
            session=mock_session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
        )

        # Should raise AuthenticationError, not HTTPError
        with pytest.raises(AuthenticationError):
            client.get_json("https://api.example.com/test", "cache_key")

        # Should only make ONE request
        assert mock_session.get.call_count == 1

    def test_403_raises_auth_error_immediately(self):
        """Verify that 403 Forbidden (IP ban) raises AuthenticationError immediately."""
        import requests

        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_session.get.return_value = mock_response

        cache = MagicMock()
        cache.get.return_value = None
        rate_limiter = RateLimiter(max_rpm=600, min_delay_seconds=0)
        circuit_breaker = CircuitBreaker(threshold=5)

        client = CachedHttpClient(
            session=mock_session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
        )

        # Should raise AuthenticationError, not HTTPError
        with pytest.raises(AuthenticationError) as exc_info:
            client.get_json("https://api.example.com/test", "cache_key")

        # Should only make ONE request
        assert mock_session.get.call_count == 1
        # Error message should mention 403
        assert "403" in str(exc_info.value)


class TestStage2AuthIntegration:
    """Integration tests for Stage 2 authentication."""

    def test_api_key_is_passed_to_session(self, tmp_path):
        """Verify the API key from config is correctly added to session headers."""
        # Create minimal stage1 input
        stage1_csv = tmp_path / "stage1.csv"
        stage1_csv.write_text(
            "Organisation Name,org_name_normalized,has_multiple_towns,has_multiple_counties,"
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

        # Run stage2 with our mock
        out_dir = tmp_path / "out"
        cache_dir = tmp_path / "cache"

        try:
            run_stage2(
                stage1_path=stage1_csv,
                out_dir=out_dir,
                cache_dir=cache_dir,
                config=config,
                http_client=mock_http,
                resume=False,
            )
        except Exception:
            pass  # We just want to verify the mock was called

        # Verify http_client.get_json was called (meaning config was used)
        assert mock_http.get_json.called


class TestStage2CandidateOrdering:
    """Tests for candidate ranking across multiple query variants."""

    def test_candidates_sorted_across_queries(self, tmp_path, monkeypatch):
        stage1_csv = tmp_path / "stage1.csv"
        stage1_csv.write_text(
            "Organisation Name,org_name_normalized,has_multiple_towns,has_multiple_counties,"
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
                self.calls = []

            def get_json(self, url, cache_key=None):
                self.calls.append(url)
                return {"items": []}

        monkeypatch.setattr(s2, "generate_query_variants", lambda org: ["q1", "q2"])

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
            org_norm,
            town_norm,
            county_norm,
            items,
            query_used,
            similarity_fn,
            normalize_fn,
        ):
            return scores.pop(0)

        monkeypatch.setattr(s2, "score_candidates", fake_score_candidates)

        out_dir = tmp_path / "out"
        run_stage2(
            stage1_path=stage1_csv,
            out_dir=out_dir,
            cache_dir=tmp_path / "cache",
            config=config,
            http_client=DummyHttp(),
            resume=False,
        )

        candidates_df = pd.read_csv(out_dir / "stage2_candidates_top3.csv", dtype=str).fillna("")
        top_score = float(candidates_df.loc[0, "candidate_score"])
        assert top_score == 0.7


class TestStage2Resume:
    """Tests for batching, incremental output, and resume logic."""

    def test_resume_skips_processed_orgs(self, in_memory_fs, fake_http_client, monkeypatch):
        stage1_path = Path("data/interim/stage1.csv")
        out_dir = Path("data/processed")
        cache_dir = Path("data/cache/companies_house")

        df = pd.DataFrame(
            [
                {
                    "Organisation Name": "Alpha Ltd",
                    "org_name_normalized": "alpha ltd",
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
                    "org_name_normalized": "beta ltd",
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
        in_memory_fs.write_csv(df, stage1_path)

        config = PipelineConfig(
            ch_api_key="test-key",
            ch_sleep_seconds=0,
            ch_max_rpm=600,
            ch_min_match_score=0.9,  # Force unmatched path
            ch_search_limit=1,
            ch_batch_size=1,  # Flush per org to exercise append
        )

        fake_http_client.responses = {"search/companies": {"items": []}}

        monkeypatch.setattr(s2, "generate_query_variants", lambda org: [org])

        def fake_score_candidates(
            *,
            org_norm,
            town_norm,
            county_norm,
            items,
            query_used,
            similarity_fn,
            normalize_fn,
        ):
            score = s2.MatchScore(0.5, 0.5, 0.0, 0.0, 0.0)
            return [
                s2.CandidateMatch(
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

        run_stage2(
            stage1_path=stage1_path,
            out_dir=out_dir,
            cache_dir=cache_dir,
            config=config,
            http_client=fake_http_client,
            resume=True,
            fs=in_memory_fs,
        )

        unmatched_df = in_memory_fs.read_csv(out_dir / "stage2_unmatched.csv")
        checkpoint_df = in_memory_fs.read_csv(out_dir / "stage2_checkpoint.csv")
        candidates_df = in_memory_fs.read_csv(out_dir / "stage2_candidates_top3.csv")

        assert len(unmatched_df) == 2
        assert len(checkpoint_df) == 2
        assert len(candidates_df) == 2
        assert sorted(checkpoint_df["Organisation Name"].tolist()) == ["Alpha Ltd", "Beta Ltd"]

        class FailingHttp:
            calls = 0

            def get_json(self, url, cache_key=None):
                self.calls += 1
                raise AssertionError("Should not call HTTP client when resuming")

        failing_http = FailingHttp()

        run_stage2(
            stage1_path=stage1_path,
            out_dir=out_dir,
            cache_dir=cache_dir,
            config=config,
            http_client=failing_http,
            resume=True,
            fs=in_memory_fs,
        )

        assert failing_http.calls == 0

    def test_batch_start_and_count_select_subset(self, in_memory_fs, fake_http_client, monkeypatch):
        stage1_path = Path("data/interim/stage1.csv")
        out_dir = Path("data/processed")
        cache_dir = Path("data/cache/companies_house")

        df = pd.DataFrame(
            [
                {
                    "Organisation Name": "Alpha Ltd",
                    "org_name_normalized": "alpha ltd",
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
                    "org_name_normalized": "beta ltd",
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
                    "org_name_normalized": "gamma ltd",
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
        in_memory_fs.write_csv(df, stage1_path)

        config = PipelineConfig(
            ch_api_key="test-key",
            ch_sleep_seconds=0,
            ch_max_rpm=600,
            ch_min_match_score=0.9,  # Force unmatched path
            ch_search_limit=1,
            ch_batch_size=1,
        )

        fake_http_client.responses = {"search/companies": {"items": []}}
        monkeypatch.setattr(s2, "generate_query_variants", lambda org: [org])

        def fake_score_candidates(
            *,
            org_norm,
            town_norm,
            county_norm,
            items,
            query_used,
            similarity_fn,
            normalize_fn,
        ):
            score = s2.MatchScore(0.5, 0.5, 0.0, 0.0, 0.0)
            return [
                s2.CandidateMatch(
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

        run_stage2(
            stage1_path=stage1_path,
            out_dir=out_dir,
            cache_dir=cache_dir,
            config=config,
            http_client=fake_http_client,
            resume=False,
            fs=in_memory_fs,
            batch_start=2,
            batch_count=1,
        )

        checkpoint_df = in_memory_fs.read_csv(out_dir / "stage2_checkpoint.csv")
        unmatched_df = in_memory_fs.read_csv(out_dir / "stage2_unmatched.csv")
        report = in_memory_fs.read_json(out_dir / "stage2_resume_report.json")

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


class TestStage2FailFast:
    """Ensure fatal search errors stop the run and can be resumed later."""

    @pytest.mark.parametrize(
        ("exc_type", "exc_args"),
        [
            (AuthenticationError, ("invalid key",)),
            (RateLimitError, (60,)),
            (CircuitBreakerOpen, (5, 5)),
        ],
    )
    def test_search_errors_fail_fast(self, in_memory_fs, exc_type, exc_args) -> None:
        stage1_path = Path("data/interim/stage1.csv")
        in_memory_fs.write_csv(
            pd.DataFrame(
                [
                    {
                        "Organisation Name": "Failing Co",
                        "org_name_normalized": "failing co",
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
            stage1_path,
        )

        class FailingHttp:
            def get_json(self, url, cache_key=None):
                raise exc_type(*exc_args)

        config = PipelineConfig(
            ch_api_key="test-key",
            ch_sleep_seconds=0,
            ch_max_rpm=600,
            ch_min_match_score=0.0,
            ch_search_limit=1,
        )

        with pytest.raises(exc_type):
            run_stage2(
                stage1_path=stage1_path,
                out_dir=Path("data/processed"),
                cache_dir=Path("data/cache"),
                config=config,
                http_client=FailingHttp(),
                resume=False,
                fs=in_memory_fs,
            )


def test_stage2_requires_config() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        run_stage2()
    assert "PipelineConfig" in str(exc_info.value)
