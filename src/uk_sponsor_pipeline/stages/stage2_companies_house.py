from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm

from ..utils.http import DiskCache, get_json

CH_BASE = "https://api.company-information.service.gov.uk"


def _normalize_name(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\b(limited|ltd|plc|llp|inc|incorporated|company|co|group|holdings)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _token_sort_key(s: str) -> str:
    toks = _normalize_name(s).split()
    toks.sort()
    return " ".join(toks)


def _simple_similarity(a: str, b: str) -> float:
    a0, b0 = _token_sort_key(a), _token_sort_key(b)
    if not a0 or not b0:
        return 0.0
    set_a, set_b = set(a0.split()), set(b0.split())
    jacc = len(set_a & set_b) / max(1, len(set_a | set_b))
    common = sum((min(a0.count(ch), b0.count(ch)) for ch in set(a0)))
    denom = max(len(a0), len(b0))
    char_overlap = common / denom if denom else 0.0
    return 0.6 * jacc + 0.4 * char_overlap


@dataclass
class CandidateScore:
    company_number: str
    title: str
    status: str
    locality: str
    region: str
    postcode: str
    score: float


def _auth_header(api_key: str) -> Dict[str, str]:
    token = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _score_candidates(org_name: str, town: str, county: str, items: List[dict]) -> List[CandidateScore]:
    org_norm = _normalize_name(org_name)
    town_norm = _normalize_name(town)
    county_norm = _normalize_name(county)

    out: List[CandidateScore] = []
    for it in items:
        title = it.get("title") or ""
        number = it.get("company_number") or ""
        status = it.get("company_status") or ""
        addr = it.get("address") or {}
        loc = addr.get("locality") or ""
        region = addr.get("region") or ""
        postcode = addr.get("postal_code") or ""

        base = _simple_similarity(org_norm, title)

        bonus = 0.0
        if town_norm and (town_norm in _normalize_name(loc) or town_norm in _normalize_name(region)):
            bonus += 0.08
        if county_norm and county_norm in _normalize_name(region):
            bonus += 0.05
        if (status or "").lower() == "active":
            bonus += 0.05

        out.append(CandidateScore(number, title, status, loc, region, postcode, min(1.0, base + bonus)))

    out.sort(key=lambda x: x.score, reverse=True)
    return out


def run_stage2(
    stage1_path: str | Path = "data/interim/stage1_skilled_worker_A_rated_aggregated_by_org.csv",
    out_dir: str | Path = "data/processed",
    cache_dir: str | Path = "data/cache/companies_house",
) -> Dict[str, Path]:
    """Stage 2: Enrich Stage 1 orgs with Companies House search + company profile."""
    load_dotenv()

    api_key = (os.getenv("CH_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Missing CH_API_KEY. Set it in .env or environment variables.")

    sleep_s = float(os.getenv("CH_SLEEP_SECONDS") or "0.2")
    min_score = float(os.getenv("CH_MIN_MATCH_SCORE") or "0.72")
    limit = int(os.getenv("CH_SEARCH_LIMIT") or "10")

    stage1_path = Path(stage1_path)
    out_dir = Path(out_dir)
    cache_dir = Path(cache_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(stage1_path, dtype=str).fillna("")
    for col in ["Organisation Name", "Town/City", "County"]:
        if col not in df.columns:
            raise RuntimeError(f"Stage 1 missing required column: {col}")

    session = requests.Session()
    session.headers.update(_auth_header(api_key))
    cache = DiskCache(cache_dir)

    enriched: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Companies House enrichment"):
        org = row["Organisation Name"]
        town = row.get("Town/City", "")
        county = row.get("County", "")

        search_url = f"{CH_BASE}/search/companies?q={requests.utils.quote(org)}&items_per_page={limit}"
        search_key = f"search:{org}:{limit}"
        try:
            search = get_json(session, search_url, cache, search_key, sleep_s=sleep_s)
        except Exception as e:
            r = dict(row)
            r["match_status"] = "error"
            r["match_error"] = str(e)
            unmatched.append(r)
            continue

        items = search.get("items") or []
        scored = _score_candidates(org, town, county, items)

        for rank, cand in enumerate(scored[:3], start=1):
            candidates.append({
                "Organisation Name": org,
                "rank": rank,
                "candidate_company_number": cand.company_number,
                "candidate_title": cand.title,
                "candidate_status": cand.status,
                "candidate_locality": cand.locality,
                "candidate_region": cand.region,
                "candidate_postcode": cand.postcode,
                "candidate_score": round(cand.score, 4),
            })

        best = scored[0] if scored else None
        if not best or best.score < min_score or not best.company_number:
            r = dict(row)
            r["match_status"] = "unmatched"
            r["best_candidate_score"] = round(best.score, 4) if best else ""
            r["best_candidate_title"] = best.title if best else ""
            r["best_candidate_company_number"] = best.company_number if best else ""
            unmatched.append(r)
            continue

        profile_url = f"{CH_BASE}/company/{best.company_number}"
        profile_key = f"profile:{best.company_number}"
        try:
            profile = get_json(session, profile_url, cache, profile_key, sleep_s=sleep_s)
        except Exception as e:
            r = dict(row)
            r["match_status"] = "profile_error"
            r["best_candidate_score"] = round(best.score, 4)
            r["best_candidate_title"] = best.title
            r["best_candidate_company_number"] = best.company_number
            r["match_error"] = str(e)
            unmatched.append(r)
            continue

        sic = profile.get("sic_codes") or []
        ro = profile.get("registered_office_address") or {}

        out = dict(row)
        out.update({
            "match_status": "matched",
            "match_score": round(best.score, 4),
            "ch_company_number": best.company_number,
            "ch_company_name": profile.get("company_name") or best.title,
            "ch_company_status": profile.get("company_status") or best.status,
            "ch_company_type": profile.get("type") or "",
            "ch_date_of_creation": profile.get("date_of_creation") or "",
            "ch_sic_codes": ";".join(sic) if isinstance(sic, list) else str(sic),
            "ch_address_locality": ro.get("locality") or best.locality,
            "ch_address_region": ro.get("region") or best.region,
            "ch_address_postcode": ro.get("postal_code") or best.postcode,
        })
        enriched.append(out)

    out_enriched = out_dir / "stage2_enriched_companies_house.csv"
    out_unmatched = out_dir / "stage2_unmatched.csv"
    out_candidates = out_dir / "stage2_candidates_top3.csv"

    pd.DataFrame(enriched).to_csv(out_enriched, index=False)
    pd.DataFrame(unmatched).to_csv(out_unmatched, index=False)
    pd.DataFrame(candidates).to_csv(out_candidates, index=False)

    return {"enriched": out_enriched, "unmatched": out_unmatched, "candidates": out_candidates}
