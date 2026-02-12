"""Usage shortlist: filter scored artefacts into shortlist and explain outputs.

Usage example:
    >>> from uk_sponsor_pipeline.application.usage import run_usage_shortlist
    >>> from uk_sponsor_pipeline.config import PipelineConfig
    >>> config = PipelineConfig.from_env()
    >>> fs = ...  # Injected FileSystem from the CLI/composition root
    >>> run_usage_shortlist(
    ...     scored_path="data/processed/companies_scored.csv",
    ...     config=config,
    ...     fs=fs,
    ... )
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
from ..domain.location_profiles import (
    matches_geo_filter as domain_matches_geo_filter,
)
from ..exceptions import (
    DependencyMissingError,
    InvalidEmployeeCountError,
    LocationAliasesNotFoundError,
    PipelineConfigMissingError,
)
from ..io_validation import parse_location_aliases, validate_as
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
        raise LocationAliasesNotFoundError()
    payload = fs.read_json(path)
    return build_location_profiles(parse_location_aliases(payload))


def _matches_geographic_filter_row(row: pd.Series[str], geo_filter: GeoFilter) -> bool:
    payload = row.to_dict()
    enrich_payload = {key: payload[key] for key in TRANSFORM_ENRICH_OUTPUT_COLUMNS}
    return domain_matches_geo_filter(validate_as(TransformEnrichRow, enrich_payload), geo_filter)


def _build_employee_count_filter_mask(
    shortlist: pd.DataFrame,
    *,
    min_employee_count: int,
    include_unknown_employee_count: bool,
) -> pd.Series:
    employee_counts = shortlist["employee_count"].fillna("").astype(str).str.strip()
    unknown_mask = employee_counts.eq("")
    known_counts = employee_counts[~unknown_mask]
    valid_known_mask = known_counts.str.fullmatch(r"[1-9][0-9]*").fillna(False)
    if not bool(valid_known_mask.all()):
        invalid_values = sorted(set(known_counts[~valid_known_mask].tolist()))
        sample = ", ".join(invalid_values[:3])
        raise InvalidEmployeeCountError(sample)

    meets_minimum = pd.Series(False, index=shortlist.index)
    if not known_counts.empty:
        meets_minimum.loc[known_counts.index] = known_counts.astype(int) >= min_employee_count

    if include_unknown_employee_count:
        return meets_minimum | unknown_mask
    return meets_minimum


def run_usage_shortlist(
    scored_path: str | Path = "data/processed/companies_scored.csv",
    out_dir: str | Path = "data/processed",
    config: PipelineConfig | None = None,
    fs: FileSystem | None = None,
) -> dict[str, Path]:
    """Filter scored output into shortlist and explain artefacts.

    Args:
        scored_path: Path to scored Companies House CSV.
        out_dir: Directory for output files.
        config: Pipeline configuration (required; load at entry point).
        fs: Filesystem (required; inject at entry point).

    Returns:
        Dict with paths to shortlist and explain files.
    """
    if config is None:
        raise PipelineConfigMissingError()

    if fs is None:
        raise DependencyMissingError("FileSystem", reason="Inject it at the entry point.")
    logger = get_logger("uk_sponsor_pipeline.usage_shortlist")
    scored_path = Path(scored_path)
    out_dir = Path(out_dir)
    fs.mkdir(out_dir, parents=True)

    df = fs.read_csv(scored_path).fillna("")
    validate_columns(
        list(df.columns),
        frozenset(TRANSFORM_SCORE_OUTPUT_COLUMNS),
        "Scored output",
    )

    shortlist = df[
        (df["role_fit_score"].astype(float) >= config.tech_score_threshold)
        & (df["role_fit_bucket"].isin(["strong", "possible"]))
    ].copy()

    if config.min_employee_count is not None:
        employee_count_mask = _build_employee_count_filter_mask(
            shortlist,
            min_employee_count=config.min_employee_count,
            include_unknown_employee_count=config.include_unknown_employee_count,
        )
        shortlist = shortlist[employee_count_mask]
        logger.info(
            "Employee-count filter: %s companies match (min=%s, include_unknown=%s)",
            int(employee_count_mask.sum()),
            config.min_employee_count,
            config.include_unknown_employee_count,
        )

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

    validate_columns(
        list(shortlist.columns),
        frozenset(TRANSFORM_SCORE_EXPLAIN_COLUMNS),
        "Shortlist output",
    )
    explain_df = shortlist[list(TRANSFORM_SCORE_EXPLAIN_COLUMNS)]
    explain_path = out_dir / "companies_explain.csv"
    fs.write_csv(explain_df, explain_path)
    logger.info("Explainability: %s", explain_path)

    return {"shortlist": shortlist_path, "explain": explain_path}
