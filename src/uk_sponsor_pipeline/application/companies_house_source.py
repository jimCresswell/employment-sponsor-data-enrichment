"""Companies House data sources for enrichment.

Usage example:
    from uk_sponsor_pipeline.application.companies_house_source import (
        ApiCompaniesHouseSource,
        FileCompaniesHouseSource,
    )
    from uk_sponsor_pipeline.infrastructure.io.http import build_companies_house_client

    api_source = ApiCompaniesHouseSource(
        http_client=build_companies_house_client(...),
        search_limit=10,
    )

    file_source = FileCompaniesHouseSource(
        searches=[{"query": "Acme Ltd", "items": []}],
        profiles=[],
    )
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from ..config import PipelineConfig
from ..infrastructure.io.http import RequestsSession
from ..infrastructure.io.validation import (
    parse_companies_house_file,
    parse_companies_house_profile,
    parse_companies_house_search,
    validate_as,
    validate_json_as,
)
from ..io_contracts import CompaniesHouseProfileEntryIO, CompaniesHouseSearchEntryIO
from ..protocols import FileSystem, HttpClient, HttpSession
from ..types import CompanyProfile, SearchItem

CH_BASE = "https://api.company-information.service.gov.uk"


class CompaniesHouseSource(Protocol):
    """Abstract Companies House source for search and profile lookups."""

    def search(self, query: str) -> list[SearchItem]:
        """Return search candidates for a query."""
        ...

    def profile(self, company_number: str) -> CompanyProfile:
        """Return a company profile for a company number."""
        ...


@dataclass(frozen=True)
class ApiCompaniesHouseSource:
    """API-backed Companies House source using HttpClient."""

    http_client: HttpClient
    search_limit: int

    def search(self, query: str) -> list[SearchItem]:
        search_url = (
            f"{CH_BASE}/search/companies?q={quote(query)}&items_per_page={self.search_limit}"
        )
        cache_key = _cache_key("search", query, str(self.search_limit))
        payload = self.http_client.get_json(search_url, cache_key)
        items_io = parse_companies_house_search(payload)
        return validate_as(list[SearchItem], items_io)

    def profile(self, company_number: str) -> CompanyProfile:
        profile_url = f"{CH_BASE}/company/{company_number}"
        cache_key = _cache_key("profile", company_number)
        payload = self.http_client.get_json(profile_url, cache_key)
        profile_io = parse_companies_house_profile(payload)
        return validate_as(CompanyProfile, profile_io)


@dataclass(frozen=True)
class FileCompaniesHouseSource:
    """File-backed Companies House source."""

    searches: tuple[CompaniesHouseSearchEntryIO, ...]
    profiles: tuple[CompaniesHouseProfileEntryIO, ...]
    _search_map: dict[str, list[SearchItem]] = field(init=False, repr=False)
    _profile_map: dict[str, CompanyProfile] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_search_map", _build_search_map(self.searches))
        object.__setattr__(self, "_profile_map", _build_profile_map(self.profiles))

    def search(self, query: str) -> list[SearchItem]:
        key = _normalise_key(query)
        return self._search_map.get(key, [])

    def profile(self, company_number: str) -> CompanyProfile:
        key = _normalise_key(company_number)
        profile = self._profile_map.get(key)
        if profile is None:
            raise RuntimeError(
                "Companies House file source is missing a profile for company number "
                f"'{company_number}'."
            )
        return profile


def build_companies_house_source(
    *,
    config: PipelineConfig,
    fs: FileSystem,
    http_client: HttpClient | None,
    http_session: HttpSession | None,
) -> CompaniesHouseSource:
    if config.ch_source_type == "api":
        if http_client is None:
            raise RuntimeError("API source requires an HTTP client.")
        return ApiCompaniesHouseSource(http_client=http_client, search_limit=config.ch_search_limit)

    if config.ch_source_type == "file":
        payload = _load_file_payload(
            config.ch_source_path,
            fs=fs,
            http_session=http_session,
            timeout_seconds=config.ch_timeout_seconds,
        )
        parsed = parse_companies_house_file(payload)
        return FileCompaniesHouseSource(
            searches=tuple(parsed["searches"]),
            profiles=tuple(parsed["profiles"]),
        )

    raise ValueError("CH_SOURCE_TYPE must be 'api' or 'file'.")


def _load_file_payload(
    path: str,
    *,
    fs: FileSystem,
    http_session: HttpSession | None,
    timeout_seconds: float,
) -> dict[str, object]:
    if not path:
        raise RuntimeError("CH_SOURCE_PATH is required when CH_SOURCE_TYPE is 'file'.")
    if path.startswith("http://") or path.startswith("https://"):
        session = http_session or RequestsSession()
        content = session.get_text(path, timeout_seconds=timeout_seconds)
        return validate_json_as(dict[str, object], content)
    file_path = Path(path)
    return fs.read_json(file_path)


def _normalise_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _normalise_for_cache(value: str) -> str:
    return re.sub(r"\s+", "_", value.strip().lower())


def _cache_key(prefix: str, *parts: str) -> str:
    normalized = "_".join(_normalise_for_cache(p) for p in parts if p)
    h = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"{prefix}:{h}"


def _build_search_map(
    searches: Iterable[CompaniesHouseSearchEntryIO],
) -> dict[str, list[SearchItem]]:
    mapping: dict[str, list[SearchItem]] = {}
    for entry in searches:
        key = _normalise_key(entry["query"])
        items = validate_as(list[SearchItem], entry["items"])
        mapping[key] = items
    return mapping


def _build_profile_map(
    profiles: Iterable[CompaniesHouseProfileEntryIO],
) -> dict[str, CompanyProfile]:
    mapping: dict[str, CompanyProfile] = {}
    for entry in profiles:
        key = _normalise_key(entry["company_number"])
        profile = validate_as(CompanyProfile, entry["profile"])
        mapping[key] = profile
    return mapping
