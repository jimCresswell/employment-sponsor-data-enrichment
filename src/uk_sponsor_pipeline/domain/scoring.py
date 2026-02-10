"""Domain scoring rules for role-likelihood classification.

Usage example:
    from uk_sponsor_pipeline.domain.scoring import calculate_features
    from uk_sponsor_pipeline.types import TransformEnrichRow

    row: TransformEnrichRow = {
        "Organisation Name": "Acme Ltd",
        "org_name_normalised": "acme",
        "has_multiple_towns": "False",
        "has_multiple_counties": "False",
        "Town/City": "London",
        "County": "Greater London",
        "Type & Rating": "A rating",
        "Route": "Skilled Worker",
        "raw_name_variants": "Acme Ltd",
        "match_status": "matched",
        "match_score": 2.0,
        "match_confidence": "medium",
        "match_query_used": "Acme Ltd",
        "score_name_similarity": 0.8,
        "score_locality_bonus": 0.1,
        "score_region_bonus": 0.05,
        "score_status_bonus": 0.1,
        "ch_company_number": "12345678",
        "ch_company_name": "ACME LTD",
        "ch_company_status": "active",
        "ch_company_type": "ltd",
        "ch_date_of_creation": "2015-01-01",
        "ch_sic_codes": "62020",
        "ch_address_locality": "London",
        "ch_address_region": "Greater London",
        "ch_address_postcode": "EC1A 1BB",
    }

    features = calculate_features(row)
    assert features.bucket in {"strong", "possible", "unlikely"}
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

from ..types import TransformEnrichRow
from .scoring_profiles import ScoringProfile

# SIC code mappings for tech signals (prefix → score)
TECH_SIC_PREFIXES = {
    "620": 0.50,  # Computer programming, consultancy, IT services
    "631": 0.40,  # Data processing, hosting
    "582": 0.35,  # Software publishing
    "611": 0.25,  # Wired telecommunications
    "612": 0.25,  # Wireless telecommunications
    "619": 0.20,  # Other telecommunications
    "721": 0.20,  # R&D in natural sciences
    "722": 0.15,  # R&D in social sciences
    "711": 0.15,  # Architectural and engineering activities
}

# Negative SIC signals (sectors unlikely to hire senior engineers)
NEGATIVE_SIC_PREFIXES = {
    "861": -0.25,  # Hospital activities
    "862": -0.20,  # Medical practice
    "869": -0.15,  # Other human health
    "871": -0.25,  # Residential nursing care
    "872": -0.25,  # Residential care for disabilities
    "873": -0.25,  # Residential care for elderly
    "879": -0.25,  # Other residential care
    "412": -0.15,  # Construction of buildings
    "411": -0.10,  # Development of building projects
    "432": -0.10,  # Electrical installation
    "439": -0.10,  # Other construction
    "561": -0.20,  # Restaurants
    "562": -0.20,  # Event catering
    "551": -0.15,  # Hotels
}

# Name keywords that suggest tech company
TECH_KEYWORDS = frozenset(
    {
        "software",
        "digital",
        "tech",
        "technology",
        "data",
        "ai",
        "cloud",
        "cyber",
        "app",
        "platform",
        "saas",
        "fintech",
        "healthtech",
        "edtech",
        "devops",
        "analytics",
        "machine",
        "learning",
        "automation",
    }
)

# Name keywords that suggest non-tech
NEGATIVE_KEYWORDS = frozenset(
    {
        "care",
        "nursing",
        "recruitment",
        "staffing",
        "construction",
        "cleaning",
        "security",
        "catering",
        "restaurant",
        "hotel",
    }
)

# Company types and their weights
COMPANY_TYPE_WEIGHTS = {
    "ltd": 0.08,
    "private-limited-company": 0.08,
    "public limited company": 0.05,
    "plc": 0.05,
    "llp": 0.06,
    "limited-partnership": 0.04,
    "community-interest-company": 0.02,
    "charitable-incorporated-organisation": 0.01,
}

DEFAULT_ACTIVE_SCORE = 0.10
DEFAULT_INACTIVE_SCORE = 0.0
DEFAULT_UNKNOWN_AGE_SCORE = 0.05
DEFAULT_UNKNOWN_COMPANY_TYPE_SCORE = 0.03
DEFAULT_SIC_BASELINE = 0.10
DEFAULT_SIC_SCORE_MIN = 0.0
DEFAULT_SIC_SCORE_MAX = 0.5
DEFAULT_STRONG_THRESHOLD = 0.55
DEFAULT_POSSIBLE_THRESHOLD = 0.35


@dataclass
class ScoringFeatures:
    """Feature breakdown for tech-likelihood scoring."""

    sic_tech_score: float  # 0.0–0.5 from SIC codes
    is_active_score: float  # 0.0 or 0.10
    company_age_score: float  # 0.0–0.15 based on years since creation
    company_type_score: float  # 0.0–0.10 based on company type
    name_keyword_score: float  # -0.10 to 0.15 based on name keywords
    strong_threshold: float = DEFAULT_STRONG_THRESHOLD
    possible_threshold: float = DEFAULT_POSSIBLE_THRESHOLD

    @property
    def total(self) -> float:
        """Calculate total score, clamped to 0.0–1.0."""
        raw = (
            self.sic_tech_score
            + self.is_active_score
            + self.company_age_score
            + self.company_type_score
            + self.name_keyword_score
        )
        return max(0.0, min(1.0, raw))

    @property
    def bucket(self) -> str:
        """Classify into role-fit bucket."""
        if self.total >= self.strong_threshold:
            return "strong"
        if self.total >= self.possible_threshold:
            return "possible"
        return "unlikely"


def parse_sic_list(s: str) -> list[str]:
    """Parse semicolon/comma-separated SIC codes."""
    if not s.strip():
        return []
    parts = [p.strip() for p in s.replace(",", ";").split(";")]
    return [p for p in parts if p]


def score_from_sic(sics: list[str], profile: ScoringProfile | None = None) -> float:
    """Calculate SIC-based tech score."""
    if not sics:
        return DEFAULT_SIC_BASELINE  # Unknown: small baseline

    positive_prefixes = profile.sic_positive_prefixes if profile is not None else TECH_SIC_PREFIXES
    negative_prefixes = (
        profile.sic_negative_prefixes if profile is not None else NEGATIVE_SIC_PREFIXES
    )

    score = DEFAULT_SIC_BASELINE
    for sic in sics:
        # Tech positive signals (take max)
        for pref, val in positive_prefixes.items():
            if sic.startswith(pref):
                score = max(score, val)
        # Negative signals (additive penalty)
        for pref, val in negative_prefixes.items():
            if sic.startswith(pref):
                score += val

    return max(DEFAULT_SIC_SCORE_MIN, min(DEFAULT_SIC_SCORE_MAX, score))


def score_company_age(date_of_creation: str, profile: ScoringProfile | None = None) -> float:
    """Score based on company age (established companies score higher)."""
    default_unknown_score = (
        profile.company_age_scores.unknown if profile is not None else DEFAULT_UNKNOWN_AGE_SCORE
    )
    if not date_of_creation:
        return default_unknown_score

    try:
        created = date.fromisoformat(date_of_creation)
        today = datetime.now(UTC).date()
        years = (today - created).days / 365.25

        if profile is not None:
            for band in profile.company_age_scores.bands:
                if years >= band.min_years:
                    return band.score
            return default_unknown_score

        if years >= 10:
            return 0.12
        if years >= 5:
            return 0.10
        if years >= 2:
            return 0.07
        if years >= 1:
            return 0.04
        else:
            return 0.02  # Very new
    except (TypeError, ValueError):
        return default_unknown_score


def score_company_type(company_type: str, profile: ScoringProfile | None = None) -> float:
    """Score based on company type."""
    ct = (company_type or "").lower().strip()
    if profile is not None:
        return profile.company_type_weights.get(ct, DEFAULT_UNKNOWN_COMPANY_TYPE_SCORE)
    return COMPANY_TYPE_WEIGHTS.get(ct, 0.03)


def score_name_keywords(name: str, profile: ScoringProfile | None = None) -> float:
    """Score based on keywords in company name."""
    if not name:
        return 0.0

    name_lower = name.lower()
    words = set(re.findall(r"\w+", name_lower))

    score = 0.0
    if profile is not None:
        keyword_weights = profile.keyword_weights
        positive_keywords = frozenset(profile.keyword_positive)
        negative_keywords = frozenset(profile.keyword_negative)
        positive_matches = words & positive_keywords
        if positive_matches:
            score += min(
                keyword_weights.positive_cap,
                len(positive_matches) * keyword_weights.positive_per_match,
            )
        negative_matches = words & negative_keywords
        if negative_matches:
            score -= min(
                keyword_weights.negative_cap,
                len(negative_matches) * keyword_weights.negative_per_match,
            )
        return score

    # Positive keywords
    tech_matches = words & TECH_KEYWORDS
    if tech_matches:
        score += min(0.15, len(tech_matches) * 0.05)

    # Negative keywords
    negative_matches = words & NEGATIVE_KEYWORDS
    if negative_matches:
        score -= min(0.10, len(negative_matches) * 0.05)

    return score


def calculate_features(
    row: TransformEnrichRow,
    profile: ScoringProfile | None = None,
) -> ScoringFeatures:
    """Calculate all scoring features for a company row."""
    sics = parse_sic_list(row["ch_sic_codes"])
    status = row["ch_company_status"].lower()
    date_of_creation = row["ch_date_of_creation"]
    company_type = row["ch_company_type"]
    company_name = row["ch_company_name"] or row["Organisation Name"]
    status_score = (
        profile.company_status_scores.active
        if profile is not None and status == "active"
        else profile.company_status_scores.inactive
        if profile is not None
        else DEFAULT_ACTIVE_SCORE
        if status == "active"
        else DEFAULT_INACTIVE_SCORE
    )

    return ScoringFeatures(
        sic_tech_score=score_from_sic(sics, profile=profile),
        is_active_score=status_score,
        company_age_score=score_company_age(date_of_creation, profile=profile),
        company_type_score=score_company_type(company_type, profile=profile),
        name_keyword_score=score_name_keywords(company_name, profile=profile),
        strong_threshold=profile.bucket_thresholds.strong
        if profile is not None
        else DEFAULT_STRONG_THRESHOLD,
        possible_threshold=profile.bucket_thresholds.possible
        if profile is not None
        else DEFAULT_POSSIBLE_THRESHOLD,
    )
