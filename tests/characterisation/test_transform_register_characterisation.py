"""Characterisation tests for Transform register outputs."""

from pathlib import Path

import pandas as pd

from tests.fakes import InMemoryFileSystem
from uk_sponsor_pipeline.application.transform_register import run_transform_register
from uk_sponsor_pipeline.schemas import TRANSFORM_REGISTER_OUTPUT_COLUMNS


def test_transform_register_output_schema_and_stats(
    sample_raw_csv: pd.DataFrame, in_memory_fs: InMemoryFileSystem
) -> None:
    raw_path = Path("data/raw/raw.csv")
    out_path = Path("data/interim/sponsor_register_filtered.csv")
    reports_dir = Path("reports")

    in_memory_fs.write_csv(sample_raw_csv, raw_path)

    result = run_transform_register(
        raw_dir=raw_path, out_path=out_path, reports_dir=reports_dir, fs=in_memory_fs
    )

    output_df = in_memory_fs.read_csv(out_path)
    assert list(output_df.columns) == list(TRANSFORM_REGISTER_OUTPUT_COLUMNS)
    assert result.unique_orgs == 4

    stats = in_memory_fs.read_json(reports_dir / "register_stats.json")
    assert isinstance(stats.get("total_raw_rows"), int)
    assert isinstance(stats.get("filtered_rows"), int)
    assert isinstance(stats.get("unique_orgs_normalized"), int)
    assert isinstance(stats.get("processed_at_utc"), str)
    assert stats["total_raw_rows"] == 5
    assert stats["filtered_rows"] == 5
    assert stats["unique_orgs_normalized"] == 4

    acme_row = output_df[output_df["org_name_normalized"] == "acme software"].iloc[0]
    assert "ACME SOFTWARE LIMITED" in acme_row["raw_name_variants"]
