"""Refresh sponsor register snapshot (cache-first)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from ..exceptions import DependencyMissingError, PendingAcquireSnapshotNotFoundError
from ..observability import get_logger
from ..protocols import FileSystem, HttpSession, ProgressReporter
from .snapshots import (
    PendingAcquireState,
    SnapshotPaths,
    SnapshotRowCounts,
    build_snapshot_manifest,
    commit_snapshot,
    derive_snapshot_date,
    resolve_latest_pending_snapshot,
    start_snapshot_write,
    write_pending_acquire_state,
)
from .source_links import SPONSOR_SOURCE_PAGE_URL, resolve_sponsor_csv_url
from .transform_register import TransformRegisterResult, run_transform_register

SPONSOR_DATASET = "sponsor"
SPONSOR_SCHEMA_VERSION = "sponsor_clean_v1"


@dataclass(frozen=True)
class RefreshSponsorResult:
    """Result of refresh-sponsor snapshot generation."""

    snapshot_dir: Path
    snapshot_date: str
    raw_path: Path
    clean_path: Path
    stats_path: Path
    manifest_path: Path
    bytes_raw: int
    row_counts: SnapshotRowCounts


@dataclass(frozen=True)
class RefreshSponsorAcquireResult:
    """Result of refresh-sponsor acquire stage (download only)."""

    paths: SnapshotPaths
    source_url: str
    downloaded_at_utc: datetime
    raw_path: Path
    bytes_raw: int


def _sha256(path: Path, fs: FileSystem) -> str:
    return hashlib.sha256(fs.read_bytes(path)).hexdigest()


def run_refresh_sponsor_acquire(
    *,
    url: str | None,
    snapshot_root: str | Path,
    fs: FileSystem | None = None,
    http_session: HttpSession | None = None,
    command_line: str,
    progress: ProgressReporter | None = None,
    now_fn: Callable[[], datetime] | None = None,
    source_page_url: str | None = None,
) -> RefreshSponsorAcquireResult:
    """Resolve/discover source and download raw sponsor CSV into staging."""
    _ = command_line
    if fs is None:
        raise DependencyMissingError("FileSystem", reason="Inject it at the entry point.")
    if http_session is None:
        raise DependencyMissingError("HttpSession", reason="Inject it at the entry point.")

    clock = now_fn or (lambda: datetime.now(UTC))
    downloaded_at = clock()
    resolved_url = resolve_sponsor_csv_url(
        http_session=http_session,
        url=url,
        source_page_url=source_page_url or SPONSOR_SOURCE_PAGE_URL,
    )
    source_name = Path(urlparse(resolved_url).path).name or "sponsor_register.csv"
    snapshot_date = derive_snapshot_date(
        source_name=source_name,
        downloaded_at_utc=downloaded_at,
    )
    paths = start_snapshot_write(
        snapshot_root=Path(snapshot_root),
        dataset=SPONSOR_DATASET,
        snapshot_date=snapshot_date,
        fs=fs,
    )

    logger = get_logger("uk_sponsor_pipeline.refresh_sponsor")
    logger.info("Downloading sponsor register: %s", resolved_url)

    raw_path = paths.staging_dir / "raw.csv"
    bytes_downloaded = 0

    if progress is not None:
        progress.start("download", None)

    def stream() -> Iterable[bytes]:
        nonlocal bytes_downloaded
        for chunk in http_session.iter_bytes(
            resolved_url,
            timeout_seconds=120,
            chunk_size=1024 * 64,
        ):
            bytes_downloaded += len(chunk)
            if progress is not None:
                progress.advance(len(chunk))
            yield chunk

    fs.write_bytes_stream(raw_path, stream())
    if progress is not None:
        progress.finish()

    write_pending_acquire_state(
        paths=paths,
        source_url=resolved_url,
        downloaded_at_utc=downloaded_at,
        bytes_raw=bytes_downloaded,
        fs=fs,
    )
    return RefreshSponsorAcquireResult(
        paths=paths,
        source_url=resolved_url,
        downloaded_at_utc=downloaded_at,
        raw_path=raw_path,
        bytes_raw=bytes_downloaded,
    )


def run_refresh_sponsor_clean(
    *,
    snapshot_root: str | Path,
    fs: FileSystem | None = None,
    command_line: str,
    progress: ProgressReporter | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> RefreshSponsorResult:
    """Clean the latest pending sponsor acquire snapshot and commit it."""
    if fs is None:
        raise DependencyMissingError("FileSystem", reason="Inject it at the entry point.")
    pending = resolve_latest_pending_snapshot(
        snapshot_root=Path(snapshot_root),
        dataset=SPONSOR_DATASET,
        fs=fs,
    )
    if pending is None:
        raise PendingAcquireSnapshotNotFoundError(
            SPONSOR_DATASET,
            str(snapshot_root),
            "uship admin refresh sponsor --only acquire",
        )
    return _finalise_sponsor_snapshot(
        paths=pending.paths,
        state=pending.state,
        fs=fs,
        command_line=command_line,
        progress=progress,
        now_fn=now_fn,
    )


def run_refresh_sponsor(
    *,
    url: str | None,
    snapshot_root: str | Path,
    fs: FileSystem | None = None,
    http_session: HttpSession | None = None,
    command_line: str,
    progress: ProgressReporter | None = None,
    now_fn: Callable[[], datetime] | None = None,
    source_page_url: str | None = None,
) -> RefreshSponsorResult:
    """Download, clean, and snapshot the sponsor register.

    Args:
        url: Direct CSV URL for the sponsor register. If omitted, resolves from GOV.UK.
        snapshot_root: Root directory for snapshots.
        fs: Filesystem dependency (required).
        http_session: HTTP session dependency (required).
        command_line: Command line string for manifest.
        progress: Optional progress reporter (CLI-owned).
        now_fn: Optional clock function for tests.
        source_page_url: Optional GOV.UK page URL for CSV discovery.

    Returns:
        RefreshSponsorResult with snapshot paths and counts.
    """
    acquired = run_refresh_sponsor_acquire(
        url=url,
        snapshot_root=snapshot_root,
        fs=fs,
        http_session=http_session,
        command_line=command_line,
        progress=progress,
        now_fn=now_fn,
        source_page_url=source_page_url,
    )
    state: PendingAcquireState = {
        "snapshot_date": acquired.paths.snapshot_date,
        "source_url": acquired.source_url,
        "downloaded_at_utc": acquired.downloaded_at_utc.isoformat(),
        "bytes_raw": acquired.bytes_raw,
    }
    return _finalise_sponsor_snapshot(
        paths=acquired.paths,
        state=state,
        fs=fs,
        command_line=command_line,
        progress=progress,
        now_fn=now_fn,
    )


def _finalise_sponsor_snapshot(
    *,
    paths: SnapshotPaths,
    state: PendingAcquireState,
    fs: FileSystem | None,
    command_line: str,
    progress: ProgressReporter | None,
    now_fn: Callable[[], datetime] | None,
) -> RefreshSponsorResult:
    if fs is None:
        raise DependencyMissingError("FileSystem", reason="Inject it at the entry point.")
    clock = now_fn or (lambda: datetime.now(UTC))
    raw_path = paths.staging_dir / "raw.csv"
    logger = get_logger("uk_sponsor_pipeline.refresh_sponsor")
    logger.info("Cleaning sponsor register: %s", raw_path)
    clean_path = paths.staging_dir / "clean.csv"
    stats_path = paths.staging_dir / "register_stats.json"
    register_result: TransformRegisterResult = run_transform_register(
        raw_dir=paths.staging_dir,
        out_path=clean_path,
        reports_dir=paths.staging_dir,
        fs=fs,
    )
    if progress is not None:
        progress.start("clean", register_result.unique_orgs)
        progress.advance(register_result.unique_orgs)
        progress.finish()
    row_counts: SnapshotRowCounts = {
        "raw": register_result.total_raw_rows,
        "clean": register_result.unique_orgs,
    }
    downloaded_at = datetime.fromisoformat(state["downloaded_at_utc"])
    sha_raw = _sha256(raw_path, fs)
    sha_clean = _sha256(clean_path, fs)
    last_updated = clock()
    manifest = build_snapshot_manifest(
        dataset=SPONSOR_DATASET,
        snapshot_date=state["snapshot_date"],
        source_url=state["source_url"],
        downloaded_at_utc=downloaded_at,
        last_updated_at_utc=last_updated,
        schema_version=SPONSOR_SCHEMA_VERSION,
        sha256_hash_raw=sha_raw,
        sha256_hash_clean=sha_clean,
        bytes_raw=state["bytes_raw"],
        row_counts=row_counts,
        artefacts={
            "raw": raw_path.name,
            "clean": clean_path.name,
            "register_stats": stats_path.name,
            "manifest": "manifest.json",
        },
        command_line=command_line,
        git_sha=None,
        tool_version=None,
    )
    manifest_path = paths.staging_dir / "manifest.json"
    fs.write_json(manifest, manifest_path)
    commit_snapshot(paths=paths, fs=fs)
    final_dir = paths.final_dir
    return RefreshSponsorResult(
        snapshot_dir=final_dir,
        snapshot_date=state["snapshot_date"],
        raw_path=final_dir / raw_path.name,
        clean_path=final_dir / clean_path.name,
        stats_path=final_dir / stats_path.name,
        manifest_path=final_dir / manifest_path.name,
        bytes_raw=state["bytes_raw"],
        row_counts=row_counts,
    )
