"""Tests for Companies House source behaviour."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from tests.fakes import InMemoryFileSystem
from uk_sponsor_pipeline.application.companies_house_bulk import CANONICAL_HEADERS_V1
from uk_sponsor_pipeline.application.companies_house_source import build_companies_house_source
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.exceptions import (
    CompaniesHouseFileProfileMissingError,
    MissingSnapshotPathError,
)
from uk_sponsor_pipeline.protocols import FileSystem


def _write_clean_csv(fs: FileSystem, path: Path) -> None:
    fs.write_text(",".join(CANONICAL_HEADERS_V1) + "\n", path)


def _write_profiles(fs: FileSystem, path: Path, rows: list[dict[str, str]]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CANONICAL_HEADERS_V1)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    fs.write_text(buffer.getvalue(), path)


def test_file_source_search_requires_two_token_hits(
    in_memory_fs: InMemoryFileSystem,
) -> None:
    snapshot_dir = Path("data/cache/snapshots/companies_house/2026-02-01")
    clean_path = snapshot_dir / "clean.csv"
    _write_clean_csv(in_memory_fs, clean_path)

    index_path = snapshot_dir / "index_tokens_a.csv"
    in_memory_fs.write_text(
        "token,company_number\nacme,11111111\nacme,22222222\nalpha,22222222\n",
        index_path,
    )

    profiles_path = snapshot_dir / "profiles_0-9.csv"
    _write_profiles(
        in_memory_fs,
        profiles_path,
        [
            {
                "company_number": "11111111",
                "company_name": "ACME LTD",
                "company_status": "active",
                "company_type": "ltd",
                "date_of_creation": "2015-01-01",
                "sic_codes": "62020",
                "address_locality": "London",
                "address_region": "Greater London",
                "address_postcode": "EC1A 1BB",
                "uri": "http://data.companieshouse.gov.uk/doc/company/11111111",
            },
            {
                "company_number": "22222222",
                "company_name": "ACME ALPHA LTD",
                "company_status": "active",
                "company_type": "ltd",
                "date_of_creation": "2016-01-01",
                "sic_codes": "62020",
                "address_locality": "London",
                "address_region": "Greater London",
                "address_postcode": "EC1A 1BB",
                "uri": "http://data.companieshouse.gov.uk/doc/company/22222222",
            },
        ],
    )

    config = PipelineConfig(
        ch_source_type="file",
        ch_clean_path=str(clean_path),
        ch_token_index_dir=str(snapshot_dir),
    )

    source = build_companies_house_source(
        config=config,
        fs=in_memory_fs,
        http_client=None,
        token_set={"acme", "alpha"},
    )

    results = source.search("Acme Alpha")
    assert [item["company_number"] for item in results] == ["22222222"]


def test_file_source_profile_missing_raises(
    in_memory_fs: InMemoryFileSystem,
) -> None:
    snapshot_dir = Path("data/cache/snapshots/companies_house/2026-02-01")
    clean_path = snapshot_dir / "clean.csv"
    _write_clean_csv(in_memory_fs, clean_path)

    index_path = snapshot_dir / "index_tokens_a.csv"
    in_memory_fs.write_text("token,company_number\nacme,11111111\n", index_path)

    profiles_path = snapshot_dir / "profiles_0-9.csv"
    _write_profiles(
        in_memory_fs,
        profiles_path,
        [
            {
                "company_number": "11111111",
                "company_name": "ACME LTD",
                "company_status": "active",
                "company_type": "ltd",
                "date_of_creation": "2015-01-01",
                "sic_codes": "62020",
                "address_locality": "London",
                "address_region": "Greater London",
                "address_postcode": "EC1A 1BB",
                "uri": "http://data.companieshouse.gov.uk/doc/company/11111111",
            }
        ],
    )

    config = PipelineConfig(
        ch_source_type="file",
        ch_clean_path=str(clean_path),
        ch_token_index_dir=str(snapshot_dir),
    )

    source = build_companies_house_source(
        config=config,
        fs=in_memory_fs,
        http_client=None,
        token_set={"acme"},
    )

    with pytest.raises(CompaniesHouseFileProfileMissingError):
        source.profile("99999999")


def test_file_source_requires_snapshot_paths(
    in_memory_fs: InMemoryFileSystem,
) -> None:
    config = PipelineConfig(ch_source_type="file")

    with pytest.raises(MissingSnapshotPathError):
        build_companies_house_source(
            config=config,
            fs=in_memory_fs,
            http_client=None,
            token_set={"acme"},
        )
