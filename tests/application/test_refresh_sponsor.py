"""Tests for refresh-sponsor snapshot generation."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import override

import pandas as pd
import pytest

from uk_sponsor_pipeline.application.refresh_sponsor import run_refresh_sponsor
from uk_sponsor_pipeline.exceptions import SchemaColumnsMissingError
from uk_sponsor_pipeline.infrastructure import LocalFileSystem
from uk_sponsor_pipeline.io_validation import validate_as
from uk_sponsor_pipeline.protocols import HttpSession


class DummySession(HttpSession):
    """HTTP session stub that streams provided bytes."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    @override
    def get_text(self, url: str, *, timeout_seconds: float) -> str:
        _ = (url, timeout_seconds)
        return self.payload.decode("utf-8")

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

    result = run_refresh_sponsor(
        url="https://example.com/sponsor-register-2026-02-01.csv",
        snapshot_root=snapshot_root,
        fs=fs,
        http_session=session,
        command_line="uk-sponsor refresh-sponsor --url https://example.com",
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
