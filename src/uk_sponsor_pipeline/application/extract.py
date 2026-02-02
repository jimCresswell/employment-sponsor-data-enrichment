"""Extract use-case: fetch latest sponsor register CSV from GOV.UK."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..exceptions import (
    CsvLinkAmbiguousError,
    CsvLinkNotFoundError,
    CsvSchemaDecodeError,
    CsvSchemaMissingColumnsError,
    DependencyMissingError,
)
from ..io_validation import validate_as
from ..observability import get_logger
from ..protocols import FileSystem, HttpSession
from ..schemas import RAW_REQUIRED_COLUMNS

GOVUK_PAGE = "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"

# Patterns to identify the correct CSV (ranked by preference)
PREFERRED_PATTERNS = [
    r"worker.*temporary.*worker",  # "Worker and Temporary Worker"
    r"licensed.*sponsors.*workers",
    r"sponsor.*register",
]


@dataclass
class ExtractResult:
    """Result of extract operation."""

    output_path: Path
    asset_url: str
    sha256_hash: str
    bytes_downloaded: int
    schema_valid: bool
    downloaded_at_utc: str


def _safe_filename_from_url(url: str) -> str:
    """Extract safe filename from URL."""
    path = urlparse(url).path
    name = Path(path).name
    return name or "register.csv"


def _calculate_sha256(content: bytes) -> str:
    """Calculate SHA256 hash of content."""
    return hashlib.sha256(content).hexdigest()


def _find_best_csv_link(soup: BeautifulSoup) -> str | None:
    """Find the best CSV link from the page, preferring specific patterns.

    Raises:
        CsvLinkAmbiguousError: If multiple links match the top-ranked pattern.
    """
    csv_links: list[tuple[int, str, str]] = []  # (priority, link_text, url)

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not isinstance(href, str):
            continue
        if not href.lower().endswith(".csv"):
            continue

        # Resolve relative URLs
        if "assets.publishing.service.gov.uk" in href:
            url = href
        else:
            url = urljoin(GOVUK_PAGE, href)

        # Get link text for pattern matching
        link_text = (a.get_text() or "").lower()
        combined_text = f"{link_text} {href}".lower()

        # Score based on pattern matches
        priority = 100  # Default low priority
        for i, pattern in enumerate(PREFERRED_PATTERNS):
            if re.search(pattern, combined_text, re.IGNORECASE):
                priority = i  # Lower = better
                break

        csv_links.append((priority, link_text, url))

    if not csv_links:
        return None

    # Sort by priority (lower is better), return best match
    csv_links.sort(key=lambda x: x[0])
    best_priority = csv_links[0][0]
    best_links = [link for link in csv_links if link[0] == best_priority]
    unique_urls = sorted({link[2] for link in best_links})
    if len(unique_urls) > 1:
        raise CsvLinkAmbiguousError(unique_urls)
    return unique_urls[0]


def _validate_csv_schema(content: bytes) -> None:
    """Validate that CSV has required columns."""
    try:
        first_line = content.split(b"\n", 1)[0].decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvSchemaDecodeError() from exc
    headers = {h.strip().strip('"').strip("'") for h in first_line.split(",")}
    missing = RAW_REQUIRED_COLUMNS - headers
    if missing:
        raise CsvSchemaMissingColumnsError(sorted(missing))


def extract_register(
    url_override: str | None = None,
    data_dir: str | Path = "data/raw",
    reports_dir: str | Path = "reports",
    session: HttpSession | None = None,
    fs: FileSystem | None = None,
) -> ExtractResult:
    """Extract the latest sponsor register CSV from GOV.UK.

    Args:
        url_override: Direct URL to CSV (bypasses page scraping).
        data_dir: Directory to save downloaded CSV.
        reports_dir: Directory to save manifest.
        session: HTTP session (required; inject at entry point).
        fs: Filesystem (required; inject at entry point).

    Returns:
        ExtractResult with path, hash, and validation status.

    Raises:
        DependencyMissingError: If required dependencies are missing.
        CsvLinkNotFoundError: If no CSV link is found on the GOV.UK page.
        CsvLinkAmbiguousError: If multiple CSV links match the best pattern.
        CsvSchemaDecodeError: If CSV headers cannot be decoded.
        CsvSchemaMissingColumnsError: If required columns are missing.
    """
    data_dir = Path(data_dir)
    reports_dir = Path(reports_dir)
    if fs is None:
        raise DependencyMissingError("FileSystem", reason="Inject it at the entry point.")
    fs.mkdir(data_dir, parents=True)
    fs.mkdir(reports_dir, parents=True)

    if session is None:
        raise DependencyMissingError("HttpSession", reason="Inject it at the entry point.")
    logger = get_logger("uk_sponsor_pipeline.extract")

    # Determine asset URL
    asset_url: str | None = url_override
    if asset_url:
        logger.info("Using override URL: %s", asset_url)
    else:
        logger.info("Fetching GOV.UK page: %s", GOVUK_PAGE)
        html = validate_as(str, session.get_text(GOVUK_PAGE, timeout_seconds=30))
        soup = BeautifulSoup(html, "lxml")

        asset_url = _find_best_csv_link(soup)
        if asset_url is None:
            raise CsvLinkNotFoundError()

    assert asset_url is not None

    # Download the CSV
    filename = _safe_filename_from_url(asset_url)
    out_path = data_dir / filename

    logger.info("Downloading: %s", asset_url)
    content = validate_as(bytes, session.get_bytes(asset_url, timeout_seconds=120))
    fs.write_bytes(content, out_path)

    # Calculate hash and validate schema
    sha256_hash = _calculate_sha256(content)
    _validate_csv_schema(content)
    schema_valid = True

    downloaded_at = datetime.now(UTC).isoformat()

    # Write manifest
    manifest = {
        "source_page": GOVUK_PAGE,
        "asset_url": asset_url,
        "downloaded_at_utc": downloaded_at,
        "output_file": str(out_path),
        "bytes": len(content),
        "sha256_hash": sha256_hash,
        "schema_valid": schema_valid,
    }
    fs.write_json(manifest, reports_dir / "extract_manifest.json")

    result = ExtractResult(
        output_path=out_path,
        asset_url=asset_url,
        sha256_hash=sha256_hash,
        bytes_downloaded=len(content),
        schema_valid=schema_valid,
        downloaded_at_utc=downloaded_at,
    )

    logger.info("Downloaded %s bytes, SHA256: %s", f"{len(content):,}", sha256_hash[:16])

    return result
