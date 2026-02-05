"""Tests for refresh-companies-house snapshot generation."""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import override

import pandas as pd
import pytest

from tests.fakes import FakeProgressReporter
from uk_sponsor_pipeline.application.companies_house_bulk import RAW_HEADERS_TRIMMED
from uk_sponsor_pipeline.application.refresh_companies_house import run_refresh_companies_house
from uk_sponsor_pipeline.exceptions import (
    CompaniesHouseUriMismatchError,
    CsvSchemaMissingColumnsError,
)
from uk_sponsor_pipeline.infrastructure import LocalFileSystem
from uk_sponsor_pipeline.protocols import HttpSession


class DummySession(HttpSession):
    """HTTP session stub that streams provided bytes."""

    def __init__(self, payload: bytes, page_html: str | None = None) -> None:
        self.payload = payload
        self.page_html = page_html or ""

    @override
    def get_text(self, url: str, *, timeout_seconds: float) -> str:
        _ = (url, timeout_seconds)
        return self.page_html

    @override
    def get_bytes(self, url: str, *, timeout_seconds: float) -> bytes:
        _ = (url, timeout_seconds)
        return self.payload

    @override
    def iter_bytes(
        self,
        url: str,
        *,
        timeout_seconds: float,
        chunk_size: int,
    ) -> Iterable[bytes]:
        _ = (url, timeout_seconds, chunk_size)
        yield self.payload


def _raw_headers_with_spaces() -> list[str]:
    headers: list[str] = []
    for idx, name in enumerate(RAW_HEADERS_TRIMMED):
        if idx % 4 == 0:
            headers.append(f" {name}")
        else:
            headers.append(name)
    return headers


def _build_raw_row(company_number: str, uri: str) -> dict[str, str]:
    row = {header: "" for header in RAW_HEADERS_TRIMMED}
    row["CompanyNumber"] = company_number
    row["CompanyName"] = "Acme Ltd"
    row["CompanyStatus"] = "ACTIVE"
    row["CompanyCategory"] = "Public Limited Company"
    row["IncorporationDate"] = "2020-01-02"
    row["SICCode.SicText_1"] = "62020 - Information technology consultancy activities"
    row["SICCode.SicText_2"] = "62090 - Other information technology service activities"
    row["RegAddress.PostTown"] = "London"
    row["RegAddress.County"] = "Greater London"
    row["RegAddress.PostCode"] = "EC1A 1BB"
    row["URI"] = uri
    return row


def _build_csv_payload(company_number: str, uri: str) -> bytes:
    headers = _raw_headers_with_spaces()
    raw_row = _build_raw_row(company_number, uri)
    row = {header: raw_row[header.strip()] for header in headers}
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def test_refresh_companies_house_csv_writes_snapshot_and_index(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    payload = _build_csv_payload(
        company_number="01234567",
        uri="http://data.companieshouse.gov.uk/doc/company/01234567",
    )
    session = DummySession(payload)
    now = datetime(2026, 2, 4, 12, 30, tzinfo=UTC)
    progress = FakeProgressReporter()

    result = run_refresh_companies_house(
        url="https://example.com/BasicCompanyDataAsOneFile-2026-02-01.csv",
        snapshot_root=snapshot_root,
        fs=fs,
        http_session=session,
        command_line="uk-sponsor refresh-companies-house --url https://example.com",
        progress=progress,
        now_fn=lambda: now,
    )

    snapshot_dir = snapshot_root / "companies_house" / "2026-02-01"
    assert result.snapshot_dir == snapshot_dir
    assert (snapshot_dir / "raw.csv").exists() is True
    assert (snapshot_dir / "clean.csv").exists() is True
    assert (snapshot_dir / "manifest.json").exists() is True

    clean = pd.read_csv(snapshot_dir / "clean.csv", dtype=str).fillna("")
    assert clean["company_number"].tolist() == ["01234567"]
    assert clean["company_type"].tolist() == ["public-limited-company"]

    index_path = snapshot_dir / "index_tokens_a.csv"
    assert index_path.exists() is True
    contents = index_path.read_text(encoding="utf-8")
    assert "acme,01234567" in contents
    assert progress.starts == [("download", None), ("clean", None), ("index", 1)]
    assert progress.advances == [len(payload), 1, 1]
    assert progress.finished == 3


def test_refresh_companies_house_zip_extracts_raw_csv(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    csv_payload = _build_csv_payload(
        company_number="01234567",
        uri="http://data.companieshouse.gov.uk/doc/company/01234567",
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipf:
        zipf.writestr("BasicCompanyDataAsOneFile-2026-02-01.csv", csv_payload)
    session = DummySession(buffer.getvalue())

    result = run_refresh_companies_house(
        url="https://example.com/BasicCompanyDataAsOneFile-2026-02-01.zip",
        snapshot_root=snapshot_root,
        fs=fs,
        http_session=session,
        command_line="uk-sponsor refresh-companies-house --url https://example.com",
        now_fn=lambda: datetime(2026, 2, 4, tzinfo=UTC),
    )

    snapshot_dir = snapshot_root / "companies_house" / "2026-02-01"
    assert result.snapshot_dir == snapshot_dir
    assert (snapshot_dir / "raw.zip").exists() is True
    assert (snapshot_dir / "raw.csv").exists() is True


def test_refresh_companies_house_fails_on_uri_mismatch(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    payload = _build_csv_payload(
        company_number="01234567",
        uri="http://data.companieshouse.gov.uk/doc/company/99999999",
    )
    session = DummySession(payload)

    with pytest.raises(CompaniesHouseUriMismatchError):
        run_refresh_companies_house(
            url="https://example.com/BasicCompanyDataAsOneFile-2026-02-01.csv",
            snapshot_root=snapshot_root,
            fs=fs,
            http_session=session,
            command_line="uk-sponsor refresh-companies-house --url https://example.com",
            now_fn=lambda: datetime(2026, 2, 4, tzinfo=UTC),
        )


def test_refresh_companies_house_fails_on_missing_columns(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    payload = (
        b"CompanyName,CompanyNumber,URI\n"
        b"Acme Ltd,01234567,http://data.companieshouse.gov.uk/doc/company/01234567\n"
    )
    session = DummySession(payload)

    with pytest.raises(CsvSchemaMissingColumnsError):
        run_refresh_companies_house(
            url="https://example.com/BasicCompanyDataAsOneFile-2026-02-01.csv",
            snapshot_root=snapshot_root,
            fs=fs,
            http_session=session,
            command_line="uk-sponsor refresh-companies-house --url https://example.com",
            now_fn=lambda: datetime(2026, 2, 4, tzinfo=UTC),
        )


def test_refresh_companies_house_discovers_zip_link(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    csv_payload = _build_csv_payload(
        company_number="01234567",
        uri="http://data.companieshouse.gov.uk/doc/company/01234567",
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipf:
        zipf.writestr("BasicCompanyDataAsOneFile-2026-02-01.csv", csv_payload)
    html = """
    <html>
        <body>
            <a href="BasicCompanyDataAsOneFile-2026-02-01.zip">ZIP</a>
        </body>
    </html>
    """
    session = DummySession(buffer.getvalue(), page_html=html)

    result = run_refresh_companies_house(
        url=None,
        snapshot_root=snapshot_root,
        fs=fs,
        http_session=session,
        command_line="uk-sponsor refresh-companies-house",
        now_fn=lambda: datetime(2026, 2, 4, tzinfo=UTC),
        source_page_url="https://download.companieshouse.gov.uk/en_output.html",
    )

    assert result.snapshot_date == "2026-02-01"
