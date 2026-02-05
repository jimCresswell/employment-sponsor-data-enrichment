"""Snapshot helpers for cache-first refresh commands."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

import uk_sponsor_pipeline

from ..exceptions import SnapshotAlreadyExistsError, SnapshotTimestampError
from ..protocols import FileSystem

_SNAPSHOT_DATE_PATTERN = re.compile(r"(20\d{2}-\d{2}-\d{2})")


@dataclass(frozen=True)
class SnapshotPaths:
    """Resolved snapshot directories for a dataset/date."""

    snapshot_root: Path
    dataset: str
    snapshot_date: str
    final_dir: Path
    staging_dir: Path


class SnapshotRowCounts(TypedDict):
    """Row counts for raw and clean artefacts."""

    raw: int
    clean: int


class SnapshotManifest(TypedDict):
    """Snapshot manifest payload shape."""

    dataset: str
    snapshot_date: str
    source_url: str
    downloaded_at_utc: str
    last_updated_at_utc: str
    schema_version: str
    sha256_hash_raw: str
    sha256_hash_clean: str
    bytes_raw: int
    row_counts: SnapshotRowCounts
    artefacts: dict[str, str]
    git_sha: str
    tool_version: str
    command_line: str


def derive_snapshot_date(*, source_name: str, downloaded_at_utc: datetime) -> str:
    """Derive snapshot date from filename or download timestamp."""
    match = _SNAPSHOT_DATE_PATTERN.search(source_name)
    if match:
        return match.group(1)
    if downloaded_at_utc.tzinfo is None:
        raise SnapshotTimestampError("downloaded_at_utc")
    return downloaded_at_utc.astimezone(UTC).date().isoformat()


def start_snapshot_write(
    *,
    snapshot_root: Path,
    dataset: str,
    snapshot_date: str,
    fs: FileSystem,
    uuid_factory: Callable[[], str] | None = None,
) -> SnapshotPaths:
    """Create a staging directory for a snapshot write."""
    root = Path(snapshot_root)
    dataset_dir = root / dataset
    final_dir = dataset_dir / snapshot_date
    if fs.exists(final_dir):
        raise SnapshotAlreadyExistsError(dataset, snapshot_date)
    new_uuid = uuid_factory() if uuid_factory else uuid4().hex
    staging_dir = dataset_dir / f".tmp-{new_uuid}"
    fs.mkdir(staging_dir, parents=True)
    return SnapshotPaths(
        snapshot_root=root,
        dataset=dataset,
        snapshot_date=snapshot_date,
        final_dir=final_dir,
        staging_dir=staging_dir,
    )


def commit_snapshot(*, paths: SnapshotPaths, fs: FileSystem) -> None:
    """Atomically move a staging directory into place."""
    if fs.exists(paths.final_dir):
        raise SnapshotAlreadyExistsError(paths.dataset, paths.snapshot_date)
    fs.rename(paths.staging_dir, paths.final_dir)


def build_snapshot_manifest(
    *,
    dataset: str,
    snapshot_date: str,
    source_url: str,
    downloaded_at_utc: datetime,
    last_updated_at_utc: datetime,
    schema_version: str,
    sha256_hash_raw: str,
    sha256_hash_clean: str,
    bytes_raw: int,
    row_counts: SnapshotRowCounts,
    artefacts: dict[str, str],
    command_line: str,
    git_sha: str | None = None,
    tool_version: str | None = None,
) -> SnapshotManifest:
    """Build a snapshot manifest payload."""
    resolved_git_sha = _resolve_git_sha(git_sha)
    resolved_tool_version = _resolve_tool_version(tool_version)
    return {
        "dataset": dataset,
        "snapshot_date": snapshot_date,
        "source_url": source_url,
        "downloaded_at_utc": downloaded_at_utc.isoformat(),
        "last_updated_at_utc": last_updated_at_utc.isoformat(),
        "schema_version": schema_version,
        "sha256_hash_raw": sha256_hash_raw,
        "sha256_hash_clean": sha256_hash_clean,
        "bytes_raw": int(bytes_raw),
        "row_counts": row_counts,
        "artefacts": artefacts,
        "git_sha": resolved_git_sha,
        "tool_version": resolved_tool_version,
        "command_line": command_line,
    }


def _resolve_git_sha(override: str | None) -> str:
    if override:
        return override
    return os.getenv("GIT_SHA", "").strip() or "unknown"


def _resolve_tool_version(override: str | None) -> str:
    if override:
        return override
    raw = getattr(uk_sponsor_pipeline, "__version__", "")
    value = str(raw).strip()
    return value or "0.0.0+unknown"
