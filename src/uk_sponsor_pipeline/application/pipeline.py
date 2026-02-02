"""Application pipeline orchestration for running all steps in sequence.

Example:
    >>> from uk_sponsor_pipeline.config import PipelineConfig
    >>> from uk_sponsor_pipeline.application.pipeline import run_pipeline
    >>> config = PipelineConfig.from_env()
    >>> result = run_pipeline(config=config, skip_download=True)
    >>> result.score["shortlist"]
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import PipelineConfig
from ..infrastructure import LocalFileSystem
from ..protocols import FileSystem, HttpClient, HttpSession
from .extract import ExtractResult, extract_register
from .transform_enrich import run_transform_enrich
from .transform_register import TransformRegisterResult, run_transform_register
from .transform_score import run_transform_score


@dataclass(frozen=True)
class PipelineRunResult:
    """Results from a full pipeline run."""

    extract: ExtractResult | None
    register: TransformRegisterResult
    enrich: dict[str, Path]
    score: dict[str, Path]


def run_pipeline(
    *,
    config: PipelineConfig,
    skip_download: bool = False,
    raw_dir: str | Path = "data/raw",
    reports_dir: str | Path = "reports",
    register_out_path: str | Path = "data/interim/sponsor_register_filtered.csv",
    enrich_out_dir: str | Path = "data/processed",
    cache_dir: str | Path = "data/cache/companies_house",
    score_out_dir: str | Path = "data/processed",
    resume: bool = True,
    fs: FileSystem | None = None,
    http_client: HttpClient | None = None,
    http_session: HttpSession | None = None,
    session: HttpSession | None = None,
) -> PipelineRunResult:
    """Run extract → transform-register → transform-enrich → transform-score.

    Args:
        config: Pipeline configuration (required; load once at entry point).
        skip_download: If True, assume raw CSV already exists and skip extract.
        raw_dir: Directory for raw CSV files (extract output and register input).
        reports_dir: Directory for reports/manifest outputs.
        register_out_path: Output path for the register transform CSV.
        enrich_out_dir: Directory for transform-enrich outputs.
        cache_dir: Directory for Companies House API cache.
        score_out_dir: Directory for transform-score outputs.
        resume: If True, transform-enrich resumes from existing artefacts.
        fs: Optional filesystem for testing.
        http_client: Optional Companies House HTTP client.
        http_session: Optional HTTP session for file-based Companies House sources.
        session: Optional HTTP session for extract download.

    Returns:
        PipelineRunResult with outputs for each step.
    """
    fs = fs or LocalFileSystem()

    extract_result: ExtractResult | None = None
    if not skip_download:
        extract_result = extract_register(
            data_dir=raw_dir,
            reports_dir=reports_dir,
            session=session,
            fs=fs,
        )

    register_result = run_transform_register(
        raw_dir=raw_dir,
        out_path=register_out_path,
        reports_dir=reports_dir,
        fs=fs,
    )

    enrich_outs = run_transform_enrich(
        register_path=register_result.output_path,
        out_dir=enrich_out_dir,
        cache_dir=cache_dir,
        config=config,
        http_client=http_client,
        http_session=http_session,
        resume=resume,
        fs=fs,
    )

    score_outs = run_transform_score(
        enriched_path=enrich_outs["enriched"],
        out_dir=score_out_dir,
        config=config,
        fs=fs,
    )

    return PipelineRunResult(
        extract=extract_result,
        register=register_result,
        enrich=enrich_outs,
        score=score_outs,
    )
