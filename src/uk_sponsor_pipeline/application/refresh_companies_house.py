"""Refresh Companies House bulk snapshot (cache-first)."""

from __future__ import annotations

import csv
import hashlib
import shutil
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO
from urllib.parse import urlparse

from ..exceptions import (
    CompaniesHouseCsvEmptyError,
    CompaniesHouseZipMissingCsvError,
    DependencyMissingError,
)
from ..observability import get_logger
from ..protocols import FileSystem, HttpSession, ProgressReporter
from .companies_house_bulk import (
    CANONICAL_HEADERS_V1,
    clean_companies_house_row,
    normalise_raw_headers,
    validate_raw_headers,
)
from .companies_house_index import bucket_for_token, tokenise_company_name
from .snapshots import (
    SnapshotRowCounts,
    build_snapshot_manifest,
    commit_snapshot,
    derive_snapshot_date,
    start_snapshot_write,
)
from .source_links import COMPANIES_HOUSE_SOURCE_PAGE_URL, resolve_companies_house_zip_url

CH_DATASET = "companies_house"
CH_SCHEMA_VERSION = "ch_clean_v1"


@dataclass(frozen=True)
class RefreshCompaniesHouseResult:
    """Result of refresh-companies-house snapshot generation."""

    snapshot_dir: Path
    snapshot_date: str
    raw_path: Path
    clean_path: Path
    manifest_path: Path
    index_paths: tuple[Path, ...]
    profile_paths: tuple[Path, ...]
    bytes_raw: int
    row_counts: SnapshotRowCounts


class _TokenIndexWriter:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._handles: dict[str, TextIO] = {}
        self._paths: list[Path] = []

    def write(self, company_name: str, company_number: str) -> None:
        tokens = tokenise_company_name(company_name)
        for token in tokens:
            bucket = bucket_for_token(token)
            handle = self._handle(bucket)
            handle.write(f"{token},{company_number}\n")

    def _handle(self, bucket: str) -> TextIO:
        if bucket in self._handles:
            return self._handles[bucket]
        path = self._base_dir / f"index_tokens_{bucket}.csv"
        handle = path.open("w", encoding="utf-8", newline="")
        handle.write("token,company_number\n")
        self._handles[bucket] = handle
        self._paths.append(path)
        return handle

    def close(self) -> tuple[Path, ...]:
        for handle in self._handles.values():
            handle.close()
        return tuple(self._paths)


class _ProfileBucketWriter:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._handles: dict[str, TextIO] = {}
        self._writers: dict[str, csv.DictWriter[str]] = {}
        self._paths: list[Path] = []

    def write(self, row: dict[str, str]) -> None:
        bucket = bucket_for_token(row["company_number"])
        writer = self._writer(bucket)
        writer.writerow(row)

    def _writer(self, bucket: str) -> csv.DictWriter[str]:
        if bucket in self._writers:
            return self._writers[bucket]
        path = self._base_dir / f"profiles_{bucket}.csv"
        handle = path.open("w", encoding="utf-8", newline="")
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_HEADERS_V1)
        writer.writeheader()
        self._handles[bucket] = handle
        self._writers[bucket] = writer
        self._paths.append(path)
        return writer

    def close(self) -> tuple[Path, ...]:
        for handle in self._handles.values():
            handle.close()
        return tuple(self._paths)


def _sha256(path: Path, fs: FileSystem) -> str:
    return hashlib.sha256(fs.read_bytes(path)).hexdigest()


def _download_stream(
    *,
    url: str,
    dest: Path,
    http_session: HttpSession,
    fs: FileSystem,
    progress: ProgressReporter | None,
) -> int:
    bytes_downloaded = 0

    if progress is not None:
        progress.start("download", None)

    def stream() -> Iterable[bytes]:
        nonlocal bytes_downloaded
        for chunk in http_session.iter_bytes(url, timeout_seconds=300, chunk_size=1024 * 64):
            bytes_downloaded += len(chunk)
            if progress is not None:
                progress.advance(len(chunk))
            yield chunk

    fs.write_bytes_stream(dest, stream())
    if progress is not None:
        progress.finish()
    return bytes_downloaded


def _extract_zip(zip_path: Path, csv_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_members:
            raise CompaniesHouseZipMissingCsvError()
        member = csv_members[0]
        with archive.open(member) as source, csv_path.open("wb") as target:
            shutil.copyfileobj(source, target)


def run_refresh_companies_house(
    *,
    url: str | None,
    snapshot_root: str | Path,
    fs: FileSystem | None = None,
    http_session: HttpSession | None = None,
    command_line: str,
    progress: ProgressReporter | None = None,
    now_fn: Callable[[], datetime] | None = None,
    source_page_url: str | None = None,
) -> RefreshCompaniesHouseResult:
    """Download, clean, and snapshot Companies House bulk data.

    Args:
        url: Direct ZIP URL for Companies House bulk data. If omitted, resolves from the
            Companies House download page.
        snapshot_root: Root directory for snapshots.
        fs: Filesystem dependency (required).
        http_session: HTTP session dependency (required).
        command_line: Command line string for manifest.
        progress: Optional progress reporter (CLI-owned).
        now_fn: Optional clock function for tests.
        source_page_url: Optional Companies House download page URL for ZIP discovery.

    Returns:
        RefreshCompaniesHouseResult with snapshot paths and counts.
    """
    if fs is None:
        raise DependencyMissingError("FileSystem", reason="Inject it at the entry point.")
    if http_session is None:
        raise DependencyMissingError("HttpSession", reason="Inject it at the entry point.")

    clock = now_fn or (lambda: datetime.now(UTC))
    downloaded_at = clock()

    resolved_url = resolve_companies_house_zip_url(
        http_session=http_session,
        url=url,
        source_page_url=source_page_url or COMPANIES_HOUSE_SOURCE_PAGE_URL,
    )

    source_name = Path(urlparse(resolved_url).path).name or "companies_house.csv"
    snapshot_date = derive_snapshot_date(
        source_name=source_name,
        downloaded_at_utc=downloaded_at,
    )

    paths = start_snapshot_write(
        snapshot_root=Path(snapshot_root),
        dataset=CH_DATASET,
        snapshot_date=snapshot_date,
        fs=fs,
    )

    logger = get_logger("uk_sponsor_pipeline.refresh_companies_house")
    logger.info("Downloading Companies House bulk data: %s", resolved_url)

    is_zip = resolved_url.lower().endswith(".zip")
    raw_name = "raw.zip" if is_zip else "raw.csv"
    raw_path = paths.staging_dir / raw_name

    bytes_downloaded = _download_stream(
        url=resolved_url,
        dest=raw_path,
        http_session=http_session,
        fs=fs,
        progress=progress,
    )

    raw_csv_path = raw_path
    if is_zip:
        raw_csv_path = paths.staging_dir / "raw.csv"
        _extract_zip(raw_path, raw_csv_path)

    clean_path = paths.staging_dir / "clean.csv"

    raw_rows = 0
    clean_rows = 0

    logger.info("Cleaning Companies House bulk CSV: %s", raw_csv_path)
    index_writer = _TokenIndexWriter(paths.staging_dir)
    profile_writer = _ProfileBucketWriter(paths.staging_dir)
    index_paths: tuple[Path, ...] = ()
    profile_paths: tuple[Path, ...] = ()

    try:
        if progress is not None:
            progress.start("clean", None)
        with raw_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header_row = next(reader, None)
            if header_row is None:
                raise CompaniesHouseCsvEmptyError()
            trimmed_headers = normalise_raw_headers(header_row)
            validate_raw_headers(trimmed_headers)

            dict_reader = csv.DictReader(handle, fieldnames=trimmed_headers)
            with clean_path.open("w", encoding="utf-8", newline="") as clean_file:
                writer = csv.DictWriter(clean_file, fieldnames=CANONICAL_HEADERS_V1)
                writer.writeheader()
                for row in dict_reader:
                    raw_rows += 1
                    raw_row = {key: (value or "") for key, value in row.items()}
                    clean_row = clean_companies_house_row(raw_row)
                    writer.writerow(clean_row)
                    clean_rows += 1
                    if progress is not None:
                        progress.advance(1)
                    index_writer.write(clean_row["company_name"], clean_row["company_number"])
                    profile_writer.write(clean_row)
    finally:
        index_paths = index_writer.close()
        profile_paths = profile_writer.close()
        if progress is not None:
            progress.finish()

    if progress is not None:
        progress.start("index", clean_rows)
        progress.advance(clean_rows)
        progress.finish()

    row_counts: SnapshotRowCounts = {"raw": raw_rows, "clean": clean_rows}

    sha_raw = _sha256(raw_path, fs)
    sha_clean = _sha256(clean_path, fs)
    last_updated = clock()

    artefacts: dict[str, str] = {
        "raw": raw_path.name,
        "clean": clean_path.name,
    }
    for path in index_paths:
        artefacts[path.name] = path.name
    for path in profile_paths:
        artefacts[path.name] = path.name
    if is_zip:
        artefacts["raw_csv"] = raw_csv_path.name

    manifest = build_snapshot_manifest(
        dataset=CH_DATASET,
        snapshot_date=snapshot_date,
        source_url=resolved_url,
        downloaded_at_utc=downloaded_at,
        last_updated_at_utc=last_updated,
        schema_version=CH_SCHEMA_VERSION,
        sha256_hash_raw=sha_raw,
        sha256_hash_clean=sha_clean,
        bytes_raw=bytes_downloaded,
        row_counts=row_counts,
        artefacts=artefacts,
        command_line=command_line,
        git_sha=None,
        tool_version=None,
    )

    manifest_path = paths.staging_dir / "manifest.json"
    fs.write_json(manifest, manifest_path)

    commit_snapshot(paths=paths, fs=fs)

    final_dir = paths.final_dir
    final_index_paths = tuple(final_dir / path.name for path in index_paths)
    return RefreshCompaniesHouseResult(
        snapshot_dir=final_dir,
        snapshot_date=snapshot_date,
        raw_path=final_dir / raw_path.name,
        clean_path=final_dir / clean_path.name,
        manifest_path=final_dir / manifest_path.name,
        index_paths=final_index_paths,
        profile_paths=tuple(final_dir / path.name for path in profile_paths),
        bytes_raw=bytes_downloaded,
        row_counts=row_counts,
    )
