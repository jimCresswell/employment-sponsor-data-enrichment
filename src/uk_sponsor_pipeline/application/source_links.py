"""Source link discovery helpers for refresh commands."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import override
from urllib.parse import urljoin

from ..exceptions import (
    CompaniesHouseZipLinkAmbiguousError,
    CompaniesHouseZipLinkNotFoundError,
    CsvLinkAmbiguousError,
    CsvLinkNotFoundError,
)
from ..protocols import HttpSession

SPONSOR_SOURCE_PAGE_URL = (
    "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"
)
COMPANIES_HOUSE_SOURCE_PAGE_URL = "https://download.companieshouse.gov.uk/en_output.html"

_CSV_PATTERN = re.compile(r"\.csv($|\\?)", re.IGNORECASE)
_ZIP_PATTERN = re.compile(r"\.zip($|\\?)", re.IGNORECASE)
_CH_ZIP_PATTERN = re.compile(
    r"BasicCompanyDataAsOneFile-(20\d{2}-\d{2}-\d{2})\.zip",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LinkCandidate:
    """HTML link candidate with href and text."""

    href: str
    text: str


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._links: list[LinkCandidate] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = ""
        for name, value in attrs:
            if name.lower() == "href" and value:
                href = value
                break
        if not href:
            return
        self._current_href = href
        self._current_text = []

    @override
    def handle_data(self, data: str) -> None:
        if self._current_href is None:
            return
        self._current_text.append(data)

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return
        text = _normalise_text("".join(self._current_text))
        self._links.append(LinkCandidate(href=self._current_href, text=text))
        self._current_href = None
        self._current_text = []

    def links(self) -> list[LinkCandidate]:
        return list(self._links)


def extract_links(html: str) -> list[LinkCandidate]:
    """Extract anchor links from HTML."""
    parser = _LinkParser()
    parser.feed(html)
    return parser.links()


def find_sponsor_csv_link(*, html: str, base_url: str) -> str:
    """Find the best sponsor register CSV link from a GOV.UK page."""
    candidates = _filter_candidates(
        links=extract_links(html),
        base_url=base_url,
        predicate=_is_csv_link,
    )
    if not candidates:
        raise CsvLinkNotFoundError()
    scored = [(candidate, _score_sponsor_candidate(candidate)) for candidate in candidates]
    top_score = max(score for _, score in scored)
    top_candidates = [candidate for candidate, score in scored if score == top_score]
    if len(top_candidates) > 1:
        raise CsvLinkAmbiguousError([candidate.href for candidate in top_candidates])
    return top_candidates[0].href


def find_companies_house_zip_link(*, html: str, base_url: str) -> str:
    """Find the best Companies House ZIP link from the download page."""
    candidates = _filter_candidates(
        links=extract_links(html),
        base_url=base_url,
        predicate=_is_zip_link,
    )
    if not candidates:
        raise CompaniesHouseZipLinkNotFoundError()

    dated: list[tuple[str, LinkCandidate]] = []
    for candidate in candidates:
        match = _CH_ZIP_PATTERN.search(candidate.href)
        if match:
            dated.append((match.group(1), candidate))
    if dated:
        dated.sort(key=lambda item: (item[0], item[1].href), reverse=True)
        top_date = dated[0][0]
        top_candidates = [candidate for date, candidate in dated if date == top_date]
        if len(top_candidates) > 1:
            raise CompaniesHouseZipLinkAmbiguousError(
                [candidate.href for candidate in top_candidates]
            )
        return top_candidates[0].href

    named = [
        candidate
        for candidate in candidates
        if "basiccompanydataasonefile" in candidate.href.lower()
    ]
    if len(named) == 1:
        return named[0].href
    if len(named) > 1:
        raise CompaniesHouseZipLinkAmbiguousError([candidate.href for candidate in named])
    raise CompaniesHouseZipLinkNotFoundError()


def resolve_sponsor_csv_url(
    *,
    http_session: HttpSession,
    url: str | None,
    source_page_url: str = SPONSOR_SOURCE_PAGE_URL,
    timeout_seconds: float = 30,
) -> str:
    """Resolve sponsor register CSV URL from explicit input or GOV.UK page."""
    if url:
        return url
    html = http_session.get_text(source_page_url, timeout_seconds=timeout_seconds)
    return find_sponsor_csv_link(html=html, base_url=source_page_url)


def resolve_companies_house_zip_url(
    *,
    http_session: HttpSession,
    url: str | None,
    source_page_url: str = COMPANIES_HOUSE_SOURCE_PAGE_URL,
    timeout_seconds: float = 30,
) -> str:
    """Resolve Companies House ZIP URL from explicit input or download page."""
    if url:
        return url
    html = http_session.get_text(source_page_url, timeout_seconds=timeout_seconds)
    return find_companies_house_zip_link(html=html, base_url=source_page_url)


def _normalise_text(text: str) -> str:
    return " ".join(text.split())


def _is_csv_link(href: str) -> bool:
    return _CSV_PATTERN.search(href) is not None


def _is_zip_link(href: str) -> bool:
    return _ZIP_PATTERN.search(href) is not None


def _filter_candidates(
    *,
    links: list[LinkCandidate],
    base_url: str,
    predicate: Callable[[str], bool],
) -> list[LinkCandidate]:
    out: list[LinkCandidate] = []
    for link in links:
        href = link.href.strip()
        if not href:
            continue
        if not predicate(href):
            continue
        out.append(
            LinkCandidate(
                href=_normalise_href(href, base_url),
                text=link.text,
            )
        )
    return out


def _normalise_href(href: str, base_url: str) -> str:
    return urljoin(base_url, href.strip())


def _score_sponsor_candidate(candidate: LinkCandidate) -> int:
    combined = f"{candidate.href} {candidate.text}".lower()
    score = 0
    if "sponsor" in combined:
        score += 2
    if "licensed" in combined:
        score += 1
    if "register" in combined:
        score += 1
    if "worker" in combined:
        score += 1
    return score
