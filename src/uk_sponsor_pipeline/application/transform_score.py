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
from ..infrastructure import LocalFileSystem
from ..infrastructure.io.validation import validate_as
from ..observability import get_logger
from ..protocols import FileSystem
from ..schemas import (
    TRANSFORM_ENRICH_OUTPUT_COLUMNS,
    TRANSFORM_SCORE_OUTPUT_COLUMNS,
    validate_columns,
)
from ..types import TransformEnrichRow


def run_transform_score(
    enriched_path: str | Path = "data/processed/companies_house_enriched.csv",
    out_dir: str | Path = "data/processed",
    config: PipelineConfig | None = None,
    fs: FileSystem | None = None,
) -> dict[str, Path]:
    """Transform enrich outputs into scored artefacts.

    Args:
        enriched_path: Path to enriched Companies House CSV.
        out_dir: Directory for output files.
        config: Pipeline configuration (required; load at entry point).
        fs: Optional filesystem for testing.

    Returns:
        Dict with path to scored file.
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

    return {"scored": scored_path}
