"""Companies House domain logic for candidate scoring and mapping.

Usage example:
    from uk_sponsor_pipeline.domain.companies_house import score_candidates

    scored = score_candidates(
        org_norm="acme",
        town_norm="london",
        county_norm="greater london",
        items=search_items,
        query_used="Acme Ltd",
        similarity_fn=my_similarity,
    )
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..types import (
    CompanyProfile,
    SearchItem,
    TransformEnrichCandidateRow,
    TransformEnrichRow,
    TransformEnrichUnmatchedRow,
    TransformRegisterRow,
)

SimilarityFn = Callable[[str, str], float]
NormalizeFn = Callable[[str], str]


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


@dataclass
class CandidateScores:
    """Score components for a candidate before creating a MatchScore."""

    name_similarity: float
    locality_bonus: float
    region_bonus: float
    status_bonus: float

    @property
    def total(self) -> float:
        return min(
            1.0, self.name_similarity + self.locality_bonus + self.region_bonus + self.status_bonus
        )


def score_candidates(
    *,
    org_norm: str,
    town_norm: str,
    county_norm: str,
    items: list[SearchItem],
    query_used: str,
    similarity_fn: SimilarityFn,
    normalize_fn: NormalizeFn,
) -> list[CandidateMatch]:
    """Score candidate companies from search results."""
    out: list[CandidateMatch] = []
    for it in items:
        title = it.get("title") or ""
        number = it.get("company_number") or ""
        status = it.get("company_status") or ""
        addr = it.get("address") or {}
        loc = addr.get("locality") or ""
        region = addr.get("region") or ""
        postcode = addr.get("postal_code") or ""

        name_sim = similarity_fn(org_norm, title)

        locality_bonus = 0.0
        if town_norm and (town_norm in normalize_fn(loc) or town_norm in normalize_fn(region)):
            locality_bonus = 0.08

        region_bonus = 0.0
        if county_norm and county_norm in normalize_fn(region):
            region_bonus = 0.05

        status_bonus = 0.05 if (status or "").lower() == "active" else 0.0

        scores = CandidateScores(
            name_similarity=name_sim,
            locality_bonus=locality_bonus,
            region_bonus=region_bonus,
            status_bonus=status_bonus,
        )
        score = MatchScore(
            total=scores.total,
            name_similarity=scores.name_similarity,
            locality_bonus=scores.locality_bonus,
            region_bonus=scores.region_bonus,
            status_bonus=scores.status_bonus,
        )

        out.append(CandidateMatch(number, title, status, loc, region, postcode, score, query_used))

    out.sort(key=lambda x: x.score.total, reverse=True)
    return out


def build_candidate_row(
    *, org: str, cand: CandidateMatch, rank: int
) -> TransformEnrichCandidateRow:
    """Build a candidate audit row."""
    row: TransformEnrichCandidateRow = {
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
    return row


def build_unmatched_row(
    *, row: TransformRegisterRow, best_match: CandidateMatch | None
) -> TransformEnrichUnmatchedRow:
    """Build an unmatched row for audit."""
    out: TransformEnrichUnmatchedRow = {
        **row,
        "match_status": "unmatched",
        "best_candidate_score": round(best_match.score.total, 4) if best_match else "",
        "best_candidate_title": best_match.title if best_match else "",
        "best_candidate_company_number": best_match.company_number if best_match else "",
        "match_error": "",
    }
    return out


def build_profile_error_row(
    *,
    row: TransformRegisterRow,
    best_match: CandidateMatch,
    error: Exception,
) -> TransformEnrichUnmatchedRow:
    """Build a profile error row for audit."""
    out: TransformEnrichUnmatchedRow = {
        **row,
        "match_status": "profile_error",
        "best_candidate_score": round(best_match.score.total, 4),
        "best_candidate_title": best_match.title,
        "best_candidate_company_number": best_match.company_number,
        "match_error": str(error),
    }
    return out


def build_enriched_row(
    *,
    row: TransformRegisterRow,
    best_match: CandidateMatch,
    profile: CompanyProfile,
) -> TransformEnrichRow:
    """Build an enriched row from profile details."""
    sic = profile.get("sic_codes") or []
    ro = profile.get("registered_office_address") or {}

    out: TransformEnrichRow = {
        **row,
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
        "ch_sic_codes": ";".join(sic),
        "ch_address_locality": ro.get("locality") or best_match.locality,
        "ch_address_region": ro.get("region") or best_match.region,
        "ch_address_postcode": ro.get("postal_code") or best_match.postcode,
    }
    return out
