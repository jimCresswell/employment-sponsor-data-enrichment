"""Tests for register transform behavior."""

import json
from pathlib import Path

import pandas as pd

from uk_sponsor_pipeline.application.transform_register import run_transform_register
from uk_sponsor_pipeline.infrastructure.io.validation import validate_as


def test_transform_register_filters_and_aggregates(
    sample_raw_csv: pd.DataFrame, tmp_path: Path
) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    in_path = raw_dir / "input.csv"
    sample_raw_csv.to_csv(in_path, index=False)

    out_path = tmp_path / "interim" / "sponsor_register_filtered.csv"
    reports_dir = tmp_path / "reports"

    result = run_transform_register(raw_dir=raw_dir, out_path=out_path, reports_dir=reports_dir)

    df = pd.read_csv(out_path, dtype=str).fillna("")

    assert "org_name_normalized" in df.columns
    assert result.unique_orgs == 4  # 5 rows with 1 duplicate normalized

    acme = df[df["org_name_normalized"] == "acme software"].iloc[0]
    assert "ACME SOFTWARE LIMITED" in acme["raw_name_variants"]

    stats = validate_as(
        dict[str, object],
        json.loads((reports_dir / "register_stats.json").read_text()),
    )
    assert isinstance(stats.get("total_raw_rows"), int)
    assert isinstance(stats.get("filtered_rows"), int)
    assert isinstance(stats.get("unique_orgs_normalized"), int)
    assert stats["total_raw_rows"] == 5
    assert stats["filtered_rows"] == 5
    assert stats["unique_orgs_normalized"] == 4
