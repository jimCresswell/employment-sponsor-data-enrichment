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

from ..exceptions import (
    PendingAcquireSnapshotStateError,
    SnapshotAlreadyExistsError,
    SnapshotArtefactMissingError,
    SnapshotNotFoundError,
    SnapshotTimestampError,
)
from ..io_validation import IncomingDataError, validate_as
from ..protocols import FileSystem

_SNAPSHOT_DATE_PATTERN = re.compile(r"(20\d{2}-\d{2}-\d{2})")
_PENDING_FILENAME = "pending.json"


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


class PendingAcquireState(TypedDict):
    """Pending acquire metadata for staged refresh."""

    snapshot_date: str
    source_url: str
    downloaded_at_utc: str
    bytes_raw: int


@dataclass(frozen=True)
class PendingAcquireSnapshot:
    """Resolved pending acquire snapshot for clean-finalise."""

    paths: SnapshotPaths
    state: PendingAcquireState


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


def write_pending_acquire_state(
    *,
    paths: SnapshotPaths,
    source_url: str,
    downloaded_at_utc: datetime,
    bytes_raw: int,
    fs: FileSystem,
) -> Path:
    """Write pending acquire metadata into the staging directory."""
    payload: PendingAcquireState = {
        "snapshot_date": paths.snapshot_date,
        "source_url": source_url,
        "downloaded_at_utc": downloaded_at_utc.isoformat(),
        "bytes_raw": int(bytes_raw),
    }
    path = paths.staging_dir / _PENDING_FILENAME
    fs.write_json(payload, path)
    return path


def resolve_latest_pending_snapshot(
    *,
    snapshot_root: Path,
    dataset: str,
    fs: FileSystem,
) -> PendingAcquireSnapshot | None:
    """Return the latest pending acquire snapshot for dataset, if any."""
    dataset_dir = Path(snapshot_root) / dataset
    pending_paths = fs.list_files(dataset_dir, pattern=f".tmp-*/{_PENDING_FILENAME}")
    if not pending_paths:
        return None

    candidates: list[tuple[str, float, PendingAcquireSnapshot]] = []
    for pending_path in pending_paths:
        try:
            state = _read_pending_state(path=pending_path, fs=fs)
        except PendingAcquireSnapshotStateError:
            continue
        snapshot_date = state["snapshot_date"]
        staging_dir = pending_path.parent
        paths = SnapshotPaths(
            snapshot_root=Path(snapshot_root),
            dataset=dataset,
            snapshot_date=snapshot_date,
            final_dir=dataset_dir / snapshot_date,
            staging_dir=staging_dir,
        )
        candidates.append(
            (
                snapshot_date,
                fs.mtime(pending_path),
                PendingAcquireSnapshot(paths=paths, state=state),
            )
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def resolve_latest_snapshot_dir(
    *,
    snapshot_root: Path,
    dataset: str,
    fs: FileSystem,
) -> Path:
    dataset_dir = Path(snapshot_root) / dataset
    manifest_paths = fs.list_files(dataset_dir, pattern="*/manifest.json")
    candidates: list[tuple[str, float, Path]] = []
    for manifest_path in manifest_paths:
        snapshot_dir = manifest_path.parent
        snapshot_date = snapshot_dir.name
        if _SNAPSHOT_DATE_PATTERN.fullmatch(snapshot_date) is None:
            continue
        candidates.append((snapshot_date, fs.mtime(manifest_path), snapshot_dir))
    if not candidates:
        raise SnapshotNotFoundError(dataset, str(snapshot_root))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def resolve_latest_snapshot_path(
    *,
    snapshot_root: Path,
    dataset: str,
    filename: str,
    fs: FileSystem,
) -> Path:
    snapshot_dir = resolve_latest_snapshot_dir(
        snapshot_root=snapshot_root,
        dataset=dataset,
        fs=fs,
    )
    path = snapshot_dir / filename
    if not fs.exists(path):
        raise SnapshotArtefactMissingError(str(path))
    return path


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


def _read_pending_state(*, path: Path, fs: FileSystem) -> PendingAcquireState:
    payload = fs.read_json(path)
    try:
        state = validate_as(PendingAcquireState, payload)
    except IncomingDataError as exc:
        raise PendingAcquireSnapshotStateError(str(path)) from exc
    downloaded_at_raw = state["downloaded_at_utc"]
    try:
        downloaded_at = datetime.fromisoformat(downloaded_at_raw)
    except ValueError as exc:
        raise PendingAcquireSnapshotStateError(str(path)) from exc
    if downloaded_at.tzinfo is None:
        raise PendingAcquireSnapshotStateError(str(path))
    snapshot_date = state["snapshot_date"]
    if _SNAPSHOT_DATE_PATTERN.fullmatch(snapshot_date) is None:
        raise PendingAcquireSnapshotStateError(str(path))
    return state
