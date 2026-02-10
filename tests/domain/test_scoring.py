"""Tests for domain scoring logic."""

from types import MappingProxyType

from tests.support.transform_enrich_rows import make_enrich_row
from uk_sponsor_pipeline.domain.scoring import (
    ScoringFeatures,
    calculate_features,
    parse_sic_list,
    score_company_age,
    score_company_type,
    score_from_sic,
    score_name_keywords,
)
from uk_sponsor_pipeline.domain.scoring_profiles import (
    BucketThresholds,
    CompanyAgeBand,
    CompanyAgeScores,
    CompanyStatusScores,
    KeywordWeights,
    ScoringProfile,
)


def _make_profile(
    *,
    sic_positive_prefixes: dict[str, float] | None = None,
    sic_negative_prefixes: dict[str, float] | None = None,
    keyword_positive: tuple[str, ...] = (),
    keyword_negative: tuple[str, ...] = (),
    keyword_weights: KeywordWeights | None = None,
    company_status_scores: CompanyStatusScores | None = None,
    company_age_scores: CompanyAgeScores | None = None,
    company_type_weights: dict[str, float] | None = None,
    bucket_thresholds: BucketThresholds | None = None,
) -> ScoringProfile:
    return ScoringProfile(
        name="custom",
        job_type="custom_job_type",
        sector_signals=MappingProxyType({}),
        location_signals=MappingProxyType({}),
        size_signals=MappingProxyType({}),
        sic_positive_prefixes=MappingProxyType(dict(sic_positive_prefixes or {})),
        sic_negative_prefixes=MappingProxyType(dict(sic_negative_prefixes or {})),
        keyword_positive=keyword_positive,
        keyword_negative=keyword_negative,
        keyword_weights=keyword_weights
        or KeywordWeights(
            positive_per_match=0.05,
            positive_cap=0.15,
            negative_per_match=0.05,
            negative_cap=0.1,
        ),
        company_status_scores=company_status_scores
        or CompanyStatusScores(
            active=0.1,
            inactive=0.0,
        ),
        company_age_scores=company_age_scores
        or CompanyAgeScores(
            unknown=0.05,
            bands=(
                CompanyAgeBand(min_years=10.0, score=0.12),
                CompanyAgeBand(min_years=5.0, score=0.1),
                CompanyAgeBand(min_years=2.0, score=0.07),
                CompanyAgeBand(min_years=1.0, score=0.04),
                CompanyAgeBand(min_years=0.0, score=0.02),
            ),
        ),
        company_type_weights=MappingProxyType(dict(company_type_weights or {})),
        bucket_thresholds=bucket_thresholds or BucketThresholds(strong=0.55, possible=0.35),
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
        row = make_enrich_row(
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
        row = make_enrich_row(
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

    def test_profile_drives_sic_status_age_and_type_features(self) -> None:
        profile = _make_profile(
            sic_negative_prefixes={"620": -0.3},
            company_status_scores=CompanyStatusScores(active=0.2, inactive=-0.25),
            company_age_scores=CompanyAgeScores(
                unknown=-0.2,
                bands=(
                    CompanyAgeBand(min_years=2.0, score=0.35),
                    CompanyAgeBand(min_years=0.0, score=0.05),
                ),
            ),
            company_type_weights={"charity": 0.45},
        )
        row = make_enrich_row(
            **{
                "ch_sic_codes": "62020",
                "ch_company_status": "inactive",
                "ch_date_of_creation": "2020-01-01",
                "ch_company_type": "charity",
                "ch_company_name": "Neutral Name",
            }
        )

        features = calculate_features(row, profile=profile)

        assert features.sic_tech_score == 0.0
        assert features.is_active_score == -0.25
        assert features.company_age_score == 0.35
        assert features.company_type_score == 0.45

    def test_profile_drives_keyword_weighting(self) -> None:
        profile = _make_profile(
            keyword_positive=("banana",),
            keyword_negative=("software",),
            keyword_weights=KeywordWeights(
                positive_per_match=0.4,
                positive_cap=0.4,
                negative_per_match=0.2,
                negative_cap=0.2,
            ),
        )
        row = make_enrich_row(
            **{
                "ch_company_name": "Software Banana Ltd",
            }
        )

        features = calculate_features(row, profile=profile)

        assert features.name_keyword_score == 0.2

    def test_profile_drives_bucket_thresholds(self) -> None:
        profile = _make_profile(
            sic_positive_prefixes={"999": 0.1},
            company_status_scores=CompanyStatusScores(active=0.2, inactive=0.0),
            company_age_scores=CompanyAgeScores(
                unknown=0.0,
                bands=(CompanyAgeBand(min_years=0.0, score=0.2),),
            ),
            company_type_weights={"ltd": 0.2},
            bucket_thresholds=BucketThresholds(strong=0.8, possible=0.6),
        )
        row = make_enrich_row(
            **{
                "ch_sic_codes": "99999",
                "ch_company_status": "active",
                "ch_date_of_creation": "2025-01-01",
                "ch_company_type": "ltd",
                "ch_company_name": "Neutral Name",
            }
        )

        features = calculate_features(row, profile=profile)

        assert features.total == 0.7
        assert features.bucket == "possible"


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
