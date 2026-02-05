"""Tests for source link discovery helpers."""

from __future__ import annotations

import pytest

from uk_sponsor_pipeline.application.source_links import (
    find_companies_house_zip_link,
    find_sponsor_csv_link,
)
from uk_sponsor_pipeline.exceptions import (
    CompaniesHouseZipLinkNotFoundError,
    CsvLinkAmbiguousError,
    CsvLinkNotFoundError,
)


def test_find_sponsor_csv_link_selects_best_match() -> None:
    html = """
    <html>
        <body>
            <a href="/files/register-of-licensed-sponsors-workers-2026-02-01.pdf">PDF</a>
            <a href="/files/register-of-licensed-sponsors-workers-2026-02-01.csv">CSV</a>
        </body>
    </html>
    """
    url = find_sponsor_csv_link(
        html=html,
        base_url="https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers",
    )
    assert url == ("https://www.gov.uk/files/register-of-licensed-sponsors-workers-2026-02-01.csv")


def test_find_sponsor_csv_link_raises_on_ambiguous() -> None:
    html = """
    <html>
        <body>
            <a href="/files/sponsors-1.csv">CSV</a>
            <a href="/files/sponsors-2.csv">CSV</a>
        </body>
    </html>
    """
    with pytest.raises(CsvLinkAmbiguousError):
        find_sponsor_csv_link(
            html=html,
            base_url="https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers",
        )


def test_find_sponsor_csv_link_raises_when_missing() -> None:
    html = '<html><body><a href="/files/sponsors.pdf">PDF</a></body></html>'
    with pytest.raises(CsvLinkNotFoundError):
        find_sponsor_csv_link(
            html=html,
            base_url="https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers",
        )


def test_find_companies_house_zip_link_selects_latest() -> None:
    html = """
    <html>
        <body>
            <a href="BasicCompanyDataAsOneFile-2026-01-01.zip">ZIP</a>
            <a href="BasicCompanyDataAsOneFile-2026-02-01.zip">ZIP</a>
        </body>
    </html>
    """
    url = find_companies_house_zip_link(
        html=html,
        base_url="https://download.companieshouse.gov.uk/en_output.html",
    )
    assert url == "https://download.companieshouse.gov.uk/BasicCompanyDataAsOneFile-2026-02-01.zip"


def test_find_companies_house_zip_link_raises_when_missing() -> None:
    html = '<html><body><a href="file.txt">Text</a></body></html>'
    with pytest.raises(CompaniesHouseZipLinkNotFoundError):
        find_companies_house_zip_link(
            html=html,
            base_url="https://download.companieshouse.gov.uk/en_output.html",
        )
