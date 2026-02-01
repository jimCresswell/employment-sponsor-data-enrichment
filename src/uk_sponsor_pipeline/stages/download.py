"""Download stage: fetch latest sponsor register CSV from GOV.UK.

Improvements over original:
- URL override via --url flag or env var
- SHA256 hash included in manifest
- CSV schema validation after download
- Prefer link text matching "Worker and Temporary Worker"
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from rich import print as rprint

from ..infrastructure import LocalFileSystem, RequestsSession
from ..infrastructure.io.validation import validate_as
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
class DownloadResult:
    """Result of download operation."""

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
    """Find the best CSV link from the page, preferring specific patterns."""
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
    return csv_links[0][2]


def _validate_csv_schema(content: bytes) -> bool:
    """Validate that CSV has required columns."""
    try:
        # Read first line to get headers
        first_line = content.split(b"\n")[0].decode("utf-8-sig")
        # Strip quotes and whitespace from each header
        headers = {h.strip().strip('"').strip("'") for h in first_line.split(",")}
        missing = RAW_REQUIRED_COLUMNS - headers
        if missing:
            rprint(f"[yellow]Warning: Missing columns: {missing}[/yellow]")
            return False
        return True
    except Exception as e:
        rprint(f"[yellow]Warning: Could not validate schema: {e}[/yellow]")
        return False


def download_latest(
    url_override: str | None = None,
    data_dir: str | Path = "data/raw",
    reports_dir: str | Path = "reports",
    session: HttpSession | None = None,
    fs: FileSystem | None = None,
) -> DownloadResult:
    """Download the latest sponsor register CSV from GOV.UK.

    Args:
        url_override: Direct URL to CSV (bypasses page scraping).
        data_dir: Directory to save downloaded CSV.
        reports_dir: Directory to save manifest.
        session: Optional HTTP session for testing.
        fs: Optional filesystem for testing.

    Returns:
        DownloadResult with path, hash, and validation status.

    Raises:
        RuntimeError: If no CSV link found or download fails.
    """
    data_dir = Path(data_dir)
    reports_dir = Path(reports_dir)
    fs = fs or LocalFileSystem()
    fs.mkdir(data_dir, parents=True)
    fs.mkdir(reports_dir, parents=True)

    session = session or RequestsSession()

    # Determine asset URL
    asset_url: str | None = url_override
    if asset_url:
        rprint(f"[cyan]Using override URL:[/cyan] {asset_url}")
    else:
        rprint(f"[cyan]Fetching GOV.UK page:[/cyan] {GOVUK_PAGE}")
        html = validate_as(str, session.get_text(GOVUK_PAGE, timeout_seconds=30))
        soup = BeautifulSoup(html, "lxml")

        asset_url = _find_best_csv_link(soup)
        if asset_url is None:
            raise RuntimeError(
                "Could not find a CSV link on the GOV.UK sponsor register page.\n"
                "The page structure may have changed. Use --url to specify the direct CSV URL."
            )

    assert asset_url is not None

    # Download the CSV
    filename = _safe_filename_from_url(asset_url)
    out_path = data_dir / filename

    rprint(f"[cyan]Downloading:[/cyan] {asset_url}")
    content = validate_as(bytes, session.get_bytes(asset_url, timeout_seconds=120))
    fs.write_bytes(content, out_path)

    # Calculate hash and validate schema
    sha256_hash = _calculate_sha256(content)
    schema_valid = _validate_csv_schema(content)

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
    fs.write_json(manifest, reports_dir / "download_manifest.json")

    result = DownloadResult(
        output_path=out_path,
        asset_url=asset_url,
        sha256_hash=sha256_hash,
        bytes_downloaded=len(content),
        schema_valid=schema_valid,
        downloaded_at_utc=downloaded_at,
    )

    if not schema_valid:
        rprint("[yellow]⚠ CSV schema validation failed. Check columns.[/yellow]")
    else:
        rprint(f"[green]✓ Downloaded {len(content):,} bytes, SHA256: {sha256_hash[:16]}...[/green]")

    return result
