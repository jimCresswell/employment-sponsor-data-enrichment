from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from dotenv import load_dotenv


# A lightweight, transparent heuristic model that maps SIC codes to a 'tech-likelihood' signal.
# You can refine this mapping over time.
TECH_SIC_PREFIXES = {
    # Computer programming, consultancy, IT services
    "620": 0.95,
    "631": 0.80,  # data processing, hosting
    "582": 0.75,  # software publishing
    "611": 0.55,  # telecoms
    "612": 0.55,
    "619": 0.45,
    # R&D / engineering services (sometimes tech employers)
    "721": 0.40,
    "722": 0.25,
    "711": 0.30,
}

NEGATIVE_HINT_PREFIXES = {
    # Sectors that are commonly sponsors but rarely hire senior RN/FE/iOS engineers
    "861": -0.30,  # hospitals
    "862": -0.25,  # medical practice
    "869": -0.20,
    "871": -0.30,  # residential care
    "872": -0.30,
    "873": -0.30,
    "879": -0.30,
    "412": -0.20,  # construction
    "411": -0.15,
    "432": -0.15,
    "439": -0.15,
    "561": -0.25,  # restaurants
    "562": -0.25,
    "551": -0.20,  # hotels
}


def _parse_sic_list(s: str) -> List[str]:
    if not isinstance(s, str) or not s.strip():
        return []
    parts = [p.strip() for p in s.replace(",", ";").split(";")]
    return [p for p in parts if p]


def _score_from_sic(sics: List[str]) -> float:
    if not sics:
        return 0.15  # unknown: low-but-not-zero
    score = 0.15
    for sic in sics:
        pref3 = sic[:3]
        pref2 = sic[:2]
        # tech positive signals
        for pref, val in TECH_SIC_PREFIXES.items():
            if pref3.startswith(pref) or pref2.startswith(pref):
                score = max(score, val)
        # negative hints (reduce)
        for pref, val in NEGATIVE_HINT_PREFIXES.items():
            if pref3.startswith(pref) or pref2.startswith(pref):
                score += val
    return max(0.0, min(1.0, score))


def run_stage3(
    stage2_path: str | Path = "data/processed/stage2_enriched_companies_house.csv",
    out_dir: str | Path = "data/processed",
) -> Dict[str, Path]:
    """Stage 3: create tech-likelihood score + shortlist."""
    load_dotenv()
    threshold = float(os.getenv("TECH_SCORE_THRESHOLD") or "0.55")

    stage2_path = Path(stage2_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(stage2_path, dtype=str).fillna("")

    if "ch_sic_codes" not in df.columns:
        raise RuntimeError("Stage 2 output missing ch_sic_codes; run stage2 first.")

    sics = df["ch_sic_codes"].apply(_parse_sic_list)
    df["tech_score"] = sics.apply(_score_from_sic)

    # common sense exclusions: non-active companies
    if "ch_company_status" in df.columns:
        df["is_active"] = df["ch_company_status"].str.lower().eq("active")
    else:
        df["is_active"] = True

    scored_path = out_dir / "stage3_scored.csv"
    df.sort_values(["tech_score", "match_score"], ascending=False).to_csv(scored_path, index=False)

    shortlist = df[(df["tech_score"] >= threshold) & (df["is_active"])].copy()
    shortlist_path = out_dir / "stage3_shortlist_tech.csv"
    shortlist.sort_values(["tech_score", "match_score"], ascending=False).to_csv(shortlist_path, index=False)

    return {"scored": scored_path, "shortlist": shortlist_path}
