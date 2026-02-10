"""Loading and strict validation for scoring profile catalogues."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from ..domain.scoring_profiles import (
    BucketThresholds,
    CompanyAgeBand,
    CompanyAgeScores,
    CompanyStatusScores,
    KeywordWeights,
    ScoringProfile,
    ScoringProfileCatalog,
)
from ..exceptions import (
    ScoringProfileFileNotFoundError,
    ScoringProfileSelectionError,
    ScoringProfileValidationError,
)
from ..protocols import FileSystem

_SCHEMA_VERSION = 1


class _KeywordWeightsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    positive_per_match: float
    positive_cap: float
    negative_per_match: float
    negative_cap: float

    @field_validator("positive_per_match", "positive_cap", "negative_per_match", "negative_cap")
    @classmethod
    def _validate_range(cls, value: float) -> float:
        if value < 0.0 or value > 1.0:
            raise ValueError
        return value


class _CompanyStatusScoresModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    active: float
    inactive: float

    @field_validator("active", "inactive")
    @classmethod
    def _validate_range(cls, value: float) -> float:
        if value < -1.0 or value > 1.0:
            raise ValueError
        return value


class _CompanyAgeBandModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_years: float
    score: float

    @field_validator("min_years")
    @classmethod
    def _validate_min_years(cls, value: float) -> float:
        if value < 0.0:
            raise ValueError
        return value

    @field_validator("score")
    @classmethod
    def _validate_score(cls, value: float) -> float:
        if value < -1.0 or value > 1.0:
            raise ValueError
        return value


class _CompanyAgeScoresModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    unknown: float
    bands: tuple[_CompanyAgeBandModel, ...]

    @field_validator("unknown")
    @classmethod
    def _validate_unknown(cls, value: float) -> float:
        if value < -1.0 or value > 1.0:
            raise ValueError
        return value

    @model_validator(mode="after")
    def _validate_bands(self) -> _CompanyAgeScoresModel:
        if not self.bands:
            raise ValueError
        min_years = [band.min_years for band in self.bands]
        if sorted(min_years, reverse=True) != list(min_years):
            raise ValueError
        return self


class _BucketThresholdsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strong: float
    possible: float

    @field_validator("strong", "possible")
    @classmethod
    def _validate_range(cls, value: float) -> float:
        if value < 0.0 or value > 1.0:
            raise ValueError
        return value

    @model_validator(mode="after")
    def _validate_order(self) -> _BucketThresholdsModel:
        if self.strong <= self.possible:
            raise ValueError
        return self


class _ScoringProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    job_type: str
    sector_signals: dict[str, float]
    location_signals: dict[str, float]
    size_signals: dict[str, float]
    sic_positive_prefixes: dict[str, float]
    sic_negative_prefixes: dict[str, float]
    keyword_positive: tuple[str, ...]
    keyword_negative: tuple[str, ...]
    keyword_weights: _KeywordWeightsModel
    company_status_scores: _CompanyStatusScoresModel
    company_age_scores: _CompanyAgeScoresModel
    company_type_weights: dict[str, float]
    bucket_thresholds: _BucketThresholdsModel

    @field_validator("name", "job_type")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError
        return text

    @field_validator("keyword_positive", "keyword_negative")
    @classmethod
    def _validate_keywords(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not keyword.strip() for keyword in value):
            raise ValueError
        return tuple(keyword.strip().lower() for keyword in value)

    @field_validator(
        "sector_signals",
        "location_signals",
        "size_signals",
        "sic_positive_prefixes",
        "sic_negative_prefixes",
        "company_type_weights",
    )
    @classmethod
    def _validate_signal_map(cls, value: dict[str, float]) -> dict[str, float]:
        cleaned: dict[str, float] = {}
        for key, score in value.items():
            key_text = key.strip()
            if not key_text:
                raise ValueError
            if score < -1.0 or score > 1.0:
                raise ValueError
            cleaned[key_text] = score
        return cleaned


class _ScoringProfileCatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int
    default_profile: str
    profiles: tuple[_ScoringProfileModel, ...]

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != _SCHEMA_VERSION:
            raise ValueError
        return value

    @field_validator("default_profile")
    @classmethod
    def _validate_default_profile(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError
        return text

    @model_validator(mode="after")
    def _validate_profiles(self) -> _ScoringProfileCatalogModel:
        if not self.profiles:
            raise ValueError
        names = [profile.name for profile in self.profiles]
        if len(set(names)) != len(names):
            raise ValueError
        if self.default_profile not in set(names):
            raise ValueError
        return self


def _format_validation_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    location = ".".join(str(part) for part in first.get("loc", ("<root>",)))
    message = str(first.get("msg", "invalid value"))
    return f"{location}: {message}"


def _to_readonly_mapping(values: Mapping[str, float]) -> MappingProxyType[str, float]:
    return MappingProxyType(dict(values))


def _to_domain_profile(model: _ScoringProfileModel) -> ScoringProfile:
    return ScoringProfile(
        name=model.name,
        job_type=model.job_type,
        sector_signals=_to_readonly_mapping(model.sector_signals),
        location_signals=_to_readonly_mapping(model.location_signals),
        size_signals=_to_readonly_mapping(model.size_signals),
        sic_positive_prefixes=_to_readonly_mapping(model.sic_positive_prefixes),
        sic_negative_prefixes=_to_readonly_mapping(model.sic_negative_prefixes),
        keyword_positive=model.keyword_positive,
        keyword_negative=model.keyword_negative,
        keyword_weights=KeywordWeights(
            positive_per_match=model.keyword_weights.positive_per_match,
            positive_cap=model.keyword_weights.positive_cap,
            negative_per_match=model.keyword_weights.negative_per_match,
            negative_cap=model.keyword_weights.negative_cap,
        ),
        company_status_scores=CompanyStatusScores(
            active=model.company_status_scores.active,
            inactive=model.company_status_scores.inactive,
        ),
        company_age_scores=CompanyAgeScores(
            unknown=model.company_age_scores.unknown,
            bands=tuple(
                CompanyAgeBand(min_years=band.min_years, score=band.score)
                for band in model.company_age_scores.bands
            ),
        ),
        company_type_weights=_to_readonly_mapping(model.company_type_weights),
        bucket_thresholds=BucketThresholds(
            strong=model.bucket_thresholds.strong,
            possible=model.bucket_thresholds.possible,
        ),
    )


def load_scoring_profile_catalog(*, path: Path, fs: FileSystem) -> ScoringProfileCatalog:
    """Load and validate a scoring profile catalogue from JSON."""
    if not fs.exists(path):
        raise ScoringProfileFileNotFoundError(str(path))

    payload = fs.read_text(path)
    try:
        model = _ScoringProfileCatalogModel.model_validate_json(payload)
    except ValidationError as exc:
        raise ScoringProfileValidationError(str(path), _format_validation_error(exc)) from exc

    return ScoringProfileCatalog(
        schema_version=model.schema_version,
        default_profile=model.default_profile,
        profiles=tuple(_to_domain_profile(profile) for profile in model.profiles),
    )


def resolve_scoring_profile(
    catalog: ScoringProfileCatalog,
    profile_name: str | None = None,
) -> ScoringProfile:
    """Resolve one profile by name, defaulting to the catalogue default profile."""
    target = (profile_name or catalog.default_profile).strip()
    if not target:
        target = catalog.default_profile

    for profile in catalog.profiles:
        if profile.name == target:
            return profile

    available = tuple(sorted(profile.name for profile in catalog.profiles))
    raise ScoringProfileSelectionError(target, available)
