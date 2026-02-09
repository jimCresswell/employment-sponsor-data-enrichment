# Performance Improvement Plan (File-First Runtime)

Date: 2026-02-08

## Objective

Reduce wall-clock runtime for `transform-enrich` while preserving deterministic output
contracts and fail-fast behaviour.

## Current Baseline

- Live snapshot run (sponsor `2026-02-06`, Companies House `2026-02-01`):
  - `transform-enrich`: `44m52s` for `119,109` sponsor organisations.
  - `transform-score` and `usage-shortlist`: materially faster and not the primary bottleneck.
- Primary bottleneck remains enrich matching and profile lookup throughput.

## Scope and Guardrails

1. Preserve output contracts:
   - `sponsor_enriched.csv`
   - `sponsor_unmatched.csv`
   - `sponsor_match_candidates_top3.csv`
   - `sponsor_enrich_checkpoint.csv`
   - `sponsor_enrich_resume_report.json`
2. Preserve deterministic behaviour (same inputs/config -> same ordered outputs).
3. Preserve file-first runtime and network-isolated tests.
4. Treat runtime quality as correctness, not optional optimisation.

## Improvement Tracks

### Track A: Incremental Improvements (Lower Risk)

1. Query-level result memoisation:
   - Cache `source.search(query)` results within run scope.
   - Avoid repeated candidate scoring for repeated query variants.
   - Expected impact: incremental (`~5-15%`).
2. Match pre-computation and normalisation reuse:
   - Precompute normalised organisation/query variants once per row.
   - Reduce repeated string processing in inner loops.
   - Expected impact: incremental (`~5-10%`).
3. Write-path optimisation:
   - Reduce repeated DataFrame conversions in batch flush paths.
   - Keep append and finalise passes deterministic.
   - Expected impact: incremental (`~5-15%`).

### Track B: Throughput Improvements (Higher Impact)

1. Deterministic worker parallelism for enrich:
   - Partition sponsor rows deterministically.
   - Run workers in parallel and merge outputs by stable sort key.
   - Expected impact: serious (`~1.5-3x`, machine dependent).
2. Refresh-time profile offset index (Option 2):
   - Build company-number -> row offset index during Companies House clean/index phase.
   - Enable direct profile seeks instead of bucket CSV scans.
   - Expected impact: serious for lookup-heavy runs (`~2-4x` potential on enrich stage).
3. Persistent lookup cache for reruns on unchanged snapshots:
   - Optional cache keyed by snapshot hash + query/company number.
   - Primarily benefits repeated reruns.
   - Expected impact: serious for rerun workflows, limited for single-run workflows.

### Track C: Optional Format and IO Changes

1. Columnar artefact path for processed outputs (optional):
   - Add optional Parquet write/read path for internal processing speed.
   - Keep CSV outputs as the published contract surface.
   - Expected impact: situational; requires careful compatibility handling.

## Execution Order

1. Implement Track A fully and re-benchmark.
2. If target runtime is still not met, implement Track B in order:
   - parallelism first,
   - then offset index,
   - then persistent rerun cache if needed.
3. Consider Track C only after Track A/B outcomes are measured.

## Acceptance Metrics

1. Runtime:
   - End-to-end Step 4 (`transform-enrich` -> `transform-score` -> `usage-shortlist`) completes unattended within agreed SLA on baseline hardware.
2. Correctness:
   - No contract drift in validation scripts.
   - Deterministic row ordering and stable counts across repeated runs on unchanged snapshots.
3. Quality:
   - `scripts/validation_audit_enrichment.py` metrics do not regress beyond agreed thresholds.
4. Engineering gates:
   - `uv run check` passes.

