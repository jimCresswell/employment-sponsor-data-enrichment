"""Tests for refresh-sponsor snapshot generation."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import override

import pandas as pd
import pytest

from tests.fakes import FakeProgressReporter
from uk_sponsor_pipeline.application.refresh_sponsor import (
    run_refresh_sponsor,
    run_refresh_sponsor_acquire,
    run_refresh_sponsor_clean,
)
from uk_sponsor_pipeline.exceptions import (
    PendingAcquireSnapshotNotFoundError,
    SchemaColumnsMissingError,
)
from uk_sponsor_pipeline.infrastructure import LocalFileSystem
from uk_sponsor_pipeline.io_validation import validate_as
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


def test_refresh_sponsor_writes_snapshot_and_manifest(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    payload = (
        b"Organisation Name,Town/City,County,Type & Rating,Route\n"
        b"Acme Ltd,London,Greater London,A rating,Skilled Worker\n"
    )
    session = DummySession(payload)
    now = datetime(2026, 2, 4, 12, 30, tzinfo=UTC)

    progress = FakeProgressReporter()
    result = run_refresh_sponsor(
        url="https://example.com/sponsor-register-2026-02-01.csv",
        snapshot_root=snapshot_root,
        fs=fs,
        http_session=session,
        command_line="uk-sponsor refresh-sponsor --url https://example.com",
        progress=progress,
        now_fn=lambda: now,
    )

    snapshot_dir = snapshot_root / "sponsor" / "2026-02-01"
    assert result.snapshot_dir == snapshot_dir
    assert (snapshot_dir / "raw.csv").exists() is True
    assert (snapshot_dir / "clean.csv").exists() is True
    assert (snapshot_dir / "register_stats.json").exists() is True
    assert (snapshot_dir / "manifest.json").exists() is True

    manifest = validate_as(dict[str, object], fs.read_json(snapshot_dir / "manifest.json"))
    assert manifest["dataset"] == "sponsor"
    assert manifest["snapshot_date"] == "2026-02-01"
    source_url = str(manifest.get("source_url", ""))
    assert source_url.startswith("https://example.com/")

    clean = pd.read_csv(snapshot_dir / "clean.csv", dtype=str).fillna("")
    assert clean["Organisation Name"].tolist() == ["Acme Ltd"]
    assert progress.starts == [("download", None), ("clean", 1)]
    assert progress.advances == [len(payload), 1]
    assert progress.finished == 2


def test_refresh_sponsor_fails_on_missing_columns(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    payload = (
        b"Organisation Name,Town/City,Type & Rating,Route\n"
        b"Acme Ltd,London,A rating,Skilled Worker\n"
    )
    session = DummySession(payload)

    with pytest.raises(SchemaColumnsMissingError):
        run_refresh_sponsor(
            url="https://example.com/sponsor-register-2026-02-01.csv",
            snapshot_root=snapshot_root,
            fs=fs,
            http_session=session,
            command_line="uk-sponsor refresh-sponsor --url https://example.com",
            now_fn=lambda: datetime(2026, 2, 4, tzinfo=UTC),
        )


def test_refresh_sponsor_discovers_csv_link(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    payload = (
        b"Organisation Name,Town/City,County,Type & Rating,Route\n"
        b"Acme Ltd,London,Greater London,A rating,Skilled Worker\n"
    )
    html = """
    <html>
        <body>
            <a href="https://example.com/sponsor-register-2026-02-01.csv">CSV</a>
        </body>
    </html>
    """
    session = DummySession(payload, page_html=html)

    result = run_refresh_sponsor(
        url=None,
        snapshot_root=snapshot_root,
        fs=fs,
        http_session=session,
        command_line="uk-sponsor refresh-sponsor",
        now_fn=lambda: datetime(2026, 2, 4, tzinfo=UTC),
        source_page_url="https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers",
    )

    assert result.snapshot_date == "2026-02-01"


def test_refresh_sponsor_acquire_writes_pending_raw(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    payload = (
        b"Organisation Name,Town/City,County,Type & Rating,Route\n"
        b"Acme Ltd,London,Greater London,A rating,Skilled Worker\n"
    )
    session = DummySession(payload)

    result = run_refresh_sponsor_acquire(
        url="https://example.com/sponsor-register-2026-02-01.csv",
        snapshot_root=snapshot_root,
        fs=fs,
        http_session=session,
        command_line="uk-sponsor refresh-sponsor --only acquire",
        now_fn=lambda: datetime(2026, 2, 4, tzinfo=UTC),
    )

    assert result.paths.snapshot_date == "2026-02-01"
    assert result.raw_path.exists() is True
    assert result.paths.staging_dir.exists() is True
    assert (result.paths.staging_dir / "pending.json").exists() is True
    assert (snapshot_root / "sponsor" / "2026-02-01").exists() is False


def test_refresh_sponsor_clean_commits_pending_snapshot(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    payload = (
        b"Organisation Name,Town/City,County,Type & Rating,Route\n"
        b"Acme Ltd,London,Greater London,A rating,Skilled Worker\n"
    )
    session = DummySession(payload)
    run_refresh_sponsor_acquire(
        url="https://example.com/sponsor-register-2026-02-01.csv",
        snapshot_root=snapshot_root,
        fs=fs,
        http_session=session,
        command_line="uk-sponsor refresh-sponsor --only acquire",
        now_fn=lambda: datetime(2026, 2, 4, tzinfo=UTC),
    )

    result = run_refresh_sponsor_clean(
        snapshot_root=snapshot_root,
        fs=fs,
        command_line="uk-sponsor refresh-sponsor --only clean",
        now_fn=lambda: datetime(2026, 2, 4, tzinfo=UTC),
    )

    snapshot_dir = snapshot_root / "sponsor" / "2026-02-01"
    assert result.snapshot_dir == snapshot_dir
    assert (snapshot_dir / "raw.csv").exists() is True
    assert (snapshot_dir / "clean.csv").exists() is True
    assert (snapshot_dir / "manifest.json").exists() is True


def test_refresh_sponsor_clean_raises_without_pending_snapshot(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    with pytest.raises(PendingAcquireSnapshotNotFoundError):
        run_refresh_sponsor_clean(
            snapshot_root=snapshot_root,
            fs=fs,
            command_line="uk-sponsor refresh-sponsor --only clean",
            now_fn=lambda: datetime(2026, 2, 4, tzinfo=UTC),
        )
