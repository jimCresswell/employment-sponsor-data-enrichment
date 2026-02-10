"""Typed parsing and validation for pipeline config files."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from .exceptions import ConfigFileNotFoundError, ConfigFileParseError, ConfigFileValidationError
from .protocols import FileSystem

_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PipelineConfigFile:
    """Validated pipeline config values loaded from a TOML file."""

    ch_source_type: str | None = None
    snapshot_root: str | None = None
    sponsor_clean_path: str | None = None
    ch_clean_path: str | None = None
    ch_token_index_dir: str | None = None
    ch_file_max_candidates: int | None = None
    ch_batch_size: int | None = None
    ch_min_match_score: float | None = None
    ch_search_limit: int | None = None
    tech_score_threshold: float | None = None
    sector_profile_path: str | None = None
    sector_name: str | None = None
    geo_filter_region: str | None = None
    geo_filter_postcodes: tuple[str, ...] | None = None
    location_aliases_path: str | None = None


class _PipelineSectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ch_source_type: str | None = None
    snapshot_root: str | None = None
    sponsor_clean_path: str | None = None
    ch_clean_path: str | None = None
    ch_token_index_dir: str | None = None
    ch_file_max_candidates: int | None = None
    ch_batch_size: int | None = None
    ch_min_match_score: float | None = None
    ch_search_limit: int | None = None
    tech_score_threshold: float | None = None
    sector_profile_path: str | None = None
    sector_name: str | None = None
    geo_filter_region: str | None = None
    geo_filter_postcodes: tuple[str, ...] | None = None
    location_aliases_path: str | None = None

    @field_validator("ch_source_type")
    @classmethod
    def _validate_source_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        source = value.strip().lower()
        if source not in {"api", "file"}:
            raise ValueError
        return source

    @field_validator(
        "snapshot_root",
        "sponsor_clean_path",
        "ch_clean_path",
        "ch_token_index_dir",
        "sector_profile_path",
        "sector_name",
        "location_aliases_path",
    )
    @classmethod
    def _validate_non_empty_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError
        return text

    @field_validator("geo_filter_region")
    @classmethod
    def _validate_geo_filter_region(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text or "," in text:
            raise ValueError
        return text

    @field_validator("geo_filter_postcodes")
    @classmethod
    def _validate_geo_filter_postcodes(
        cls, value: tuple[str, ...] | None
    ) -> tuple[str, ...] | None:
        if value is None:
            return None
        cleaned = tuple(item.strip() for item in value if item.strip())
        if not cleaned:
            raise ValueError
        return cleaned

    @field_validator("ch_file_max_candidates", "ch_batch_size", "ch_search_limit")
    @classmethod
    def _validate_positive_int(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value < 1:
            raise ValueError
        return value

    @field_validator("ch_min_match_score", "tech_score_threshold")
    @classmethod
    def _validate_score_range(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if value < 0.0 or value > 1.0:
            raise ValueError
        return value


class _ConfigFileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int
    pipeline: _PipelineSectionModel

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != _SCHEMA_VERSION:
            raise ValueError
        return value


def _format_validation_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    location = ".".join(str(part) for part in first.get("loc", ("<root>",)))
    message = str(first.get("msg", "invalid value"))
    return f"{location}: {message}"


def load_pipeline_config_file(*, path: Path, fs: FileSystem) -> PipelineConfigFile:
    """Load and validate a pipeline TOML config file."""
    if not fs.exists(path):
        raise ConfigFileNotFoundError(str(path))

    raw_payload = fs.read_text(path)
    try:
        payload: object = tomllib.loads(raw_payload)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigFileParseError(str(path), str(exc)) from exc

    try:
        model = _ConfigFileModel.model_validate(payload)
    except ValidationError as exc:
        raise ConfigFileValidationError(str(path), _format_validation_error(exc)) from exc

    section = model.pipeline
    return PipelineConfigFile(
        ch_source_type=section.ch_source_type,
        snapshot_root=section.snapshot_root,
        sponsor_clean_path=section.sponsor_clean_path,
        ch_clean_path=section.ch_clean_path,
        ch_token_index_dir=section.ch_token_index_dir,
        ch_file_max_candidates=section.ch_file_max_candidates,
        ch_batch_size=section.ch_batch_size,
        ch_min_match_score=section.ch_min_match_score,
        ch_search_limit=section.ch_search_limit,
        tech_score_threshold=section.tech_score_threshold,
        sector_profile_path=section.sector_profile_path,
        sector_name=section.sector_name,
        geo_filter_region=section.geo_filter_region,
        geo_filter_postcodes=section.geo_filter_postcodes,
        location_aliases_path=section.location_aliases_path,
    )
