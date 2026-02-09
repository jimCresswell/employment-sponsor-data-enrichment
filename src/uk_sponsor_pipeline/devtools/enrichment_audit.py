"""Audit helpers for transform-enrich output quality checks."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_REQUIRED_ENRICH_COLUMNS: tuple[str, ...] = (
    "Organisation Name",
    "ch_company_number",
    "ch_company_name",
    "ch_company_status",
    "match_score",
    "score_name_similarity",
)
_REQUIRED_UNMATCHED_COLUMNS: tuple[str, ...] = (
    "Organisation Name",
    "best_candidate_score",
)


class EnrichmentAuditError(ValueError):
    """Raised when enrichment audit checks fail."""


@dataclass(frozen=True)
class EnrichmentAuditThresholds:
    """Warning thresholds for enrichment output quality metrics."""

    low_similarity_threshold: float = 0.60
    max_low_similarity_matches: int = 300
    near_threshold_cutoff: float = 0.70
    max_near_threshold_unmatched: int = 1500
    max_non_active_matches: int = 3000
    max_non_unique_company_number_rows: int = 2000


@dataclass(frozen=True)
class EnrichmentAuditMetrics:
    """Computed enrichment quality metrics."""

    enriched_rows: int
    unmatched_rows: int
    total_rows: int
    duplicate_org_enriched: int
    duplicate_org_unmatched: int
    overlap_org_between_sets: int
    missing_ch_company_number: int
    missing_ch_company_name: int
    missing_match_score: int
    missing_score_name_similarity: int
    low_similarity_matches: int
    non_active_matches: int
    non_unique_company_number_rows: int
    near_threshold_unmatched: int


@dataclass(frozen=True)
class EnrichmentAuditResult:
    """Result payload for enrichment quality checks."""

    out_dir: Path
    metrics: EnrichmentAuditMetrics
    threshold_breaches: tuple[str, ...]


def audit_enrichment_outputs(
    out_dir: str | Path,
    *,
    thresholds: EnrichmentAuditThresholds | None = None,
) -> EnrichmentAuditResult:
    """Audit transform-enrich output files for structural and quality risks."""
    root = Path(out_dir)
    enrich_path = root / "sponsor_enriched.csv"
    unmatched_path = root / "sponsor_unmatched.csv"
    _require_file(enrich_path)
    _require_file(unmatched_path)

    active_thresholds = thresholds if thresholds is not None else EnrichmentAuditThresholds()
    enrich_rows = _read_csv_rows(path=enrich_path, required_columns=_REQUIRED_ENRICH_COLUMNS)
    unmatched_rows = _read_csv_rows(
        path=unmatched_path, required_columns=_REQUIRED_UNMATCHED_COLUMNS
    )
    metrics = _build_metrics(
        enrich_rows=enrich_rows,
        unmatched_rows=unmatched_rows,
        thresholds=active_thresholds,
    )
    _validate_structural_metrics(metrics)

    threshold_breaches = _build_threshold_breaches(metrics=metrics, thresholds=active_thresholds)
    return EnrichmentAuditResult(
        out_dir=root,
        metrics=metrics,
        threshold_breaches=threshold_breaches,
    )


def _require_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        message = f"Required enrichment output file is missing: {path}"
        raise EnrichmentAuditError(message)


def _read_csv_rows(*, path: Path, required_columns: tuple[str, ...]) -> tuple[dict[str, str], ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            message = f"CSV is empty or missing header: {path}"
            raise EnrichmentAuditError(message)
        present = {name.strip() for name in reader.fieldnames}
        missing = sorted(set(required_columns) - present)
        if missing:
            message = f"Missing required columns in {path.name}: {missing}"
            raise EnrichmentAuditError(message)
        rows = tuple(
            {key: (value if value is not None else "") for key, value in row.items()}
            for row in reader
        )
    return rows


def _build_metrics(
    *,
    enrich_rows: tuple[dict[str, str], ...],
    unmatched_rows: tuple[dict[str, str], ...],
    thresholds: EnrichmentAuditThresholds,
) -> EnrichmentAuditMetrics:
    enrich_orgs = tuple((row.get("Organisation Name") or "").strip() for row in enrich_rows)
    unmatched_orgs = tuple((row.get("Organisation Name") or "").strip() for row in unmatched_rows)
    duplicate_org_enriched = _duplicate_count(enrich_orgs)
    duplicate_org_unmatched = _duplicate_count(unmatched_orgs)
    overlap_org_between_sets = len(set(enrich_orgs) & set(unmatched_orgs))

    missing_ch_company_number = sum(
        1 for row in enrich_rows if not _has_text(row, "ch_company_number")
    )
    missing_ch_company_name = sum(1 for row in enrich_rows if not _has_text(row, "ch_company_name"))
    missing_match_score = sum(1 for row in enrich_rows if not _has_text(row, "match_score"))
    missing_score_name_similarity = sum(
        1 for row in enrich_rows if not _has_text(row, "score_name_similarity")
    )

    low_similarity_matches = 0
    non_active_matches = 0
    company_numbers: list[str] = []
    for row in enrich_rows:
        score = _parse_float(value=row["score_name_similarity"], label="score_name_similarity")
        if score < thresholds.low_similarity_threshold:
            low_similarity_matches += 1
        status = (row.get("ch_company_status") or "").strip().lower()
        if status != "active":
            non_active_matches += 1
        company_number = (row.get("ch_company_number") or "").strip()
        if company_number:
            company_numbers.append(company_number)
    counter = Counter(company_numbers)
    non_unique_company_number_rows = sum(count for count in counter.values() if count > 1)

    near_threshold_unmatched = 0
    for row in unmatched_rows:
        raw = (row.get("best_candidate_score") or "").strip()
        if not raw:
            continue
        score = _parse_float(value=raw, label="best_candidate_score")
        if score >= thresholds.near_threshold_cutoff:
            near_threshold_unmatched += 1

    return EnrichmentAuditMetrics(
        enriched_rows=len(enrich_rows),
        unmatched_rows=len(unmatched_rows),
        total_rows=len(enrich_rows) + len(unmatched_rows),
        duplicate_org_enriched=duplicate_org_enriched,
        duplicate_org_unmatched=duplicate_org_unmatched,
        overlap_org_between_sets=overlap_org_between_sets,
        missing_ch_company_number=missing_ch_company_number,
        missing_ch_company_name=missing_ch_company_name,
        missing_match_score=missing_match_score,
        missing_score_name_similarity=missing_score_name_similarity,
        low_similarity_matches=low_similarity_matches,
        non_active_matches=non_active_matches,
        non_unique_company_number_rows=non_unique_company_number_rows,
        near_threshold_unmatched=near_threshold_unmatched,
    )


def _duplicate_count(values: tuple[str, ...]) -> int:
    return sum(count - 1 for count in Counter(values).values() if count > 1)


def _has_text(row: dict[str, str], key: str) -> bool:
    return bool((row.get(key) or "").strip())


def _parse_float(*, value: str, label: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        message = f"{label} must be numeric in enrichment outputs: got '{value}'"
        raise EnrichmentAuditError(message) from exc


def _validate_structural_metrics(metrics: EnrichmentAuditMetrics) -> None:
    if metrics.duplicate_org_enriched > 0:
        message = "Duplicate organisations found in enriched output."
        raise EnrichmentAuditError(message)
    if metrics.duplicate_org_unmatched > 0:
        message = "Duplicate organisations found in unmatched output."
        raise EnrichmentAuditError(message)
    if metrics.overlap_org_between_sets > 0:
        message = "Organisation overlap between enriched and unmatched outputs."
        raise EnrichmentAuditError(message)

    missing_fields: list[str] = []
    if metrics.missing_ch_company_number > 0:
        missing_fields.append("ch_company_number")
    if metrics.missing_ch_company_name > 0:
        missing_fields.append("ch_company_name")
    if metrics.missing_match_score > 0:
        missing_fields.append("match_score")
    if metrics.missing_score_name_similarity > 0:
        missing_fields.append("score_name_similarity")
    if missing_fields:
        message = f"Missing key fields in enriched output: {missing_fields}"
        raise EnrichmentAuditError(message)


def _build_threshold_breaches(
    *,
    metrics: EnrichmentAuditMetrics,
    thresholds: EnrichmentAuditThresholds,
) -> tuple[str, ...]:
    breaches: list[str] = []
    if metrics.low_similarity_matches > thresholds.max_low_similarity_matches:
        breaches.append(
            "Too many low-similarity matches: "
            f"{metrics.low_similarity_matches} > {thresholds.max_low_similarity_matches} "
            f"(threshold: {thresholds.low_similarity_threshold:.2f})."
        )
    if metrics.non_active_matches > thresholds.max_non_active_matches:
        breaches.append(
            "Too many non-active matched companies: "
            f"{metrics.non_active_matches} > {thresholds.max_non_active_matches}."
        )
    if metrics.non_unique_company_number_rows > thresholds.max_non_unique_company_number_rows:
        breaches.append(
            "Too many rows sharing company numbers: "
            f"{metrics.non_unique_company_number_rows} > "
            f"{thresholds.max_non_unique_company_number_rows}."
        )
    if metrics.near_threshold_unmatched > thresholds.max_near_threshold_unmatched:
        breaches.append(
            "Too many near-threshold unmatched rows: "
            f"{metrics.near_threshold_unmatched} > "
            f"{thresholds.max_near_threshold_unmatched} "
            f"(cutoff: {thresholds.near_threshold_cutoff:.2f})."
        )
    return tuple(breaches)
