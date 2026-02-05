"""Refresh sponsor register snapshot (cache-first)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from ..exceptions import DependencyMissingError
from ..observability import get_logger
from ..protocols import FileSystem, HttpSession, ProgressReporter
from .snapshots import (
    SnapshotRowCounts,
    build_snapshot_manifest,
    commit_snapshot,
    derive_snapshot_date,
    start_snapshot_write,
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


def _sha256(path: Path, fs: FileSystem) -> str:
    return hashlib.sha256(fs.read_bytes(path)).hexdigest()


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

    sha_raw = _sha256(raw_path, fs)
    sha_clean = _sha256(clean_path, fs)
    last_updated = clock()

    manifest = build_snapshot_manifest(
        dataset=SPONSOR_DATASET,
        snapshot_date=snapshot_date,
        source_url=resolved_url,
        downloaded_at_utc=downloaded_at,
        last_updated_at_utc=last_updated,
        schema_version=SPONSOR_SCHEMA_VERSION,
        sha256_hash_raw=sha_raw,
        sha256_hash_clean=sha_clean,
        bytes_raw=bytes_downloaded,
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
        snapshot_date=snapshot_date,
        raw_path=final_dir / raw_path.name,
        clean_path=final_dir / clean_path.name,
        stats_path=final_dir / stats_path.name,
        manifest_path=final_dir / manifest_path.name,
        bytes_raw=bytes_downloaded,
        row_counts=row_counts,
    )
