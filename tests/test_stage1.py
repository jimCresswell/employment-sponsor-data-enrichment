"""Tests for Stage 1 pipeline behavior."""

import json

import pandas as pd

from uk_sponsor_pipeline.stages.stage1 import run_stage1


def test_stage1_filters_and_aggregates(sample_raw_csv, tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    in_path = raw_dir / "input.csv"
    sample_raw_csv.to_csv(in_path, index=False)

    out_path = tmp_path / "interim" / "stage1.csv"
    reports_dir = tmp_path / "reports"

    result = run_stage1(raw_dir=raw_dir, out_path=out_path, reports_dir=reports_dir)

    df = pd.read_csv(out_path, dtype=str).fillna("")

    assert "org_name_normalized" in df.columns
    assert result.unique_orgs == 4  # 5 rows with 1 duplicate normalized

    acme = df[df["org_name_normalized"] == "acme software"].iloc[0]
    assert "ACME SOFTWARE LIMITED" in acme["raw_name_variants"]

    stats = json.loads((reports_dir / "stage1_stats.json").read_text())
    assert stats["total_raw_rows"] == 5
    assert stats["filtered_rows"] == 5
    assert stats["unique_orgs_normalized"] == 4
