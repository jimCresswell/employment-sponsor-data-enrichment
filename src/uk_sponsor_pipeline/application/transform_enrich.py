"""Transform enrich: Companies House enrichment with improved matching and resumability.

Improvements over original:
- Multi-query strategy using query variants
- Transparent match scoring with component breakdown
- Confidence bands (high/medium/low)
- Resumable: skips already-processed orgs
- Circuit breaker prevents API hammering on errors
- Rate limiting on all requests (including failures)
"""

from __future__ import annotations

import math
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from ..config import PipelineConfig
from ..domain.companies_house import (
    CandidateMatch,
    MatchScore,
    build_candidate_row,
    build_enriched_row,
    build_unmatched_row,
    score_candidates,
)
from ..domain.organisation_identity import (
    generate_query_variants,
    normalise_org_name,
    simple_similarity,
)
from ..exceptions import AuthenticationError, CircuitBreakerOpen, RateLimitError
from ..infrastructure import LocalFileSystem, build_companies_house_client
from ..infrastructure.io.validation import validate_as
from ..observability import get_logger
from ..protocols import FileSystem, HttpClient, HttpSession
from ..schemas import (
    TRANSFORM_ENRICH_CANDIDATES_COLUMNS,
    TRANSFORM_ENRICH_OUTPUT_COLUMNS,
    TRANSFORM_ENRICH_UNMATCHED_COLUMNS,
    TRANSFORM_REGISTER_OUTPUT_COLUMNS,
    validate_columns,
)
from ..types import (
    BatchRange,
    TransformEnrichCandidateRow,
    TransformEnrichResumeReport,
    TransformEnrichRow,
    TransformEnrichUnmatchedRow,
    TransformRegisterRow,
)
from .companies_house_source import CompaniesHouseSource, build_companies_house_source

TRANSFORM_ENRICH_CHECKPOINT_COLUMNS = ("Organisation Name",)

__all__ = [
    "CandidateMatch",
    "MatchScore",
    "run_transform_enrich",
]


def _run_dir_name(now: datetime) -> str:
    return now.strftime("run_%Y%m%d_%H%M%S")


def _coerce_output_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    """Ensure output DataFrame has all required columns and correct order."""
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df[list(columns)]


def _append_csv(fs: FileSystem, df: pd.DataFrame, path: Path, columns: tuple[str, ...]) -> None:
    if df.empty:
        return
    coerced = _coerce_output_columns(df, columns)
    validate_columns(list(coerced.columns), frozenset(columns), "Transform enrich output")
    fs.append_csv(coerced, path)


def _as_str(value: object) -> str:
    if isinstance(value, str):
        return value
    return ""


def _coerce_register_row(raw: dict[str, object]) -> TransformRegisterRow:
    return {
        "Organisation Name": _as_str(raw.get("Organisation Name")),
        "org_name_normalised": _as_str(raw.get("org_name_normalised")),
        "has_multiple_towns": _as_str(raw.get("has_multiple_towns")),
        "has_multiple_counties": _as_str(raw.get("has_multiple_counties")),
        "Town/City": _as_str(raw.get("Town/City")),
        "County": _as_str(raw.get("County")),
        "Type & Rating": _as_str(raw.get("Type & Rating")),
        "Route": _as_str(raw.get("Route")),
        "raw_name_variants": _as_str(raw.get("raw_name_variants")),
    }


def _coerce_register_rows(raw_rows: list[dict[str, object]]) -> list[TransformRegisterRow]:
    return [_coerce_register_row(row) for row in raw_rows]


def _build_resume_report(
    *,
    status: str,
    register_path: Path,
    out_dir: Path,
    batch_size: int,
    batch_start: int,
    batch_count: int | None,
    total_register_orgs: int,
    total_unprocessed_at_start: int,
    total_batches_at_start: int,
    total_batches_overall: int,
    overall_batch_start: int | None,
    overall_batch_end: int | None,
    selected_batches: int,
    processed_in_run: int,
    processed_total: int,
    remaining: int,
    run_started_at_utc: datetime,
    run_finished_at_utc: datetime,
    run_duration_seconds: float,
    error_message: str | None = None,
) -> TransformEnrichResumeReport:
    batch_range: BatchRange | None = None
    if selected_batches:
        batch_range = {"start": batch_start, "end": batch_start + selected_batches - 1}

    overall_batch_range: BatchRange | None = None
    if overall_batch_start is not None and overall_batch_end is not None:
        overall_batch_range = {"start": overall_batch_start, "end": overall_batch_end}

    resume_command = (
        "uv run uk-sponsor transform-enrich "
        f"--input {register_path} --output-dir {out_dir} --resume"
    )

    return {
        "status": status,
        "error_message": error_message or "",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "run_started_at_utc": run_started_at_utc.isoformat(),
        "run_finished_at_utc": run_finished_at_utc.isoformat(),
        "run_duration_seconds": round(run_duration_seconds, 3),
        "register_path": str(register_path),
        "out_dir": str(out_dir),
        "batch_size": batch_size,
        "batch_start": batch_start,
        "batch_count": batch_count,
        "batch_range": batch_range,
        "total_register_orgs": total_register_orgs,
        "total_unprocessed_at_start": total_unprocessed_at_start,
        "total_batches_at_start": total_batches_at_start,
        "total_batches_overall": total_batches_overall,
        "overall_batch_range": overall_batch_range,
        "selected_batches": selected_batches,
        "processed_in_run": processed_in_run,
        "processed_total": processed_total,
        "remaining": remaining,
        "resume_command": resume_command,
    }


def run_transform_enrich(
    register_path: str | Path = "data/interim/sponsor_register_filtered.csv",
    out_dir: str | Path = "data/processed",
    cache_dir: str | Path = "data/cache/companies_house",
    config: PipelineConfig | None = None,
    http_client: HttpClient | None = None,
    http_session: HttpSession | None = None,
    resume: bool = True,
    fs: FileSystem | None = None,
    batch_start: int = 1,
    batch_count: int | None = None,
    batch_size: int | None = None,
) -> dict[str, Path]:
    """Transform register orgs with Companies House search + profile.

    Args:
        register_path: Path to register transform output CSV.
        out_dir: Directory for output files.
        cache_dir: Directory for API response cache.
        config: Pipeline configuration (required; load at entry point).
        http_client: HTTP client (creates default if None).
        resume: If True, skip already-processed organisations.
        fs: Optional filesystem for testing.
        batch_start: 1-based batch index to start from (after resume filtering).
        batch_count: Number of batches to run (None = run all remaining batches).
        batch_size: Override batch size for this run (default: config.ch_batch_size).

    Returns:
        Dict with paths to enriched, unmatched, candidates, checkpoint, and resume report files.

    Raises:
        AuthenticationError: If API key is invalid (stops immediately).
        CircuitBreakerOpen: If too many consecutive API failures.
        RuntimeError: If configuration is missing.
    """
    if config is None:
        raise RuntimeError(
            "PipelineConfig is required. Load it once at the entry point with "
            "PipelineConfig.from_env() and pass it through."
        )

    if config.ch_source_type == "api" and not config.ch_api_key:
        raise RuntimeError("Missing CH_API_KEY. Set it in .env or environment variables.")

    fs = fs or LocalFileSystem()
    register_path = Path(register_path)
    out_dir = Path(out_dir)
    cache_dir = Path(cache_dir)

    # Output paths
    logger = get_logger("uk_sponsor_pipeline.transform_enrich")
    if not resume:
        out_dir = out_dir / _run_dir_name(datetime.now(UTC))
        logger.info("Resume disabled; writing to new output directory: %s", out_dir)
    fs.mkdir(out_dir, parents=True)

    out_enriched = out_dir / "companies_house_enriched.csv"
    out_unmatched = out_dir / "companies_house_unmatched.csv"
    out_candidates = out_dir / "companies_house_candidates_top3.csv"
    out_checkpoint = out_dir / "companies_house_checkpoint.csv"
    out_resume_report = out_dir / "companies_house_resume_report.json"

    # Load input
    run_started_at_utc = datetime.now(UTC)
    run_started_perf = time.perf_counter()

    df = fs.read_csv(register_path).fillna("")
    validate_columns(
        list(df.columns),
        frozenset(TRANSFORM_REGISTER_OUTPUT_COLUMNS),
        "Transform register output",
    )
    total_register_orgs = len(df)

    # Normalise batching inputs
    batch_size_value = batch_size if batch_size is not None else config.ch_batch_size
    batch_size_value = max(1, int(batch_size_value))
    batch_start = int(batch_start)
    if batch_start < 1:
        raise ValueError("batch_start must be >= 1")
    if batch_count is not None:
        batch_count = int(batch_count)
        if batch_count < 1:
            raise ValueError("batch_count must be >= 1")

    # Load existing results for resumability
    already_processed: set[str] = set()
    if resume and fs.exists(out_checkpoint):
        checkpoint_df = fs.read_csv(out_checkpoint).fillna("")
        if "Organisation Name" in checkpoint_df.columns:
            already_processed.update(checkpoint_df["Organisation Name"].tolist())
    if resume and fs.exists(out_enriched):
        existing_df = fs.read_csv(out_enriched).fillna("")
        already_processed.update(existing_df["Organisation Name"].tolist())
    if resume and fs.exists(out_unmatched):
        existing_unmatched_df = fs.read_csv(out_unmatched).fillna("")
        already_processed.update(existing_unmatched_df["Organisation Name"].tolist())
    if already_processed:
        logger.info("Resuming: %s orgs already processed", len(already_processed))

    # Set up Companies House source
    if config.ch_source_type == "api":
        if http_client is None:
            http_client = build_companies_house_client(
                api_key=config.ch_api_key,
                cache_dir=cache_dir,
                max_rpm=config.ch_max_rpm,
                min_delay_seconds=config.ch_sleep_seconds,
                circuit_breaker_threshold=config.ch_circuit_breaker_threshold,
                circuit_breaker_timeout_seconds=config.ch_circuit_breaker_timeout_seconds,
                max_retries=config.ch_max_retries,
                backoff_factor=config.ch_backoff_factor,
                max_backoff_seconds=config.ch_backoff_max_seconds,
                jitter_seconds=config.ch_backoff_jitter_seconds,
                timeout_seconds=config.ch_timeout_seconds,
            )
    source: CompaniesHouseSource = build_companies_house_source(
        config=config,
        fs=fs,
        http_client=http_client,
        http_session=http_session,
    )

    # Process organisations in batches
    raw_rows = validate_as(list[dict[str, object]], df.to_dict(orient="records"))
    rows = _coerce_register_rows(raw_rows)
    to_process_all = [
        (idx, row)
        for idx, row in enumerate(rows)
        if row["Organisation Name"] not in already_processed
    ]
    total_unprocessed = len(to_process_all)
    total_batches = math.ceil(total_unprocessed / batch_size_value) if total_unprocessed else 0
    total_batches_overall = (
        math.ceil(total_register_orgs / batch_size_value) if total_register_orgs else 0
    )
    start_index = (batch_start - 1) * batch_size_value
    end_index = start_index + (batch_count * batch_size_value) if batch_count else total_unprocessed
    to_process = to_process_all[start_index:end_index]
    selected_batches = math.ceil(len(to_process) / batch_size_value) if to_process else 0
    to_process_indices = [idx for idx, _ in to_process]
    overall_batch_start = (
        (to_process_indices[0] // batch_size_value) + 1 if to_process_indices else None
    )
    overall_batch_end = (
        (to_process_indices[-1] // batch_size_value) + 1 if to_process_indices else None
    )
    overall_range_text = "n/a"
    if overall_batch_start is not None and overall_batch_end is not None:
        overall_range_text = (
            str(overall_batch_start)
            if overall_batch_start == overall_batch_end
            else f"{overall_batch_start}-{overall_batch_end}"
        )
    logger.info(
        "Processing %s organisations (batch size %s, batch start %s, batches %s/%s, "
        "overall batch %s/%s)",
        len(to_process),
        batch_size_value,
        batch_start,
        selected_batches,
        total_batches,
        overall_range_text,
        total_batches_overall,
    )

    batch_enriched: list[TransformEnrichRow] = []
    batch_unmatched: list[TransformEnrichUnmatchedRow] = []
    batch_candidates: list[TransformEnrichCandidateRow] = []
    batch_processed: list[str] = []
    processed_in_run = 0

    def flush_batch() -> None:
        if not batch_processed:
            return
        _append_csv(fs, pd.DataFrame(batch_enriched), out_enriched, TRANSFORM_ENRICH_OUTPUT_COLUMNS)
        _append_csv(
            fs,
            pd.DataFrame(batch_unmatched),
            out_unmatched,
            TRANSFORM_ENRICH_UNMATCHED_COLUMNS,
        )
        _append_csv(
            fs,
            pd.DataFrame(batch_candidates),
            out_candidates,
            TRANSFORM_ENRICH_CANDIDATES_COLUMNS,
        )
        _append_csv(
            fs,
            pd.DataFrame({"Organisation Name": batch_processed}),
            out_checkpoint,
            TRANSFORM_ENRICH_CHECKPOINT_COLUMNS,
        )
        batch_enriched.clear()
        batch_unmatched.clear()
        batch_candidates.clear()
        batch_processed.clear()

    def mark_processed(org_name: str) -> None:
        nonlocal processed_in_run
        batch_processed.append(org_name)
        processed_in_run += 1

    status = "complete"
    error_message: str | None = None

    try:
        for _, row in tqdm(to_process, total=len(to_process), desc="Companies House enrichment"):
            org = row["Organisation Name"]
            town = row.get("Town/City", "")
            county = row.get("County", "")
            org_norm = normalise_org_name(org)
            town_norm = normalise_org_name(town)
            county_norm = normalise_org_name(county)

            # Generate query variants
            query_variants = generate_query_variants(org)
            if not query_variants:
                query_variants = [org]

            best_match: CandidateMatch | None = None
            all_candidates: list[CandidateMatch] = []

            # Try each query variant
            for query in query_variants:
                try:
                    items = source.search(query)
                except (AuthenticationError, CircuitBreakerOpen, RateLimitError):
                    raise
                except Exception as e:
                    raise RuntimeError(
                        f"Companies House search failed for query '{query}': {e}"
                    ) from e

                scored = score_candidates(
                    org_norm=org_norm,
                    town_norm=town_norm,
                    county_norm=county_norm,
                    items=items,
                    query_used=query,
                    similarity_fn=simple_similarity,
                    normalise_fn=normalise_org_name,
                )
                all_candidates.extend(scored)

                # Stop early if we found a high-confidence match
                if scored and scored[0].score.total >= 0.85:
                    best_match = scored[0]
                    break

            # Sort candidates by score for stable top-N reporting
            if all_candidates:
                all_candidates.sort(key=lambda x: x.score.total, reverse=True)

            # If no high-confidence match, take the best overall
            if not best_match and all_candidates:
                best_match = all_candidates[0]

            # Record top 3 candidates for audit
            for rank, cand in enumerate(all_candidates[:3], start=1):
                batch_candidates.append(build_candidate_row(org=org, cand=cand, rank=rank))

            # Check if match is good enough
            if (
                not best_match
                or best_match.score.total < config.ch_min_match_score
                or not best_match.company_number
            ):
                batch_unmatched.append(build_unmatched_row(row=row, best_match=best_match))
                mark_processed(org)
                if len(batch_processed) >= batch_size_value:
                    flush_batch()
                continue

            # Fetch company profile
            try:
                profile = source.profile(best_match.company_number)
            except (AuthenticationError, CircuitBreakerOpen, RateLimitError):
                flush_batch()
                raise
            except Exception as e:
                flush_batch()
                raise RuntimeError(
                    f"Companies House profile fetch failed for {best_match.company_number}: {e}"
                ) from e
            batch_enriched.append(
                build_enriched_row(row=row, best_match=best_match, profile=profile)
            )
            mark_processed(org)
            if len(batch_processed) >= batch_size_value:
                flush_batch()

        flush_batch()

        # Finalise outputs: dedupe + sort for deterministic results
        if fs.exists(out_enriched):
            enriched_df = fs.read_csv(out_enriched).fillna("")
            enriched_df = _coerce_output_columns(enriched_df, TRANSFORM_ENRICH_OUTPUT_COLUMNS)
            enriched_df = enriched_df.drop_duplicates(subset=["Organisation Name"], keep="first")
            enriched_df = enriched_df.sort_values("Organisation Name")
            fs.write_csv(enriched_df, out_enriched)
        else:
            enriched_df = pd.DataFrame(columns=TRANSFORM_ENRICH_OUTPUT_COLUMNS)

        if fs.exists(out_unmatched):
            unmatched_df = fs.read_csv(out_unmatched).fillna("")
            unmatched_df = _coerce_output_columns(unmatched_df, TRANSFORM_ENRICH_UNMATCHED_COLUMNS)
            unmatched_df = unmatched_df.drop_duplicates(subset=["Organisation Name"], keep="first")
            unmatched_df = unmatched_df.sort_values("Organisation Name")
            fs.write_csv(unmatched_df, out_unmatched)
        else:
            unmatched_df = pd.DataFrame(columns=TRANSFORM_ENRICH_UNMATCHED_COLUMNS)

        if fs.exists(out_candidates):
            candidates_df = fs.read_csv(out_candidates).fillna("")
            candidates_df = _coerce_output_columns(
                candidates_df, TRANSFORM_ENRICH_CANDIDATES_COLUMNS
            )
            candidates_df["rank"] = pd.to_numeric(candidates_df["rank"], errors="coerce").fillna(0)
            candidates_df = candidates_df.drop_duplicates(
                subset=["Organisation Name", "rank", "candidate_company_number"], keep="first"
            )
            candidates_df = candidates_df.sort_values(["Organisation Name", "rank"])
            fs.write_csv(candidates_df, out_candidates)
        else:
            candidates_df = pd.DataFrame(columns=TRANSFORM_ENRICH_CANDIDATES_COLUMNS)

        if fs.exists(out_checkpoint):
            checkpoint_df = fs.read_csv(out_checkpoint).fillna("")
            if "Organisation Name" in checkpoint_df.columns:
                checkpoint_df = checkpoint_df.drop_duplicates(
                    subset=["Organisation Name"], keep="first"
                )
                checkpoint_df = checkpoint_df.sort_values("Organisation Name")
                fs.write_csv(checkpoint_df, out_checkpoint)

        logger.info("Enriched: %s matched, %s unmatched", len(enriched_df), len(unmatched_df))
    except KeyboardInterrupt:
        status = "interrupted"
        error_message = "KeyboardInterrupt"
        flush_batch()
        raise
    except Exception as exc:
        status = "error"
        error_message = str(exc)
        flush_batch()
        raise
    finally:
        run_finished_at_utc = datetime.now(UTC)
        run_duration_seconds = time.perf_counter() - run_started_perf
        processed_total = 0
        if fs.exists(out_checkpoint):
            checkpoint_df = fs.read_csv(out_checkpoint).fillna("")
            if "Organisation Name" in checkpoint_df.columns:
                processed_total = len(set(checkpoint_df["Organisation Name"].tolist()))
        remaining = max(0, total_register_orgs - processed_total)
        report = _build_resume_report(
            status=status,
            register_path=register_path,
            out_dir=out_dir,
            batch_size=batch_size_value,
            batch_start=batch_start,
            batch_count=batch_count,
            total_register_orgs=total_register_orgs,
            total_unprocessed_at_start=total_unprocessed,
            total_batches_at_start=total_batches,
            total_batches_overall=total_batches_overall,
            overall_batch_start=overall_batch_start,
            overall_batch_end=overall_batch_end,
            selected_batches=selected_batches,
            processed_in_run=processed_in_run,
            processed_total=processed_total,
            remaining=remaining,
            run_started_at_utc=run_started_at_utc,
            run_finished_at_utc=run_finished_at_utc,
            run_duration_seconds=run_duration_seconds,
            error_message=error_message,
        )
        fs.write_json(dict(report), out_resume_report)

    return {
        "enriched": out_enriched,
        "unmatched": out_unmatched,
        "candidates": out_candidates,
        "checkpoint": out_checkpoint,
        "resume_report": out_resume_report,
    }
