"""Audit transform-enrich outputs for structural and quality risks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from uk_sponsor_pipeline.devtools.enrichment_audit import (
    EnrichmentAuditError,
    EnrichmentAuditThresholds,
    audit_enrichment_outputs,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit transform-enrich output quality and matching risk signals.",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        type=Path,
        help="Processed output directory to audit.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when warning thresholds are exceeded.",
    )
    parser.add_argument(
        "--low-similarity-threshold",
        type=float,
        default=0.60,
        help="Name similarity threshold used to count low-similarity matches.",
    )
    parser.add_argument(
        "--max-low-similarity-matches",
        type=int,
        default=300,
        help="Maximum allowed low-similarity matched rows before warning.",
    )
    parser.add_argument(
        "--near-threshold-cutoff",
        type=float,
        default=0.70,
        help="Best candidate score cutoff for near-threshold unmatched rows.",
    )
    parser.add_argument(
        "--max-near-threshold-unmatched",
        type=int,
        default=1500,
        help="Maximum allowed near-threshold unmatched rows before warning.",
    )
    parser.add_argument(
        "--max-non-active-matches",
        type=int,
        default=3000,
        help="Maximum allowed non-active matched rows before warning.",
    )
    parser.add_argument(
        "--max-non-unique-company-number-rows",
        type=int,
        default=2000,
        help="Maximum allowed rows that share Companies House company numbers.",
    )
    args = parser.parse_args(argv)

    thresholds = EnrichmentAuditThresholds(
        low_similarity_threshold=args.low_similarity_threshold,
        max_low_similarity_matches=args.max_low_similarity_matches,
        near_threshold_cutoff=args.near_threshold_cutoff,
        max_near_threshold_unmatched=args.max_near_threshold_unmatched,
        max_non_active_matches=args.max_non_active_matches,
        max_non_unique_company_number_rows=args.max_non_unique_company_number_rows,
    )

    try:
        result = audit_enrichment_outputs(args.out_dir, thresholds=thresholds)
    except EnrichmentAuditError as exc:
        print(f"FAIL enrichment audit: {exc}", file=sys.stderr)
        return 1

    metrics = result.metrics
    print(f"PASS enrichment audit: {result.out_dir}")
    print(f"- enriched rows: {metrics.enriched_rows}")
    print(f"- unmatched rows: {metrics.unmatched_rows}")
    print(f"- low-similarity matches (< {thresholds.low_similarity_threshold:.2f}): {metrics.low_similarity_matches}")
    print(f"- non-active matched companies: {metrics.non_active_matches}")
    print(f"- shared-company-number rows: {metrics.non_unique_company_number_rows}")
    print(
        "- near-threshold unmatched "
        f"(>= {thresholds.near_threshold_cutoff:.2f}): {metrics.near_threshold_unmatched}"
    )

    if not result.threshold_breaches:
        return 0

    for breach in result.threshold_breaches:
        print(f"WARN enrichment audit: {breach}", file=sys.stderr)

    if args.strict:
        print("FAIL enrichment audit: threshold breaches detected in strict mode.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

