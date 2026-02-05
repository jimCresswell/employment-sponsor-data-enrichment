"""Companies House data sources for enrichment.

Usage example:
    from uk_sponsor_pipeline.application.companies_house_source import (
        ApiCompaniesHouseSource,
        FileCompaniesHouseSource,
    )
    http_client = ...  # Injected HttpClient from the CLI/composition root

    api_source = ApiCompaniesHouseSource(http_client=http_client, search_limit=10)

    file_source = FileCompaniesHouseSource(
        fs=fs,
        token_index={"acme": ["01234567"]},
        profile_dir=Path("data/cache/snapshots/companies_house/2026-02-01"),
        max_candidates=500,
    )
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, override
from urllib.parse import quote

from ..config import PipelineConfig
from ..exceptions import (
    CompaniesHouseFileProfileMissingError,
    CsvSchemaDecodeError,
    CsvSchemaMissingColumnsError,
    DependencyMissingError,
    InvalidSourceTypeError,
    MissingSnapshotPathError,
    SnapshotArtefactMissingError,
)
from ..io_validation import parse_companies_house_profile, parse_companies_house_search, validate_as
from ..protocols import FileSystem, HttpClient
from ..types import CompaniesHouseCleanRow, CompanyProfile, SearchItem
from .companies_house_bulk import CANONICAL_HEADERS_V1
from .companies_house_index import bucket_for_token, tokenise_company_name

CH_BASE = "https://api.company-information.service.gov.uk"
_INDEX_HEADERS: tuple[str, str] = ("token", "company_number")


def _empty_profile_cache() -> dict[str, CompanyProfile]:
    return {}


def _empty_search_cache() -> dict[str, SearchItem]:
    return {}


class CompaniesHouseSource(Protocol):
    """Abstract Companies House source for search and profile lookups."""

    def search(self, query: str) -> list[SearchItem]:
        """Return search candidates for a query."""
        ...

    def profile(self, company_number: str) -> CompanyProfile:
        """Return a company profile for a company number."""
        ...


@dataclass(frozen=True)
class ApiCompaniesHouseSource(CompaniesHouseSource):
    """API-backed Companies House source using HttpClient."""

    http_client: HttpClient
    search_limit: int

    @override
    def search(self, query: str) -> list[SearchItem]:
        search_url = (
            f"{CH_BASE}/search/companies?q={quote(query)}&items_per_page={self.search_limit}"
        )
        cache_key = _cache_key("search", query, str(self.search_limit))
        payload = self.http_client.get_json(search_url, cache_key)
        items_io = parse_companies_house_search(payload)
        return validate_as(list[SearchItem], items_io)

    @override
    def profile(self, company_number: str) -> CompanyProfile:
        profile_url = f"{CH_BASE}/company/{company_number}"
        cache_key = _cache_key("profile", company_number)
        payload = self.http_client.get_json(profile_url, cache_key)
        profile_io = parse_companies_house_profile(payload)
        return validate_as(CompanyProfile, profile_io)


@dataclass(frozen=True)
class FileCompaniesHouseSource(CompaniesHouseSource):
    """File-backed Companies House source using snapshot artefacts."""

    fs: FileSystem
    token_index: dict[str, list[str]]
    profile_dir: Path
    max_candidates: int
    _profile_cache: dict[str, CompanyProfile] = field(
        default_factory=_empty_profile_cache, init=False, repr=False
    )
    _search_cache: dict[str, SearchItem] = field(
        default_factory=_empty_search_cache, init=False, repr=False
    )

    @override
    def search(self, query: str) -> list[SearchItem]:
        tokens = tokenise_company_name(query)
        if not tokens:
            return []
        candidates = _candidate_company_numbers(
            tokens=tokens,
            token_index=self.token_index,
            max_candidates=self.max_candidates,
        )
        if not candidates:
            return []
        self._load_profiles_for_numbers(candidates)
        out: list[SearchItem] = []
        for company_number in candidates:
            item = self._search_cache.get(company_number)
            if item is not None:
                out.append(item)
        return out

    @override
    def profile(self, company_number: str) -> CompanyProfile:
        key = company_number.strip()
        if key not in self._profile_cache:
            self._load_profiles_for_numbers([key])
        profile = self._profile_cache.get(key)
        if profile is None:
            raise CompaniesHouseFileProfileMissingError(company_number)
        return profile

    def _load_profiles_for_numbers(self, company_numbers: Iterable[str]) -> None:
        missing = [number for number in company_numbers if number not in self._profile_cache]
        if not missing:
            return
        bucket_map: dict[str, set[str]] = {}
        for number in missing:
            bucket = bucket_for_token(number)
            bucket_map.setdefault(bucket, set()).add(number)
        for bucket, numbers in bucket_map.items():
            path = self.profile_dir / f"profiles_{bucket}.csv"
            if not self.fs.exists(path):
                raise SnapshotArtefactMissingError(str(path))
            text = self.fs.read_text(path)
            reader = csv.DictReader(io.StringIO(text))
            if reader.fieldnames is None:
                raise CsvSchemaDecodeError()
            _validate_profile_headers([header.strip() for header in reader.fieldnames if header])
            for row in reader:
                company_number = (row.get("company_number") or "").strip()
                if not company_number or company_number not in numbers:
                    continue
                clean_row = _coerce_clean_row(row)
                self._store_profile(clean_row)

    def _store_profile(self, row: CompaniesHouseCleanRow) -> None:
        company_number = row["company_number"].strip()
        if not company_number:
            return
        self._profile_cache[company_number] = _build_company_profile(row)
        self._search_cache[company_number] = _build_search_item(row)


def build_companies_house_source(
    *,
    config: PipelineConfig,
    fs: FileSystem,
    http_client: HttpClient | None,
    token_set: set[str] | None = None,
) -> CompaniesHouseSource:
    if config.ch_source_type == "api":
        if http_client is None:
            raise DependencyMissingError("HttpClient", reason="When CH_SOURCE_TYPE is 'api'.")
        return ApiCompaniesHouseSource(http_client=http_client, search_limit=config.ch_search_limit)

    if config.ch_source_type == "file":
        if not config.ch_clean_path:
            raise MissingSnapshotPathError("CH_CLEAN_PATH")
        if not config.ch_token_index_dir:
            raise MissingSnapshotPathError("CH_TOKEN_INDEX_DIR")
        clean_path = Path(config.ch_clean_path)
        if not fs.exists(clean_path):
            raise SnapshotArtefactMissingError(str(clean_path))
        index_dir = Path(config.ch_token_index_dir)
        token_index = _load_token_index_map(
            token_set=token_set or set(),
            index_dir=index_dir,
            fs=fs,
        )
        return FileCompaniesHouseSource(
            fs=fs,
            token_index=token_index,
            profile_dir=index_dir,
            max_candidates=config.ch_file_max_candidates,
        )

    raise InvalidSourceTypeError()


def _candidate_company_numbers(
    *,
    tokens: list[str],
    token_index: dict[str, list[str]],
    max_candidates: int,
) -> list[str]:
    counts: dict[str, int] = {}
    for token in tokens:
        for company_number in token_index.get(token, []):
            counts[company_number] = counts.get(company_number, 0) + 1
    if not counts:
        return []
    min_hits = 2 if len(tokens) >= 2 else 1
    candidates = [(number, hits) for number, hits in counts.items() if hits >= min_hits]
    if not candidates:
        return []
    candidates.sort(key=lambda item: (-item[1], item[0]))
    if len(candidates) > max_candidates:
        candidates = candidates[:max_candidates]
    return [number for number, _ in candidates]


def _load_token_index_map(
    *,
    token_set: set[str],
    index_dir: Path,
    fs: FileSystem,
) -> dict[str, list[str]]:
    token_index: dict[str, list[str]] = {}
    if not token_set:
        return token_index
    buckets = {bucket_for_token(token) for token in token_set}
    seen: dict[str, set[str]] = {}
    for bucket in sorted(buckets):
        path = index_dir / f"index_tokens_{bucket}.csv"
        if not fs.exists(path):
            raise SnapshotArtefactMissingError(str(path))
        text = fs.read_text(path)
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise CsvSchemaDecodeError()
        _validate_index_headers([header.strip() for header in reader.fieldnames if header])
        for row in reader:
            token = (row.get("token") or "").strip()
            if token not in token_set:
                continue
            company_number = (row.get("company_number") or "").strip()
            if not company_number:
                continue
            seen.setdefault(token, set())
            if company_number in seen[token]:
                continue
            token_index.setdefault(token, []).append(company_number)
            seen[token].add(company_number)
    return token_index


def _validate_index_headers(headers: list[str]) -> None:
    missing = [name for name in _INDEX_HEADERS if name not in headers]
    if missing:
        raise CsvSchemaMissingColumnsError(missing)


def _validate_profile_headers(headers: list[str]) -> None:
    missing = [name for name in CANONICAL_HEADERS_V1 if name not in headers]
    if missing:
        raise CsvSchemaMissingColumnsError(missing)


def _coerce_clean_row(raw: Mapping[str, str | None]) -> CompaniesHouseCleanRow:
    return {
        "company_number": (raw.get("company_number") or "").strip(),
        "company_name": (raw.get("company_name") or "").strip(),
        "company_status": (raw.get("company_status") or "").strip(),
        "company_type": (raw.get("company_type") or "").strip(),
        "date_of_creation": (raw.get("date_of_creation") or "").strip(),
        "sic_codes": (raw.get("sic_codes") or "").strip(),
        "address_locality": (raw.get("address_locality") or "").strip(),
        "address_region": (raw.get("address_region") or "").strip(),
        "address_postcode": (raw.get("address_postcode") or "").strip(),
        "uri": (raw.get("uri") or "").strip(),
    }


def _build_search_item(row: CompaniesHouseCleanRow) -> SearchItem:
    return {
        "title": row["company_name"],
        "company_number": row["company_number"],
        "company_status": row["company_status"],
        "address": {
            "locality": row["address_locality"],
            "region": row["address_region"],
            "postal_code": row["address_postcode"],
        },
    }


def _build_company_profile(row: CompaniesHouseCleanRow) -> CompanyProfile:
    sic_raw = row["sic_codes"]
    sic_codes = [code for code in sic_raw.split(";") if code]
    return {
        "company_name": row["company_name"],
        "company_status": row["company_status"],
        "type": row["company_type"],
        "date_of_creation": row["date_of_creation"],
        "sic_codes": sic_codes,
        "registered_office_address": {
            "locality": row["address_locality"],
            "region": row["address_region"],
            "postal_code": row["address_postcode"],
        },
    }


def _normalise_for_cache(value: str) -> str:
    return re.sub(r"\s+", "_", value.strip().lower())


def _cache_key(prefix: str, *parts: str) -> str:
    normalised = "_".join(_normalise_for_cache(p) for p in parts if p)
    h = hashlib.sha256(normalised.encode()).hexdigest()[:16]
    return f"{prefix}:{h}"
