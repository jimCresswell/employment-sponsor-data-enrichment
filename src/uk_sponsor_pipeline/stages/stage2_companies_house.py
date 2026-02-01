"""Stage 2: Companies House enrichment with improved matching and resumability.

Improvements over original:
- Multi-query strategy using query variants
- Transparent match scoring with component breakdown
- Confidence bands (high/medium/low)
- Resumable: skips already-processed orgs
- Circuit breaker prevents API hammering on errors
- Rate limiting on all requests (including failures)
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

import pandas as pd
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from tqdm import tqdm

from ..config import PipelineConfig
from ..exceptions import AuthenticationError, CircuitBreakerOpen, RateLimitError
from ..infrastructure import (
    CachedHttpClient,
    CircuitBreaker,
    DiskCache,
    LocalFileSystem,
    RateLimiter,
    RetryPolicy,
)
from ..normalization import generate_query_variants, normalize_org_name
from ..protocols import FileSystem, HttpClient
from ..schemas import (
    STAGE1_OUTPUT_COLUMNS,
    STAGE2_CANDIDATES_COLUMNS,
    STAGE2_ENRICHED_COLUMNS,
    STAGE2_UNMATCHED_COLUMNS,
    validate_columns,
)

CH_BASE = "https://api.company-information.service.gov.uk"
STAGE2_CHECKPOINT_COLUMNS = ("Organisation Name",)


def _get_logger() -> logging.Logger:
    logger = logging.getLogger("uk_sponsor_pipeline.stage2")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        formatter.converter = time.gmtime
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


@dataclass
class MatchScore:
    """Transparent match scoring with component breakdown."""

    total: float
    name_similarity: float
    locality_bonus: float
    region_bonus: float
    status_bonus: float

    @property
    def confidence_band(self) -> str:
        """Classify match confidence."""
        if self.total >= 0.85:
            return "high"
        elif self.total >= 0.72:
            return "medium"
        else:
            return "low"


@dataclass
class CandidateMatch:
    """A candidate company match from Companies House."""

    company_number: str
    title: str
    status: str
    locality: str
    region: str
    postcode: str
    score: MatchScore
    query_used: str


def _normalize_for_cache(s: str) -> str:
    """Normalize string for cache key (avoid whitespace collisions)."""
    return re.sub(r"\s+", "_", s.strip().lower())


def _cache_key(prefix: str, *parts: str) -> str:
    """Create cache key from parts with normalization."""
    normalized = "_".join(_normalize_for_cache(p) for p in parts if p)
    h = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"{prefix}:{h}"


def _token_sort_key(s: str) -> str:
    """Create token-sorted key for name comparison."""
    toks = normalize_org_name(s).split()
    toks.sort()
    return " ".join(toks)


def _simple_similarity(a: str, b: str) -> float:
    """Calculate name similarity using Jaccard + character overlap."""
    a0, b0 = _token_sort_key(a), _token_sort_key(b)
    if not a0 or not b0:
        return 0.0

    set_a, set_b = set(a0.split()), set(b0.split())
    jacc = len(set_a & set_b) / max(1, len(set_a | set_b))

    common = sum(min(a0.count(ch), b0.count(ch)) for ch in set(a0))
    denom = max(len(a0), len(b0))
    char_overlap = common / denom if denom else 0.0

    return 0.6 * jacc + 0.4 * char_overlap


def _score_candidates(
    org_name: str, town: str, county: str, items: list[dict[str, Any]], query_used: str
) -> list[CandidateMatch]:
    """Score candidate companies from search results."""
    org_norm = normalize_org_name(org_name)
    town_norm = normalize_org_name(town)
    county_norm = normalize_org_name(county)

    out: list[CandidateMatch] = []
    for it in items:
        title = it.get("title") or ""
        number = it.get("company_number") or ""
        status = it.get("company_status") or ""
        addr = it.get("address") or {}
        loc = addr.get("locality") or ""
        region = addr.get("region") or ""
        postcode = addr.get("postal_code") or ""

        name_sim = _simple_similarity(org_norm, title)

        locality_bonus = 0.0
        if town_norm and (
            town_norm in normalize_org_name(loc) or town_norm in normalize_org_name(region)
        ):
            locality_bonus = 0.08

        region_bonus = 0.0
        if county_norm and county_norm in normalize_org_name(region):
            region_bonus = 0.05

        status_bonus = 0.05 if (status or "").lower() == "active" else 0.0

        total = min(1.0, name_sim + locality_bonus + region_bonus + status_bonus)

        score = MatchScore(
            total=total,
            name_similarity=name_sim,
            locality_bonus=locality_bonus,
            region_bonus=region_bonus,
            status_bonus=status_bonus,
        )

        out.append(CandidateMatch(number, title, status, loc, region, postcode, score, query_used))

    out.sort(key=lambda x: x.score.total, reverse=True)
    return out


def _basic_auth(api_key: str) -> HTTPBasicAuth:
    """Create HTTP Basic Auth credentials for Companies House API."""
    return HTTPBasicAuth(api_key, "")


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
    validate_columns(list(coerced.columns), frozenset(columns), "Stage 2 output")
    fs.append_csv(coerced, path)


def _build_resume_report(
    *,
    status: str,
    stage1_path: Path,
    out_dir: Path,
    batch_size: int,
    batch_start: int,
    batch_count: int | None,
    total_stage1_orgs: int,
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
) -> dict[str, Any]:
    batch_range = None
    if selected_batches:
        batch_range = {"start": batch_start, "end": batch_start + selected_batches - 1}

    overall_batch_range = None
    if overall_batch_start is not None and overall_batch_end is not None:
        overall_batch_range = {"start": overall_batch_start, "end": overall_batch_end}

    resume_command = (
        f"uv run uk-sponsor stage2 --input {stage1_path} --output-dir {out_dir} --resume"
    )

    return {
        "status": status,
        "error_message": error_message or "",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "run_started_at_utc": run_started_at_utc.isoformat(),
        "run_finished_at_utc": run_finished_at_utc.isoformat(),
        "run_duration_seconds": round(run_duration_seconds, 3),
        "stage1_path": str(stage1_path),
        "out_dir": str(out_dir),
        "batch_size": batch_size,
        "batch_start": batch_start,
        "batch_count": batch_count,
        "batch_range": batch_range,
        "total_stage1_orgs": total_stage1_orgs,
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


def run_stage2(
    stage1_path: str | Path = "data/interim/stage1_skilled_worker_A_rated_aggregated_by_org.csv",
    out_dir: str | Path = "data/processed",
    cache_dir: str | Path = "data/cache/companies_house",
    config: PipelineConfig | None = None,
    http_client: HttpClient | None = None,
    resume: bool = True,
    fs: FileSystem | None = None,
    batch_start: int = 1,
    batch_count: int | None = None,
    batch_size: int | None = None,
) -> dict[str, Path]:
    """Stage 2: Enrich Stage 1 orgs with Companies House search + profile.

    Args:
        stage1_path: Path to Stage 1 output CSV.
        out_dir: Directory for output files.
        cache_dir: Directory for API response cache.
        config: Pipeline configuration (loads from env if None).
        http_client: HTTP client (creates default if None).
        resume: If True, skip already-processed organizations.
        fs: Optional filesystem for testing.
        batch_start: 1-based batch index to start from (after resume filtering).
        batch_count: Number of batches to run (None = run all remaining batches).
        batch_size: Override batch size for this run (default: config.ch_batch_size).

    Returns:
        Dict with paths to enriched, unmatched, and candidates files.

    Raises:
        AuthenticationError: If API key is invalid (stops immediately).
        CircuitBreakerOpen: If too many consecutive API failures.
        RuntimeError: If configuration is missing.
    """
    load_dotenv()
    config = config or PipelineConfig.from_env()

    if not config.ch_api_key:
        raise RuntimeError("Missing CH_API_KEY. Set it in .env or environment variables.")

    fs = fs or LocalFileSystem()
    stage1_path = Path(stage1_path)
    out_dir = Path(out_dir)
    cache_dir = Path(cache_dir)
    fs.mkdir(out_dir, parents=True)

    # Output paths
    out_enriched = out_dir / "stage2_enriched_companies_house.csv"
    out_unmatched = out_dir / "stage2_unmatched.csv"
    out_candidates = out_dir / "stage2_candidates_top3.csv"
    out_checkpoint = out_dir / "stage2_checkpoint.csv"
    out_resume_report = out_dir / "stage2_resume_report.json"

    # Load input
    logger = _get_logger()
    run_started_at_utc = datetime.now(UTC)
    run_started_perf = time.perf_counter()

    df = fs.read_csv(stage1_path).fillna("")
    validate_columns(list(df.columns), frozenset(STAGE1_OUTPUT_COLUMNS), "Stage 1 output")
    total_stage1_orgs = len(df)

    # Normalize batching inputs
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

    # Set up HTTP client with circuit breaker
    if http_client is None:
        session = requests.Session()
        session.auth = _basic_auth(config.ch_api_key)
        cache = DiskCache(cache_dir)
        rate_limiter = RateLimiter(
            max_rpm=config.ch_max_rpm, min_delay_seconds=config.ch_sleep_seconds
        )
        circuit_breaker = CircuitBreaker(
            threshold=config.ch_circuit_breaker_threshold,
            recovery_timeout_seconds=config.ch_circuit_breaker_timeout_seconds,
        )
        retry_policy = RetryPolicy(
            max_retries=config.ch_max_retries,
            backoff_factor=config.ch_backoff_factor,
            max_backoff_seconds=config.ch_backoff_max_seconds,
            jitter_seconds=config.ch_backoff_jitter_seconds,
        )
        http_client = CachedHttpClient(
            session=session,
            cache=cache,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
            timeout_seconds=config.ch_timeout_seconds,
        )

    # Process organizations in batches
    rows = cast(list[dict[str, Any]], df.to_dict(orient="records"))
    to_process_all = [
        (idx, row)
        for idx, row in enumerate(rows)
        if row["Organisation Name"] not in already_processed
    ]
    total_unprocessed = len(to_process_all)
    total_batches = math.ceil(total_unprocessed / batch_size_value) if total_unprocessed else 0
    total_batches_overall = (
        math.ceil(total_stage1_orgs / batch_size_value) if total_stage1_orgs else 0
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
        "Processing %s organizations (batch size %s, batch start %s, batches %s/%s, overall batch %s/%s)",
        len(to_process),
        batch_size_value,
        batch_start,
        selected_batches,
        total_batches,
        overall_range_text,
        total_batches_overall,
    )

    batch_enriched: list[dict[str, Any]] = []
    batch_unmatched: list[dict[str, Any]] = []
    batch_candidates: list[dict[str, Any]] = []
    batch_processed: list[str] = []
    processed_in_run = 0

    def flush_batch() -> None:
        if not batch_processed:
            return
        _append_csv(fs, pd.DataFrame(batch_enriched), out_enriched, STAGE2_ENRICHED_COLUMNS)
        _append_csv(fs, pd.DataFrame(batch_unmatched), out_unmatched, STAGE2_UNMATCHED_COLUMNS)
        _append_csv(
            fs,
            pd.DataFrame(batch_candidates),
            out_candidates,
            STAGE2_CANDIDATES_COLUMNS,
        )
        _append_csv(
            fs,
            pd.DataFrame({"Organisation Name": batch_processed}),
            out_checkpoint,
            STAGE2_CHECKPOINT_COLUMNS,
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

            # Generate query variants
            query_variants = generate_query_variants(org)
            if not query_variants:
                query_variants = [org]

            best_match: CandidateMatch | None = None
            all_candidates: list[CandidateMatch] = []

            # Try each query variant
            try:
                for query in query_variants:
                    search_url = f"{CH_BASE}/search/companies?q={quote(query)}&items_per_page={config.ch_search_limit}"
                    cache_key = _cache_key("search", query, str(config.ch_search_limit))

                    try:
                        search = http_client.get_json(search_url, cache_key)
                    except requests.HTTPError as e:
                        # Non-fatal HTTP error - log and try next variant
                        logger.warning("Search error for '%s': %s", query, e)
                        continue
                    except Exception as e:
                        # Other errors - log and try next variant
                        logger.warning("Search error for '%s': %s", query, e)
                        continue

                    items = search.get("items") or []
                    scored = _score_candidates(org, town, county, items, query)
                    all_candidates.extend(scored)

                    # Stop early if we found a high-confidence match
                    if scored and scored[0].score.total >= 0.85:
                        best_match = scored[0]
                        break
            except (AuthenticationError, CircuitBreakerOpen, RateLimitError):
                flush_batch()
                raise

            # Sort candidates by score for stable top-N reporting
            if all_candidates:
                all_candidates.sort(key=lambda x: x.score.total, reverse=True)

            # If no high-confidence match, take the best overall
            if not best_match and all_candidates:
                best_match = all_candidates[0]

            # Record top 3 candidates for audit
            for rank, cand in enumerate(all_candidates[:3], start=1):
                batch_candidates.append(
                    {
                        "Organisation Name": org,
                        "rank": rank,
                        "candidate_company_number": cand.company_number,
                        "candidate_title": cand.title,
                        "candidate_status": cand.status,
                        "candidate_locality": cand.locality,
                        "candidate_region": cand.region,
                        "candidate_postcode": cand.postcode,
                        "candidate_score": round(cand.score.total, 4),
                        "score_name_similarity": round(cand.score.name_similarity, 4),
                        "score_locality_bonus": round(cand.score.locality_bonus, 4),
                        "score_region_bonus": round(cand.score.region_bonus, 4),
                        "score_status_bonus": round(cand.score.status_bonus, 4),
                        "query_used": cand.query_used,
                    }
                )

            # Check if match is good enough
            if (
                not best_match
                or best_match.score.total < config.ch_min_match_score
                or not best_match.company_number
            ):
                r = dict(row)
                r["match_status"] = "unmatched"
                r["best_candidate_score"] = round(best_match.score.total, 4) if best_match else ""
                r["best_candidate_title"] = best_match.title if best_match else ""
                r["best_candidate_company_number"] = best_match.company_number if best_match else ""
                r["match_error"] = ""
                batch_unmatched.append(r)
                mark_processed(org)
                if len(batch_processed) >= batch_size_value:
                    flush_batch()
                continue

            # Fetch company profile
            profile_url = f"{CH_BASE}/company/{best_match.company_number}"
            profile_key = _cache_key("profile", best_match.company_number)

            try:
                profile = http_client.get_json(profile_url, profile_key)
            except (AuthenticationError, CircuitBreakerOpen, RateLimitError):
                flush_batch()
                raise
            except Exception as e:
                r = dict(row)
                r["match_status"] = "profile_error"
                r["best_candidate_score"] = round(best_match.score.total, 4)
                r["best_candidate_title"] = best_match.title
                r["best_candidate_company_number"] = best_match.company_number
                r["match_error"] = str(e)
                batch_unmatched.append(r)
                mark_processed(org)
                if len(batch_processed) >= batch_size_value:
                    flush_batch()
                continue

            # Extract profile data
            sic = profile.get("sic_codes") or []
            ro = profile.get("registered_office_address") or {}

            out = dict(row)
            out.update(
                {
                    "match_status": "matched",
                    "match_score": round(best_match.score.total, 4),
                    "match_confidence": best_match.score.confidence_band,
                    "match_query_used": best_match.query_used,
                    "score_name_similarity": round(best_match.score.name_similarity, 4),
                    "score_locality_bonus": round(best_match.score.locality_bonus, 4),
                    "score_region_bonus": round(best_match.score.region_bonus, 4),
                    "score_status_bonus": round(best_match.score.status_bonus, 4),
                    "ch_company_number": best_match.company_number,
                    "ch_company_name": profile.get("company_name") or best_match.title,
                    "ch_company_status": profile.get("company_status") or best_match.status,
                    "ch_company_type": profile.get("type") or "",
                    "ch_date_of_creation": profile.get("date_of_creation") or "",
                    "ch_sic_codes": ";".join(sic) if isinstance(sic, list) else str(sic),
                    "ch_address_locality": ro.get("locality") or best_match.locality,
                    "ch_address_region": ro.get("region") or best_match.region,
                    "ch_address_postcode": ro.get("postal_code") or best_match.postcode,
                }
            )
            batch_enriched.append(out)
            mark_processed(org)
            if len(batch_processed) >= batch_size_value:
                flush_batch()

        flush_batch()

        # Finalise outputs: dedupe + sort for deterministic results
        if fs.exists(out_enriched):
            enriched_df = fs.read_csv(out_enriched).fillna("")
            enriched_df = _coerce_output_columns(enriched_df, STAGE2_ENRICHED_COLUMNS)
            enriched_df = enriched_df.drop_duplicates(subset=["Organisation Name"], keep="first")
            enriched_df = enriched_df.sort_values("Organisation Name")
            fs.write_csv(enriched_df, out_enriched)
        else:
            enriched_df = pd.DataFrame(columns=STAGE2_ENRICHED_COLUMNS)

        if fs.exists(out_unmatched):
            unmatched_df = fs.read_csv(out_unmatched).fillna("")
            unmatched_df = _coerce_output_columns(unmatched_df, STAGE2_UNMATCHED_COLUMNS)
            unmatched_df = unmatched_df.drop_duplicates(subset=["Organisation Name"], keep="first")
            unmatched_df = unmatched_df.sort_values("Organisation Name")
            fs.write_csv(unmatched_df, out_unmatched)
        else:
            unmatched_df = pd.DataFrame(columns=STAGE2_UNMATCHED_COLUMNS)

        if fs.exists(out_candidates):
            candidates_df = fs.read_csv(out_candidates).fillna("")
            candidates_df = _coerce_output_columns(candidates_df, STAGE2_CANDIDATES_COLUMNS)
            candidates_df["rank"] = pd.to_numeric(candidates_df["rank"], errors="coerce").fillna(0)
            candidates_df = candidates_df.drop_duplicates(
                subset=["Organisation Name", "rank", "candidate_company_number"], keep="first"
            )
            candidates_df = candidates_df.sort_values(["Organisation Name", "rank"])
            fs.write_csv(candidates_df, out_candidates)
        else:
            candidates_df = pd.DataFrame(columns=STAGE2_CANDIDATES_COLUMNS)

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
        remaining = max(0, total_stage1_orgs - processed_total)
        report = _build_resume_report(
            status=status,
            stage1_path=stage1_path,
            out_dir=out_dir,
            batch_size=batch_size_value,
            batch_start=batch_start,
            batch_count=batch_count,
            total_stage1_orgs=total_stage1_orgs,
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
        fs.write_json(report, out_resume_report)

    return {"enriched": out_enriched, "unmatched": out_unmatched, "candidates": out_candidates}
