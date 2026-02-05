"""Tests for extract step with filesystem injection."""

from collections.abc import Iterable
from pathlib import Path
from typing import override

import pytest

from tests.fakes import InMemoryFileSystem
from uk_sponsor_pipeline.application.extract import extract_register
from uk_sponsor_pipeline.exceptions import (
    CsvLinkAmbiguousError,
    CsvSchemaMissingColumnsError,
    DependencyMissingError,
)
from uk_sponsor_pipeline.protocols import HttpSession


class DummyResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.status_code = 200
        self.text = content.decode("utf-8", errors="ignore")

    def raise_for_status(self) -> None:
        return None


class DummySession(HttpSession):
    def __init__(self, response: DummyResponse) -> None:
        self.response = response
        self.calls: list[str] = []

    @override
    def get_text(self, url: str, *, timeout_seconds: float) -> str:
        self.calls.append(url)
        return self.response.text

    @override
    def get_bytes(self, url: str, *, timeout_seconds: float) -> bytes:
        self.calls.append(url)
        return self.response.content

    @override
    def iter_bytes(
        self,
        url: str,
        *,
        timeout_seconds: float,
        chunk_size: int,
    ) -> Iterable[bytes]:
        self.calls.append(url)
        _ = (timeout_seconds, chunk_size)
        yield self.response.content


def test_extract_with_in_memory_fs(in_memory_fs: InMemoryFileSystem) -> None:
    csv_content = (
        b"Organisation Name,Town/City,County,Type & Rating,Route\n"
        b"Acme Ltd,London,Greater London,A rating,Skilled Worker\n"
    )

    session = DummySession(DummyResponse(csv_content))

    result = extract_register(
        url_override="https://example.com/register.csv",
        data_dir="data/raw",
        reports_dir="reports",
        session=session,
        fs=in_memory_fs,
    )

    assert in_memory_fs.read_bytes(result.output_path) == csv_content
    manifest = in_memory_fs.read_json(Path("reports") / "extract_manifest.json")
    assert isinstance(manifest.get("schema_valid"), bool)
    assert isinstance(manifest.get("asset_url"), str)
    assert manifest["schema_valid"] is True
    assert manifest["asset_url"] == "https://example.com/register.csv"


def test_extract_fails_on_invalid_schema(in_memory_fs: InMemoryFileSystem) -> None:
    csv_content = (
        b"Organisation Name,Town/City,Type & Rating,Route\n"
        b"Acme Ltd,London,A rating,Skilled Worker\n"
    )
    session = DummySession(DummyResponse(csv_content))

    with pytest.raises(CsvSchemaMissingColumnsError) as exc_info:
        extract_register(
            url_override="https://example.com/register.csv",
            data_dir="data/raw",
            reports_dir="reports",
            session=session,
            fs=in_memory_fs,
        )

    assert "Missing columns" in str(exc_info.value)
    assert "County" in str(exc_info.value)


def test_extract_requires_filesystem() -> None:
    csv_content = (
        b"Organisation Name,Town/City,County,Type & Rating,Route\n"
        b"Acme Ltd,London,Greater London,A rating,Skilled Worker\n"
    )
    session = DummySession(DummyResponse(csv_content))

    with pytest.raises(DependencyMissingError) as exc_info:
        extract_register(
            url_override="https://example.com/register.csv",
            data_dir="data/raw",
            reports_dir="reports",
            session=session,
            fs=None,
        )

    assert "FileSystem" in str(exc_info.value)


def test_extract_requires_session(in_memory_fs: InMemoryFileSystem) -> None:
    with pytest.raises(DependencyMissingError) as exc_info:
        extract_register(
            url_override="https://example.com/register.csv",
            data_dir="data/raw",
            reports_dir="reports",
            session=None,
            fs=in_memory_fs,
        )

    assert "HttpSession" in str(exc_info.value)


def test_extract_fails_on_ambiguous_csv_links(in_memory_fs: InMemoryFileSystem) -> None:
    html = b"""
    <html>
      <body>
        <a href="https://assets.publishing.service.gov.uk/worker.csv">
          Worker and Temporary Worker register
        </a>
        <a href="https://assets.publishing.service.gov.uk/worker-archive.csv">
          Worker and Temporary Worker register (archive)
        </a>
      </body>
    </html>
    """
    session = DummySession(DummyResponse(html))

    with pytest.raises(CsvLinkAmbiguousError) as exc_info:
        extract_register(
            data_dir="data/raw",
            reports_dir="reports",
            session=session,
            fs=in_memory_fs,
        )

    message = str(exc_info.value)
    assert "Multiple candidate CSV links" in message
    assert "--url" in message
