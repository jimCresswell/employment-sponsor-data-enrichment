"""Domain model for configurable scoring profiles."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class KeywordWeights:
    """Keyword scoring weights and caps."""

    positive_per_match: float
    positive_cap: float
    negative_per_match: float
    negative_cap: float


@dataclass(frozen=True)
class CompanyStatusScores:
    """Status-based scoring values."""

    active: float
    inactive: float


@dataclass(frozen=True)
class CompanyAgeBand:
    """A score assigned when a company is at least ``min_years`` old."""

    min_years: float
    score: float


@dataclass(frozen=True)
class CompanyAgeScores:
    """Age-scoring defaults and threshold bands."""

    unknown: float
    bands: tuple[CompanyAgeBand, ...]


@dataclass(frozen=True)
class BucketThresholds:
    """Thresholds for role-fit buckets."""

    strong: float
    possible: float


@dataclass(frozen=True)
class ScoringProfile:
    """A full scoring profile for one job-type focused ranking strategy."""

    name: str
    job_type: str
    sector_signals: MappingProxyType[str, float]
    location_signals: MappingProxyType[str, float]
    size_signals: MappingProxyType[str, float]
    sic_positive_prefixes: MappingProxyType[str, float]
    sic_negative_prefixes: MappingProxyType[str, float]
    keyword_positive: tuple[str, ...]
    keyword_negative: tuple[str, ...]
    keyword_weights: KeywordWeights
    company_status_scores: CompanyStatusScores
    company_age_scores: CompanyAgeScores
    company_type_weights: MappingProxyType[str, float]
    bucket_thresholds: BucketThresholds


@dataclass(frozen=True)
class ScoringProfileCatalog:
    """Named scoring profiles bundled in a single schema version."""

    schema_version: int
    default_profile: str
    profiles: tuple[ScoringProfile, ...]
