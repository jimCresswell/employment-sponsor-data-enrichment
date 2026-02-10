"""Transform score: composable scoring model for tech-likelihood.

Improvements over original:
- Multi-feature additive scoring model
- Transparent feature contributions
- Stable scored artefact for downstream usage
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import PipelineConfig
from ..domain.scoring import ScoringFeatures, calculate_features
from ..domain.scoring_profiles import ScoringProfile
from ..exceptions import (
    DependencyMissingError,
    InvalidMatchScoreError,
    PipelineConfigMissingError,
)
from ..io_validation import validate_as
from ..observability import get_logger
from ..protocols import FileSystem
from ..schemas import (
    TRANSFORM_ENRICH_OUTPUT_COLUMNS,
    TRANSFORM_SCORE_OUTPUT_COLUMNS,
    validate_columns,
)
from ..types import TransformEnrichRow
from .scoring_profiles import load_scoring_profile_catalog, resolve_scoring_profile

DEFAULT_SCORING_PROFILE_PATH = Path("data/reference/scoring_profiles.json")


def _normalise_invalid_match_score(value: object) -> str:
    text = str(value).strip()
    return text if text else "<empty>"


def _format_invalid_match_scores(values: pd.Series) -> str:
    unique_values = sorted(
        {_normalise_invalid_match_score(value) for value in values.unique().tolist()}
    )
    if not unique_values:
        return "<unknown>"
    sample = ", ".join(unique_values[:5])
    if len(unique_values) > 5:
        return f"{sample}, ..."
    return sample


def _parse_match_score(values: pd.Series) -> pd.Series:
    try:
        numeric = pd.to_numeric(values, errors="raise")
    except (TypeError, ValueError) as exc:
        coerced = pd.to_numeric(values, errors="coerce")
        invalid_values = values[coerced.isna()]
        sample = _format_invalid_match_scores(invalid_values)
        raise InvalidMatchScoreError(sample) from exc
    if numeric.isna().any():
        invalid_values = values[numeric.isna()]
        sample = _format_invalid_match_scores(invalid_values)
        raise InvalidMatchScoreError(sample)
    return numeric


def _resolve_active_profile(config: PipelineConfig, fs: FileSystem) -> ScoringProfile:
    profile_path_text = config.sector_profile_path.strip()
    profile_name = config.sector_name.strip()
    profile_path = Path(profile_path_text) if profile_path_text else DEFAULT_SCORING_PROFILE_PATH
    catalog = load_scoring_profile_catalog(path=profile_path, fs=fs)
    return resolve_scoring_profile(catalog, profile_name=profile_name or None)


def run_transform_score(
    enriched_path: str | Path = "data/processed/sponsor_enriched.csv",
    out_dir: str | Path = "data/processed",
    config: PipelineConfig | None = None,
    fs: FileSystem | None = None,
) -> dict[str, Path]:
    """Transform enrich outputs into scored artefacts.

    Args:
        enriched_path: Path to enriched Companies House CSV.
        out_dir: Directory for output files.
        config: Pipeline configuration (required; load at entry point).
        fs: Filesystem (required; inject at entry point).

    Returns:
        Dict with path to scored file.
    """
    if config is None:
        raise PipelineConfigMissingError()

    if fs is None:
        raise DependencyMissingError("FileSystem", reason="Inject it at the entry point.")
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
    df["match_score"] = _parse_match_score(df["match_score"])

    active_profile = _resolve_active_profile(config, fs)
    logger.info("Using scoring profile: %s", active_profile.name)

    logger.info("Scoring: %s companies", len(df))

    # Calculate features for each row
    features_list: list[ScoringFeatures] = []
    for _, row in df.iterrows():
        features_list.append(
            calculate_features(
                validate_as(TransformEnrichRow, row.to_dict()),
                profile=active_profile,
            )
        )

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

    return {"scored": scored_path}
