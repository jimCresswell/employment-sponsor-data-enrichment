"""Tests for enrichment output audit helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.enrichment_audit_fixtures import fixture_names, write_enrichment_audit_fixture
from uk_sponsor_pipeline.devtools.enrichment_audit import (
    EnrichmentAuditError,
    EnrichmentAuditThresholds,
    audit_enrichment_outputs,
)


def test_fixture_names_are_stable() -> None:
    assert fixture_names() == (
        "valid_baseline",
        "duplicate_org_enriched",
        "overlap_between_sets",
        "missing_key_field",
        "low_similarity_spike",
        "non_active_spike",
        "shared_company_number_spike",
        "near_threshold_unmatched_spike",
    )


def test_audit_enrichment_outputs_accepts_valid_baseline(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    write_enrichment_audit_fixture(out_dir=out_dir, fixture_name="valid_baseline")

    result = audit_enrichment_outputs(out_dir)

    assert result.out_dir == out_dir
    assert result.metrics.enriched_rows == 2
    assert result.metrics.unmatched_rows == 1
    assert result.metrics.total_rows == 3
    assert result.threshold_breaches == ()


def test_audit_enrichment_outputs_raises_for_duplicate_organisation_names(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "processed"
    write_enrichment_audit_fixture(out_dir=out_dir, fixture_name="duplicate_org_enriched")

    with pytest.raises(
        EnrichmentAuditError, match="Duplicate organisations found in enriched output"
    ):
        audit_enrichment_outputs(out_dir)


def test_audit_enrichment_outputs_raises_for_overlap_between_outputs(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    write_enrichment_audit_fixture(out_dir=out_dir, fixture_name="overlap_between_sets")

    with pytest.raises(
        EnrichmentAuditError, match="Organisation overlap between enriched and unmatched outputs"
    ):
        audit_enrichment_outputs(out_dir)


def test_audit_enrichment_outputs_raises_for_missing_key_fields(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    write_enrichment_audit_fixture(out_dir=out_dir, fixture_name="missing_key_field")

    with pytest.raises(EnrichmentAuditError, match="Missing key fields in enriched output"):
        audit_enrichment_outputs(out_dir)


@pytest.mark.parametrize(
    ("fixture_name", "thresholds", "expected_breach"),
    [
        (
            "low_similarity_spike",
            EnrichmentAuditThresholds(max_low_similarity_matches=2),
            "low-similarity matches",
        ),
        (
            "non_active_spike",
            EnrichmentAuditThresholds(max_non_active_matches=2),
            "non-active matched companies",
        ),
        (
            "shared_company_number_spike",
            EnrichmentAuditThresholds(max_non_unique_company_number_rows=2),
            "rows sharing company numbers",
        ),
        (
            "near_threshold_unmatched_spike",
            EnrichmentAuditThresholds(max_near_threshold_unmatched=2),
            "near-threshold unmatched rows",
        ),
    ],
)
def test_audit_enrichment_outputs_reports_threshold_breaches(
    tmp_path: Path,
    fixture_name: str,
    thresholds: EnrichmentAuditThresholds,
    expected_breach: str,
) -> None:
    out_dir = tmp_path / "processed"
    write_enrichment_audit_fixture(out_dir=out_dir, fixture_name=fixture_name)

    result = audit_enrichment_outputs(out_dir, thresholds=thresholds)

    assert any(expected_breach in breach for breach in result.threshold_breaches)
