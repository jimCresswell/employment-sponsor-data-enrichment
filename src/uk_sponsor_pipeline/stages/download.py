from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from rich import print as rprint

GOVUK_PAGE = "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"


def _safe_filename_from_url(url: str) -> str:
    path = urlparse(url).path
    name = Path(path).name
    return name or "register.csv"


def download_latest(data_dir: str | Path = "data/raw", reports_dir: str | Path = "reports") -> Path:
    """Scrape GOV.UK to find the latest CSV asset URL and download it."""
    data_dir = Path(data_dir)
    reports_dir = Path(reports_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    html = requests.get(GOVUK_PAGE, timeout=30).text
    soup = BeautifulSoup(html, "lxml")

    # GOV.UK pages typically link assets.publishing.service.gov.uk for attachments
    csv_links = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if href.lower().endswith(".csv") and "assets.publishing.service.gov.uk" in href:
            csv_links.append(href)

    if not csv_links:
        # fallback: look for .csv anywhere, resolve relative
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if href.lower().endswith(".csv"):
                csv_links.append(urljoin(GOVUK_PAGE, href))

    if not csv_links:
        raise RuntimeError("Could not find a CSV link on the GOV.UK sponsor register page.")

    # Prefer the first (usually the latest attachment shown on GOV.UK)
    asset_url = csv_links[0]
    filename = _safe_filename_from_url(asset_url)
    out_path = data_dir / filename

    rprint(f"[cyan]Downloading[/cyan] {asset_url}")
    r = requests.get(asset_url, timeout=60)
    r.raise_for_status()
    out_path.write_bytes(r.content)

    manifest = {
        "source_page": GOVUK_PAGE,
        "asset_url": asset_url,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_file": str(out_path),
        "bytes": len(r.content),
    }
    (reports_dir / "download_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return out_path
