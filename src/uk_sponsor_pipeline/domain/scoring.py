"""Domain scoring rules for tech-likelihood classification.

Usage example:
    from uk_sponsor_pipeline.domain.scoring import calculate_features
    from uk_sponsor_pipeline.types import TransformEnrichRow

    row: TransformEnrichRow = {
        "Organisation Name": "Acme Ltd",
        "org_name_normalized": "acme",
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
from datetime import datetime

from ..types import TransformEnrichRow

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


@dataclass
class ScoringFeatures:
    """Feature breakdown for tech-likelihood scoring."""

    sic_tech_score: float  # 0.0–0.5 from SIC codes
    is_active_score: float  # 0.0 or 0.10
    company_age_score: float  # 0.0–0.15 based on years since creation
    company_type_score: float  # 0.0–0.10 based on company type
    name_keyword_score: float  # -0.10 to 0.15 based on name keywords

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
        if self.total >= 0.55:
            return "strong"
        elif self.total >= 0.35:
            return "possible"
        else:
            return "unlikely"


def parse_sic_list(s: str) -> list[str]:
    """Parse semicolon/comma-separated SIC codes."""
    if not s.strip():
        return []
    parts = [p.strip() for p in s.replace(",", ";").split(";")]
    return [p for p in parts if p]


def score_from_sic(sics: list[str]) -> float:
    """Calculate SIC-based tech score."""
    if not sics:
        return 0.10  # Unknown: small baseline

    score = 0.10  # Baseline
    for sic in sics:
        pref3 = sic[:3]
        # Tech positive signals (take max)
        for pref, val in TECH_SIC_PREFIXES.items():
            if pref3.startswith(pref):
                score = max(score, val)
        # Negative signals (additive penalty)
        for pref, val in NEGATIVE_SIC_PREFIXES.items():
            if pref3.startswith(pref):
                score += val

    return max(0.0, min(0.5, score))


def score_company_age(date_of_creation: str) -> float:
    """Score based on company age (established companies score higher)."""
    if not date_of_creation:
        return 0.05  # Unknown: small baseline

    try:
        created = datetime.strptime(date_of_creation, "%Y-%m-%d")
        years = (datetime.now() - created).days / 365.25

        if years >= 10:
            return 0.12
        elif years >= 5:
            return 0.10
        elif years >= 2:
            return 0.07
        elif years >= 1:
            return 0.04
        else:
            return 0.02  # Very new
    except (ValueError, TypeError):
        return 0.05


def score_company_type(company_type: str) -> float:
    """Score based on company type."""
    ct = (company_type or "").lower().strip()
    return COMPANY_TYPE_WEIGHTS.get(ct, 0.03)


def score_name_keywords(name: str) -> float:
    """Score based on keywords in company name."""
    if not name:
        return 0.0

    name_lower = name.lower()
    words = set(re.findall(r"\w+", name_lower))

    score = 0.0

    # Positive keywords
    tech_matches = words & TECH_KEYWORDS
    if tech_matches:
        score += min(0.15, len(tech_matches) * 0.05)

    # Negative keywords
    negative_matches = words & NEGATIVE_KEYWORDS
    if negative_matches:
        score -= min(0.10, len(negative_matches) * 0.05)

    return score


def calculate_features(row: TransformEnrichRow) -> ScoringFeatures:
    """Calculate all scoring features for a company row."""
    sics = parse_sic_list(row["ch_sic_codes"])
    status = row["ch_company_status"].lower()
    date_of_creation = row["ch_date_of_creation"]
    company_type = row["ch_company_type"]
    company_name = row["ch_company_name"] or row["Organisation Name"]

    return ScoringFeatures(
        sic_tech_score=score_from_sic(sics),
        is_active_score=0.10 if status == "active" else 0.0,
        company_age_score=score_company_age(date_of_creation),
        company_type_score=score_company_type(company_type),
        name_keyword_score=score_name_keywords(company_name),
    )
