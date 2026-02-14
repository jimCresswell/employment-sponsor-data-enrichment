"""Tests for snapshot helpers and atomic writes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

import uk_sponsor_pipeline
from uk_sponsor_pipeline.application.snapshots import (
    SnapshotPaths,
    SnapshotRowCounts,
    build_snapshot_manifest,
    commit_snapshot,
    derive_snapshot_date,
    resolve_latest_snapshot_dir,
    resolve_latest_snapshot_path,
    start_snapshot_write,
)
from uk_sponsor_pipeline.exceptions import (
    SnapshotAlreadyExistsError,
    SnapshotArtefactMissingError,
    SnapshotNotFoundError,
    SnapshotTimestampError,
)
from uk_sponsor_pipeline.infrastructure import LocalFileSystem


def test_derive_snapshot_date_from_filename() -> None:
    downloaded_at = datetime(2026, 2, 4, tzinfo=UTC)
    date = derive_snapshot_date(
        source_name="BasicCompanyDataAsOneFile-2026-02-01.csv",
        downloaded_at_utc=downloaded_at,
    )
    assert date == "2026-02-01"


def test_derive_snapshot_date_falls_back_to_download_date() -> None:
    downloaded_at = datetime(2026, 2, 4, 12, 30, tzinfo=UTC)
    date = derive_snapshot_date(
        source_name="basic-company-data.csv",
        downloaded_at_utc=downloaded_at,
    )
    assert date == "2026-02-04"


def test_derive_snapshot_date_requires_timezone() -> None:
    downloaded_at = datetime(2026, 2, 4, 12, 30, tzinfo=UTC).replace(tzinfo=None)
    with pytest.raises(SnapshotTimestampError):
        derive_snapshot_date(
            source_name="basic-company-data.csv",
            downloaded_at_utc=downloaded_at,
        )


def test_start_snapshot_write_creates_staging_dir(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    paths = start_snapshot_write(
        snapshot_root=snapshot_root,
        dataset="sponsor",
        snapshot_date="2026-02-01",
        fs=fs,
        uuid_factory=lambda: "abc123",
    )

    assert isinstance(paths, SnapshotPaths)
    assert paths.final_dir == snapshot_root / "sponsor" / "2026-02-01"
    assert paths.staging_dir == snapshot_root / "sponsor" / ".tmp-abc123"
    assert paths.staging_dir.exists() is True
    assert paths.final_dir.exists() is False


def test_start_snapshot_write_raises_if_final_exists(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    final_dir = snapshot_root / "sponsor" / "2026-02-01"
    final_dir.mkdir(parents=True)

    with pytest.raises(SnapshotAlreadyExistsError):
        start_snapshot_write(
            snapshot_root=snapshot_root,
            dataset="sponsor",
            snapshot_date="2026-02-01",
            fs=fs,
            uuid_factory=lambda: "abc123",
        )


def test_commit_snapshot_moves_staging_to_final(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    paths = start_snapshot_write(
        snapshot_root=snapshot_root,
        dataset="sponsor",
        snapshot_date="2026-02-01",
        fs=fs,
        uuid_factory=lambda: "abc123",
    )

    staged_file = paths.staging_dir / "manifest.json"
    fs.write_text("{}", staged_file)

    commit_snapshot(paths=paths, fs=fs)

    assert (paths.final_dir / "manifest.json").exists() is True
    assert paths.staging_dir.exists() is False


def test_build_snapshot_manifest_includes_required_fields() -> None:
    downloaded_at = datetime(2026, 2, 4, 12, 0, tzinfo=UTC)
    last_updated = datetime(2026, 2, 4, 12, 30, tzinfo=UTC)
    row_counts: SnapshotRowCounts = {"raw": 10, "clean": 8}
    artefacts = {"raw": "raw.csv", "clean": "clean.csv", "manifest": "manifest.json"}

    manifest = build_snapshot_manifest(
        dataset="sponsor",
        snapshot_date="2026-02-01",
        source_url="https://example.com/register.csv",
        downloaded_at_utc=downloaded_at,
        last_updated_at_utc=last_updated,
        schema_version="sponsor_clean_v1",
        sha256_hash_raw="rawhash",
        sha256_hash_clean="cleanhash",
        bytes_raw=123,
        row_counts=row_counts,
        artefacts=artefacts,
        command_line="uship admin refresh sponsor --url https://example.com/register.csv",
        git_sha="abc123",
        tool_version="1.2.3",
    )

    assert manifest["dataset"] == "sponsor"
    assert manifest["snapshot_date"] == "2026-02-01"
    assert manifest["source_url"] == "https://example.com/register.csv"
    assert manifest["downloaded_at_utc"] == downloaded_at.isoformat()
    assert manifest["last_updated_at_utc"] == last_updated.isoformat()
    assert manifest["schema_version"] == "sponsor_clean_v1"
    assert manifest["sha256_hash_raw"] == "rawhash"
    assert manifest["sha256_hash_clean"] == "cleanhash"
    assert manifest["bytes_raw"] == 123
    assert manifest["row_counts"] == {"raw": 10, "clean": 8}
    assert manifest["artefacts"] == artefacts
    assert manifest["git_sha"] == "abc123"
    assert manifest["tool_version"] == "1.2.3"
    assert manifest["command_line"]


def test_build_snapshot_manifest_defaults_git_sha_and_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.setattr(uk_sponsor_pipeline, "__version__", " ", raising=False)
    downloaded_at = datetime(2026, 2, 4, 12, 0, tzinfo=UTC)
    last_updated = datetime(2026, 2, 4, 12, 30, tzinfo=UTC)
    row_counts: SnapshotRowCounts = {"raw": 1, "clean": 1}

    manifest = build_snapshot_manifest(
        dataset="sponsor",
        snapshot_date="2026-02-01",
        source_url="https://example.com/register.csv",
        downloaded_at_utc=downloaded_at,
        last_updated_at_utc=last_updated,
        schema_version="sponsor_clean_v1",
        sha256_hash_raw="rawhash",
        sha256_hash_clean="cleanhash",
        bytes_raw=1,
        row_counts=row_counts,
        artefacts={"raw": "raw.csv", "clean": "clean.csv"},
        command_line="uship admin refresh sponsor --url https://example.com/register.csv",
        git_sha=None,
        tool_version=None,
    )

    assert manifest["git_sha"] == "unknown"
    assert manifest["tool_version"] == "0.0.0+unknown"


def test_build_snapshot_manifest_defaults_to_package_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.setattr(uk_sponsor_pipeline, "__version__", "9.8.7", raising=False)
    downloaded_at = datetime(2026, 2, 4, 12, 0, tzinfo=UTC)
    last_updated = datetime(2026, 2, 4, 12, 30, tzinfo=UTC)
    row_counts: SnapshotRowCounts = {"raw": 1, "clean": 1}

    manifest = build_snapshot_manifest(
        dataset="sponsor",
        snapshot_date="2026-02-01",
        source_url="https://example.com/register.csv",
        downloaded_at_utc=downloaded_at,
        last_updated_at_utc=last_updated,
        schema_version="sponsor_clean_v1",
        sha256_hash_raw="rawhash",
        sha256_hash_clean="cleanhash",
        bytes_raw=1,
        row_counts=row_counts,
        artefacts={"raw": "raw.csv", "clean": "clean.csv"},
        command_line="uship admin refresh sponsor --url https://example.com/register.csv",
        git_sha=None,
        tool_version=None,
    )

    assert manifest["tool_version"] == "9.8.7"


def test_resolve_latest_snapshot_dir_uses_latest_date(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    older = snapshot_root / "sponsor" / "2026-02-01"
    newer = snapshot_root / "sponsor" / "2026-02-03"
    fs.write_text("{}", older / "manifest.json")
    fs.write_text("{}", newer / "manifest.json")

    resolved = resolve_latest_snapshot_dir(
        snapshot_root=snapshot_root,
        dataset="sponsor",
        fs=fs,
    )

    assert resolved == newer


def test_resolve_latest_snapshot_dir_raises_when_missing(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"

    with pytest.raises(SnapshotNotFoundError):
        resolve_latest_snapshot_dir(
            snapshot_root=snapshot_root,
            dataset="sponsor",
            fs=fs,
        )


def test_resolve_latest_snapshot_path_requires_artefact(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    snapshot_root = tmp_path / "snapshots"
    snapshot_dir = snapshot_root / "sponsor" / "2026-02-01"
    fs.write_text("{}", snapshot_dir / "manifest.json")

    with pytest.raises(SnapshotArtefactMissingError):
        resolve_latest_snapshot_path(
            snapshot_root=snapshot_root,
            dataset="sponsor",
            filename="clean.csv",
            fs=fs,
        )
