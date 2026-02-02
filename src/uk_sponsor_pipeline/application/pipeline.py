"""Application pipeline orchestration for running all steps in sequence.

Example:
    >>> from uk_sponsor_pipeline.config import PipelineConfig
    >>> from uk_sponsor_pipeline.application.pipeline import run_pipeline
    >>> from uk_sponsor_pipeline.infrastructure import LocalFileSystem, build_companies_house_client
    >>> config = PipelineConfig.from_env()
    >>> fs = LocalFileSystem()
    >>> http_client = build_companies_house_client(
    ...     api_key=config.ch_api_key,
    ...     cache_dir="data/cache/companies_house",
    ...     max_rpm=config.ch_max_rpm,
    ...     min_delay_seconds=config.ch_sleep_seconds,
    ...     circuit_breaker_threshold=config.ch_circuit_breaker_threshold,
    ...     circuit_breaker_timeout_seconds=config.ch_circuit_breaker_timeout_seconds,
    ...     max_retries=config.ch_max_retries,
    ...     backoff_factor=config.ch_backoff_factor,
    ...     max_backoff_seconds=config.ch_backoff_max_seconds,
    ...     jitter_seconds=config.ch_backoff_jitter_seconds,
    ...     timeout_seconds=config.ch_timeout_seconds,
    ... )
    >>> result = run_pipeline(config=config, skip_download=True, fs=fs, http_client=http_client)
    >>> result.usage["shortlist"]
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import PipelineConfig
from ..protocols import FileSystem, HttpClient, HttpSession
from .extract import ExtractResult, extract_register
from .transform_enrich import run_transform_enrich
from .transform_register import TransformRegisterResult, run_transform_register
from .transform_score import run_transform_score
from .usage import run_usage_shortlist


@dataclass(frozen=True)
class PipelineRunResult:
    """Results from a full pipeline run."""

    extract: ExtractResult | None
    register: TransformRegisterResult
    enrich: dict[str, Path]
    score: dict[str, Path]
    usage: dict[str, Path]


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
    """Run extract → transform-register → transform-enrich → transform-score → usage-shortlist.

    Args:
        config: Pipeline configuration (required; load once at entry point).
        skip_download: If True, assume raw CSV already exists and skip extract.
        raw_dir: Directory for raw CSV files (extract output and register input).
        reports_dir: Directory for reports/manifest outputs.
        register_out_path: Output path for the register transform CSV.
        enrich_out_dir: Directory for transform-enrich outputs.
        cache_dir: Directory for Companies House API cache.
        score_out_dir: Directory for transform-score outputs (scored + usage outputs).
        resume: If True, transform-enrich resumes from existing artefacts.
        fs: Filesystem (required; inject at entry point).
        http_client: Companies House HTTP client (required for API source).
        http_session: HTTP session for file-based Companies House sources.
        session: HTTP session for extract download (required if not skipping).

    Returns:
        PipelineRunResult with outputs for each step.
    """
    if fs is None:
        raise RuntimeError("FileSystem is required. Inject it at the entry point.")
    if not skip_download and session is None:
        raise RuntimeError("HttpSession is required for extract. Inject it at the entry point.")
    if config.ch_source_type == "api" and http_client is None:
        raise RuntimeError("HttpClient is required when CH_SOURCE_TYPE is 'api'.")

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

    usage_outs = run_usage_shortlist(
        scored_path=score_outs["scored"],
        out_dir=score_out_dir,
        config=config,
        fs=fs,
    )

    return PipelineRunResult(
        extract=extract_result,
        register=register_result,
        enrich=enrich_outs,
        score=score_outs,
        usage=usage_outs,
    )
