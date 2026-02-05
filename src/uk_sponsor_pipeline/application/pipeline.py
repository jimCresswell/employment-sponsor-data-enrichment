"""Application pipeline orchestration for cache-only run-all.

Example:
    >>> from uk_sponsor_pipeline.config import PipelineConfig
    >>> from uk_sponsor_pipeline.application.pipeline import run_pipeline
    >>> config = PipelineConfig.from_env()
    >>> fs = ...  # Injected FileSystem from the CLI/composition root
    >>> http_client = ...  # Injected HttpClient when CH_SOURCE_TYPE is "api"
    >>> result = run_pipeline(
    ...     config=config,
    ...     register_path="data/cache/snapshots/sponsor/2026-02-01/clean.csv",
    ...     fs=fs,
    ...     http_client=http_client,
    ... )
    >>> result.usage["shortlist"]
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import PipelineConfig
from ..exceptions import DependencyMissingError
from ..protocols import FileSystem, HttpClient
from .transform_enrich import run_transform_enrich
from .transform_score import run_transform_score
from .usage import run_usage_shortlist


@dataclass(frozen=True)
class PipelineRunResult:
    """Results from a cache-only pipeline run."""

    enrich: dict[str, Path]
    score: dict[str, Path]
    usage: dict[str, Path]


def run_pipeline(
    *,
    config: PipelineConfig,
    register_path: str | Path,
    enrich_out_dir: str | Path = "data/processed",
    score_out_dir: str | Path = "data/processed",
    resume: bool = True,
    fs: FileSystem | None = None,
    http_client: HttpClient | None = None,
) -> PipelineRunResult:
    """Run transform-enrich → transform-score → usage-shortlist.

    Args:
        config: Pipeline configuration (required; load once at entry point).
        register_path: Path to sponsor clean snapshot CSV.
        enrich_out_dir: Directory for transform-enrich outputs.
        score_out_dir: Directory for transform-score outputs (scored + usage outputs).
        resume: If True, transform-enrich resumes from existing artefacts.
        fs: Filesystem (required; inject at entry point).
        http_client: Companies House HTTP client (required for API source).

    Returns:
        PipelineRunResult with outputs for each step.
    """
    if fs is None:
        raise DependencyMissingError("FileSystem", reason="Inject it at the entry point.")
    if config.ch_source_type == "api" and http_client is None:
        raise DependencyMissingError("HttpClient", reason="When CH_SOURCE_TYPE is 'api'.")

    enrich_outs = run_transform_enrich(
        register_path=register_path,
        out_dir=enrich_out_dir,
        cache_dir="data/cache/companies_house",
        config=config,
        http_client=http_client,
        resume=resume,
        fs=fs,
    )

    score_outs = run_transform_score(
        enriched_path=enrich_outs["enriched"],
        out_dir=score_out_dir,
        config=config,
        fs=fs,
    )

    usage_outs = run_usage_shortlist(
        scored_path=score_outs["scored"],
        out_dir=score_out_dir,
        config=config,
        fs=fs,
    )

    return PipelineRunResult(
        enrich=enrich_outs,
        score=score_outs,
        usage=usage_outs,
    )
