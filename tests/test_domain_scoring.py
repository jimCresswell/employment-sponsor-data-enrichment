"""Tests for domain scoring logic."""

from tests.support.stage2_rows import make_stage2_row
from uk_sponsor_pipeline.domain.scoring import (
    ScoringFeatures,
    calculate_features,
    parse_sic_list,
    score_company_age,
    score_company_type,
    score_from_sic,
    score_name_keywords,
)


class TestParseSicList:
    """Tests for SIC code parsing."""

    def test_semicolon_separated(self) -> None:
        assert parse_sic_list("62020;63110") == ["62020", "63110"]

    def test_comma_separated(self) -> None:
        assert parse_sic_list("62020,63110") == ["62020", "63110"]

    def test_empty_string(self) -> None:
        assert parse_sic_list("") == []

    def test_whitespace(self) -> None:
        assert parse_sic_list(" 62020 ; 63110 ") == ["62020", "63110"]


class TestScoreFromSic:
    """Tests for SIC-based scoring."""

    def test_tech_sic_high_score(self) -> None:
        # 62020 = Computer consultancy, maps to 0.50 (max)
        assert score_from_sic(["62020"]) == 0.50

    def test_negative_sic_low_score(self) -> None:
        # 87100 = Residential nursing care, has negative modifier
        score = score_from_sic(["87100"])
        assert score < 0.10  # Below baseline due to penalty

    def test_mixed_sics(self) -> None:
        # Mix of tech and other codes
        score = score_from_sic(["62020", "41200"])
        assert score >= 0.35  # Tech SIC should dominate

    def test_unknown_sic(self) -> None:
        # Non-tech SIC gets baseline
        assert score_from_sic(["99999"]) == 0.10


class TestScoreCompanyAge:
    """Tests for company age scoring."""

    def test_established_company(self) -> None:
        # 10+ year old company
        assert score_company_age("2010-01-01") >= 0.10

    def test_new_company(self) -> None:
        # Very new company
        assert score_company_age("2025-01-01") <= 0.05

    def test_empty_date(self) -> None:
        assert score_company_age("") == 0.05


class TestScoreCompanyType:
    """Tests for company type scoring."""

    def test_ltd(self) -> None:
        assert score_company_type("ltd") == 0.08

    def test_unknown_type(self) -> None:
        assert score_company_type("unknown-type") == 0.03


class TestScoreNameKeywords:
    """Tests for name keyword scoring."""

    def test_tech_keywords(self) -> None:
        score = score_name_keywords("Acme Software Solutions Ltd")
        assert score > 0

    def test_negative_keywords(self) -> None:
        score = score_name_keywords("Care Home Staffing Services")
        assert score < 0

    def test_neutral_name(self) -> None:
        assert score_name_keywords("ABC Company") == 0


class TestCalculateFeatures:
    """Tests for full feature calculation."""

    def test_tech_company(self) -> None:
        row = make_stage2_row(
            **{
                "ch_sic_codes": "62020",
                "ch_company_status": "active",
                "ch_date_of_creation": "2015-01-01",
                "ch_company_type": "ltd",
                "ch_company_name": "Tech Software Solutions Ltd",
            }
        )
        features = calculate_features(row)
        assert features.sic_tech_score == 0.50
        assert features.is_active_score == 0.10
        assert features.bucket == "strong"

    def test_non_tech_company(self) -> None:
        row = make_stage2_row(
            **{
                "ch_sic_codes": "87100",  # Care home
                "ch_company_status": "active",
                "ch_date_of_creation": "2020-01-01",
                "ch_company_type": "ltd",
                "ch_company_name": "Care Home Services Ltd",
            }
        )
        features = calculate_features(row)
        assert features.bucket == "unlikely"


class TestScoringFeatures:
    """Tests for ScoringFeatures dataclass."""

    def test_total_calculation(self) -> None:
        features = ScoringFeatures(
            sic_tech_score=0.50,
            is_active_score=0.10,
            company_age_score=0.10,
            company_type_score=0.05,
            name_keyword_score=0.10,
        )
        assert features.total == 0.85

    def test_total_clamped(self) -> None:
        features = ScoringFeatures(
            sic_tech_score=0.50,
            is_active_score=0.10,
            company_age_score=0.15,
            company_type_score=0.10,
            name_keyword_score=0.20,
        )
        assert features.total == 1.0  # Clamped to max

    def test_bucket_strong(self) -> None:
        features = ScoringFeatures(0.50, 0.10, 0.10, 0.05, 0.0)
        assert features.bucket == "strong"

    def test_bucket_possible(self) -> None:
        features = ScoringFeatures(0.20, 0.10, 0.05, 0.05, 0.0)
        assert features.bucket == "possible"

    def test_bucket_unlikely(self) -> None:
        features = ScoringFeatures(0.0, 0.10, 0.05, 0.05, -0.05)
        assert features.bucket == "unlikely"
