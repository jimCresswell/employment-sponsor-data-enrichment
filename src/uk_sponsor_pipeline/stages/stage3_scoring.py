"""Stage 3: Composable scoring model for tech-likelihood.

Improvements over original:
- Multi-feature additive scoring model
- Transparent feature contributions
- Explainability output (stage3_explain.csv)
- Geographic filtering support
- Configurable thresholds via CLI/env
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

import pandas as pd

from ..config import PipelineConfig
from ..infrastructure import LocalFileSystem
from ..observability import get_logger
from ..protocols import FileSystem
from ..schemas import (
    STAGE2_ENRICHED_COLUMNS,
    STAGE3_EXPLAIN_COLUMNS,
    STAGE3_SCORED_COLUMNS,
    validate_columns,
)
from ..types import Stage2EnrichedRow

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


def _parse_sic_list(s: str) -> list[str]:
    """Parse semicolon/comma-separated SIC codes."""
    if not isinstance(s, str) or not s.strip():
        return []
    parts = [p.strip() for p in s.replace(",", ";").split(";")]
    return [p for p in parts if p]


def _score_from_sic(sics: list[str]) -> float:
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


def _score_company_age(date_of_creation: str) -> float:
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


def _score_company_type(company_type: str) -> float:
    """Score based on company type."""
    ct = (company_type or "").lower().strip()
    return COMPANY_TYPE_WEIGHTS.get(ct, 0.03)


def _score_name_keywords(name: str) -> float:
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


def calculate_features(row: Stage2EnrichedRow) -> ScoringFeatures:
    """Calculate all scoring features for a company row."""
    sics = _parse_sic_list(row["ch_sic_codes"])
    status = row["ch_company_status"].lower()
    date_of_creation = row["ch_date_of_creation"]
    company_type = row["ch_company_type"]
    company_name = row["ch_company_name"] or row["Organisation Name"]

    return ScoringFeatures(
        sic_tech_score=_score_from_sic(sics),
        is_active_score=0.10 if status == "active" else 0.0,
        company_age_score=_score_company_age(date_of_creation),
        company_type_score=_score_company_type(company_type),
        name_keyword_score=_score_name_keywords(company_name),
    )


def _matches_geographic_filter(
    row: Stage2EnrichedRow,
    regions: tuple[str, ...],
    postcodes: tuple[str, ...],
) -> bool:
    """Check if company matches geographic filters."""
    if not regions and not postcodes:
        return True  # No filter = all pass

    region = row["ch_address_region"].lower()
    locality = row["ch_address_locality"].lower()
    postcode = row["ch_address_postcode"].upper()

    # Check region filter
    if regions:
        region_match = any(r.lower() in region or r.lower() in locality for r in regions)
        if region_match:
            return True

    # Check postcode prefix filter
    if postcodes:
        postcode_match = any(postcode.startswith(p.upper()) for p in postcodes)
        if postcode_match:
            return True

    return not regions and not postcodes  # Only pass if no filters specified


def run_stage3(
    stage2_path: str | Path = "data/processed/stage2_enriched_companies_house.csv",
    out_dir: str | Path = "data/processed",
    config: PipelineConfig | None = None,
    fs: FileSystem | None = None,
) -> dict[str, Path]:
    """Stage 3: Score companies for tech-likelihood and produce shortlist.

    Args:
        stage2_path: Path to Stage 2 enriched CSV.
        out_dir: Directory for output files.
        config: Pipeline configuration (required; load at entry point).
        fs: Optional filesystem for testing.

    Returns:
        Dict with paths to scored, shortlist, and explain files.
    """
    if config is None:
        raise RuntimeError(
            "PipelineConfig is required. Load it once at the entry point with "
            "PipelineConfig.from_env() and pass it through."
        )

    fs = fs or LocalFileSystem()
    logger = get_logger("uk_sponsor_pipeline.stage3")
    stage2_path = Path(stage2_path)
    out_dir = Path(out_dir)
    fs.mkdir(out_dir, parents=True)

    df = fs.read_csv(stage2_path).fillna("")
    validate_columns(
        list(df.columns), frozenset(STAGE2_ENRICHED_COLUMNS), "Stage 2 enriched output"
    )

    # Ensure match_score is numeric for correct sorting
    df["match_score"] = pd.to_numeric(df["match_score"], errors="coerce").fillna(0.0)

    logger.info("Scoring: %s companies", len(df))

    # Calculate features for each row
    features_list: list[ScoringFeatures] = []
    for _, row in df.iterrows():
        features_list.append(calculate_features(cast(Stage2EnrichedRow, row.to_dict())))

    # Add feature columns to DataFrame
    df["sic_tech_score"] = [f.sic_tech_score for f in features_list]
    df["is_active_score"] = [f.is_active_score for f in features_list]
    df["company_age_score"] = [f.company_age_score for f in features_list]
    df["company_type_score"] = [f.company_type_score for f in features_list]
    df["name_keyword_score"] = [f.name_keyword_score for f in features_list]
    df["role_fit_score"] = [f.total for f in features_list]
    df["role_fit_bucket"] = [f.bucket for f in features_list]

    # Sort by score (numeric match_score ensures stable tie-breaking)
    df = df.sort_values(["role_fit_score", "match_score"], ascending=[False, False])

    validate_columns(list(df.columns), frozenset(STAGE3_SCORED_COLUMNS), "Stage 3 scored output")

    # Full scored output
    scored_path = out_dir / "stage3_scored.csv"
    fs.write_csv(df, scored_path)
    logger.info("Scored: %s", scored_path)

    # Apply filters for shortlist
    shortlist = df[
        (df["role_fit_score"].astype(float) >= config.tech_score_threshold)
        & (df["role_fit_bucket"].isin(["strong", "possible"]))
    ].copy()

    # Apply geographic filter if specified
    if config.geo_filter_regions or config.geo_filter_postcodes:
        geo_mask = shortlist.apply(
            lambda row: _matches_geographic_filter(
                row.to_dict(),
                config.geo_filter_regions,
                config.geo_filter_postcodes,
            ),
            axis=1,
        )
        shortlist = shortlist[geo_mask]
        logger.info("Geographic filter: %s companies match", int(geo_mask.sum()))

    shortlist_path = out_dir / "stage3_shortlist_tech.csv"
    fs.write_csv(shortlist, shortlist_path)
    logger.info("Shortlist: %s (%s companies)", shortlist_path, len(shortlist))

    # Explainability output
    validate_columns(
        list(shortlist.columns), frozenset(STAGE3_EXPLAIN_COLUMNS), "Stage 3 shortlist"
    )
    explain_df = shortlist[list(STAGE3_EXPLAIN_COLUMNS)]
    explain_path = out_dir / "stage3_explain.csv"
    fs.write_csv(explain_df, explain_path)
    logger.info("Explainability: %s", explain_path)

    return {"scored": scored_path, "shortlist": shortlist_path, "explain": explain_path}
