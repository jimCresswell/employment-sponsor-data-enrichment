"""Transform score: composable scoring model for tech-likelihood.

Improvements over original:
- Multi-feature additive scoring model
- Transparent feature contributions
- Explainability output (companies_explain.csv)
- Geographic filtering support
- Location alias profiles for region/locality/postcode matching
- Configurable thresholds via CLI/env
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import PipelineConfig
from ..domain.location_profiles import (
    GeoFilter,
    LocationProfile,
    build_geo_filter,
    build_location_profiles,
)
from ..domain.location_profiles import matches_geo_filter as domain_matches_geo_filter
from ..domain.scoring import ScoringFeatures, calculate_features
from ..infrastructure import LocalFileSystem
from ..infrastructure.io.validation import parse_location_aliases, validate_as
from ..observability import get_logger
from ..protocols import FileSystem
from ..schemas import (
    TRANSFORM_ENRICH_OUTPUT_COLUMNS,
    TRANSFORM_SCORE_EXPLAIN_COLUMNS,
    TRANSFORM_SCORE_OUTPUT_COLUMNS,
    validate_columns,
)
from ..types import TransformEnrichRow


def _load_location_profiles(path: Path, fs: FileSystem) -> list[LocationProfile]:
    if not fs.exists(path):
        raise RuntimeError(
            "Location aliases file not found. Create data/reference/location_aliases.json "
            "or set LOCATION_ALIASES_PATH to a valid file."
        )
    payload = fs.read_json(path)
    return build_location_profiles(parse_location_aliases(payload))


def _matches_geographic_filter_row(row: pd.Series[str], geo_filter: GeoFilter) -> bool:
    return domain_matches_geo_filter(validate_as(TransformEnrichRow, row.to_dict()), geo_filter)


def run_transform_score(
    enriched_path: str | Path = "data/processed/companies_house_enriched.csv",
    out_dir: str | Path = "data/processed",
    config: PipelineConfig | None = None,
    fs: FileSystem | None = None,
) -> dict[str, Path]:
    """Transform enrich outputs into scores and a shortlist.

    Args:
        enriched_path: Path to enriched Companies House CSV.
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
    logger = get_logger("uk_sponsor_pipeline.transform_score")
    enriched_path = Path(enriched_path)
    out_dir = Path(out_dir)
    fs.mkdir(out_dir, parents=True)

    df = fs.read_csv(enriched_path).fillna("")
    validate_columns(
        list(df.columns),
        frozenset(TRANSFORM_ENRICH_OUTPUT_COLUMNS),
        "Transform enrich output",
    )

    # Ensure match_score is numeric for correct sorting
    df["match_score"] = pd.to_numeric(df["match_score"], errors="coerce").fillna(0.0)

    logger.info("Scoring: %s companies", len(df))

    # Calculate features for each row
    features_list: list[ScoringFeatures] = []
    for _, row in df.iterrows():
        features_list.append(calculate_features(validate_as(TransformEnrichRow, row.to_dict())))

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

    validate_columns(
        list(df.columns), frozenset(TRANSFORM_SCORE_OUTPUT_COLUMNS), "Transform score output"
    )

    # Full scored output
    scored_path = out_dir / "companies_scored.csv"
    fs.write_csv(df, scored_path)
    logger.info("Scored: %s", scored_path)

    # Apply filters for shortlist
    shortlist = df[
        (df["role_fit_score"].astype(float) >= config.tech_score_threshold)
        & (df["role_fit_bucket"].isin(["strong", "possible"]))
    ].copy()

    # Apply geographic filter if specified
    if config.geo_filter_region or config.geo_filter_postcodes:
        aliases_path = Path(config.location_aliases_path)
        profiles = _load_location_profiles(aliases_path, fs)
        geo_filter = build_geo_filter(
            config.geo_filter_region, config.geo_filter_postcodes, profiles
        )
        geo_mask = shortlist.apply(
            _matches_geographic_filter_row,
            axis=1,
            args=(geo_filter,),
        )
        shortlist = shortlist[geo_mask]
        logger.info("Geographic filter: %s companies match", int(geo_mask.sum()))

    shortlist_path = out_dir / "companies_shortlist.csv"
    fs.write_csv(shortlist, shortlist_path)
    logger.info("Shortlist: %s (%s companies)", shortlist_path, len(shortlist))

    # Explainability output
    validate_columns(
        list(shortlist.columns),
        frozenset(TRANSFORM_SCORE_EXPLAIN_COLUMNS),
        "Shortlist output",
    )
    explain_df = shortlist[list(TRANSFORM_SCORE_EXPLAIN_COLUMNS)]
    explain_path = out_dir / "companies_explain.csv"
    fs.write_csv(explain_df, explain_path)
    logger.info("Explainability: %s", explain_path)

    return {"scored": scored_path, "shortlist": shortlist_path, "explain": explain_path}
