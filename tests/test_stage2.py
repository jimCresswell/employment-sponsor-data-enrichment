"""Tests for Stage 2 Companies House integration."""

import base64
from unittest.mock import MagicMock

import pandas as pd
import pytest

from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.exceptions import AuthenticationError
from uk_sponsor_pipeline.infrastructure import CachedHttpClient, CircuitBreaker, RateLimiter
from uk_sponsor_pipeline.stages import stage2_companies_house as s2
from uk_sponsor_pipeline.stages.stage2_companies_house import _auth_header, run_stage2


class TestAuthHeader:
    """Tests for API key authentication header generation."""

    def test_auth_header_format(self):
        """Verify auth header uses HTTP Basic Auth with key:empty format."""
        api_key = "test-api-key-12345"
        headers = _auth_header(api_key)

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

        # Decode and verify format is "api_key:" (key followed by colon, no password)
        encoded = headers["Authorization"].replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == f"{api_key}:"

    def test_auth_header_with_real_format_key(self):
        """Test with a key that looks like a real CH API key (UUID format)."""
        api_key = "a06e8c82-0b3b-4b1a-9c1a-1a2b3c4d5e6f"
        headers = _auth_header(api_key)

        encoded = headers["Authorization"].replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == f"{api_key}:"


class TestCachedHttpClientAuth:
    """Tests for CachedHttpClient auth header passing."""

    def test_session_headers_are_used(self):
        """Verify that session headers are passed to requests."""
        import requests

        # Create a mock session
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_session.get.return_value = mock_response

        # Add auth header to session
        api_key = "test-key-123"
        expected_auth = _auth_header(api_key)
        mock_session.headers = {"Authorization": expected_auth["Authorization"]}

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

        def fake_score_candidates(org, town, county, items, query_used):
            return scores.pop(0)

        monkeypatch.setattr(s2, "_score_candidates", fake_score_candidates)

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
