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

import base64
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv
from rich import print as rprint
from tqdm import tqdm

from ..config import PipelineConfig
from ..exceptions import AuthenticationError, CircuitBreakerOpen, RateLimitError
from ..infrastructure import CachedHttpClient, CircuitBreaker, DiskCache, RateLimiter
from ..normalization import generate_query_variants, normalize_org_name
from ..protocols import HttpClient

CH_BASE = "https://api.company-information.service.gov.uk"


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
    org_name: str, town: str, county: str, items: list[dict], query_used: str
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


def _auth_header(api_key: str) -> dict[str, str]:
    """Create HTTP Basic Auth header for Companies House API."""
    token = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def run_stage2(
    stage1_path: str | Path = "data/interim/stage1_skilled_worker_A_rated_aggregated_by_org.csv",
    out_dir: str | Path = "data/processed",
    cache_dir: str | Path = "data/cache/companies_house",
    config: PipelineConfig | None = None,
    http_client: HttpClient | None = None,
    resume: bool = True,
) -> dict[str, Path]:
    """Stage 2: Enrich Stage 1 orgs with Companies House search + profile.

    Args:
        stage1_path: Path to Stage 1 output CSV.
        out_dir: Directory for output files.
        cache_dir: Directory for API response cache.
        config: Pipeline configuration (loads from env if None).
        http_client: HTTP client (creates default if None).
        resume: If True, skip already-processed organizations.

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

    stage1_path = Path(stage1_path)
    out_dir = Path(out_dir)
    cache_dir = Path(cache_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Output paths
    out_enriched = out_dir / "stage2_enriched_companies_house.csv"
    out_unmatched = out_dir / "stage2_unmatched.csv"
    out_candidates = out_dir / "stage2_candidates_top3.csv"

    # Load input
    df = pd.read_csv(stage1_path, dtype=str).fillna("")
    required_cols = ["Organisation Name", "Town/City", "County"]
    for col in required_cols:
        if col not in df.columns:
            raise RuntimeError(f"Stage 1 missing required column: {col}")

    # Load existing results for resumability
    already_processed: set[str] = set()
    existing_enriched: list[dict[str, Any]] = []
    existing_unmatched: list[dict[str, Any]] = []
    existing_candidates: list[dict[str, Any]] = []

    if resume and out_enriched.exists():
        existing_df = pd.read_csv(out_enriched, dtype=str).fillna("")
        already_processed.update(existing_df["Organisation Name"].tolist())
        existing_enriched = existing_df.to_dict("records")
        rprint(f"[cyan]Resuming:[/cyan] {len(already_processed)} orgs already processed")

    if resume and out_unmatched.exists():
        existing_unmatched_df = pd.read_csv(out_unmatched, dtype=str).fillna("")
        already_processed.update(existing_unmatched_df["Organisation Name"].tolist())
        existing_unmatched = existing_unmatched_df.to_dict("records")

    if resume and out_candidates.exists():
        existing_candidates = pd.read_csv(out_candidates, dtype=str).fillna("").to_dict("records")

    # Set up HTTP client with circuit breaker
    if http_client is None:
        session = requests.Session()
        session.headers.update(_auth_header(config.ch_api_key))
        cache = DiskCache(cache_dir)
        rate_limiter = RateLimiter(max_rpm=config.ch_max_rpm, min_delay_seconds=config.ch_sleep_seconds)
        circuit_breaker = CircuitBreaker(threshold=5)  # Stop after 5 consecutive failures
        http_client = CachedHttpClient(session, cache, rate_limiter, circuit_breaker, config.ch_sleep_seconds)

    # Process organizations
    enriched: list[dict[str, Any]] = list(existing_enriched)
    unmatched: list[dict[str, Any]] = list(existing_unmatched)
    candidates: list[dict[str, Any]] = list(existing_candidates)

    to_process = [row for _, row in df.iterrows() if row["Organisation Name"] not in already_processed]
    rprint(f"[cyan]Processing:[/cyan] {len(to_process)} organizations")

    for _, row in tqdm(enumerate(to_process), total=len(to_process), desc="Companies House enrichment"):
        row = to_process[_]
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
        for query in query_variants:
            search_url = f"{CH_BASE}/search/companies?q={requests.utils.quote(query)}&items_per_page={config.ch_search_limit}"
            cache_key = _cache_key("search", query, str(config.ch_search_limit))

            try:
                search = http_client.get_json(search_url, cache_key)
            except (AuthenticationError, CircuitBreakerOpen, RateLimitError):
                # Fatal errors - re-raise immediately to stop pipeline
                raise
            except requests.HTTPError as e:
                # Non-fatal HTTP error - log and try next variant
                rprint(f"[yellow]Search error for '{query}': {e}[/yellow]")
                continue
            except Exception as e:
                # Other errors - log and try next variant
                rprint(f"[yellow]Search error for '{query}': {e}[/yellow]")
                continue

            items = search.get("items") or []
            scored = _score_candidates(org, town, county, items, query)
            all_candidates.extend(scored)

            # Stop early if we found a high-confidence match
            if scored and scored[0].score.total >= 0.85:
                best_match = scored[0]
                break

        # If no high-confidence match, take the best overall
        if not best_match and all_candidates:
            all_candidates.sort(key=lambda x: x.score.total, reverse=True)
            best_match = all_candidates[0]

        # Record top 3 candidates for audit
        for rank, cand in enumerate(all_candidates[:3], start=1):
            candidates.append({
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
            })

        # Check if match is good enough
        if not best_match or best_match.score.total < config.ch_min_match_score or not best_match.company_number:
            r = dict(row)
            r["match_status"] = "unmatched"
            r["best_candidate_score"] = round(best_match.score.total, 4) if best_match else ""
            r["best_candidate_title"] = best_match.title if best_match else ""
            r["best_candidate_company_number"] = best_match.company_number if best_match else ""
            unmatched.append(r)
            continue

        # Fetch company profile
        profile_url = f"{CH_BASE}/company/{best_match.company_number}"
        profile_key = _cache_key("profile", best_match.company_number)

        try:
            profile = http_client.get_json(profile_url, profile_key)
        except (AuthenticationError, CircuitBreakerOpen, RateLimitError):
            # Fatal errors - re-raise immediately
            raise
        except Exception as e:
            r = dict(row)
            r["match_status"] = "profile_error"
            r["best_candidate_score"] = round(best_match.score.total, 4)
            r["best_candidate_title"] = best_match.title
            r["best_candidate_company_number"] = best_match.company_number
            r["match_error"] = str(e)
            unmatched.append(r)
            continue

        # Extract profile data
        sic = profile.get("sic_codes") or []
        ro = profile.get("registered_office_address") or {}

        out = dict(row)
        out.update({
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
        })
        enriched.append(out)

    # Write outputs
    pd.DataFrame(enriched).to_csv(out_enriched, index=False)
    pd.DataFrame(unmatched).to_csv(out_unmatched, index=False)
    pd.DataFrame(candidates).to_csv(out_candidates, index=False)

    rprint(f"[green]✓ Enriched:[/green] {len(enriched)} matched, {len(unmatched)} unmatched")

    return {"enriched": out_enriched, "unmatched": out_unmatched, "candidates": out_candidates}
