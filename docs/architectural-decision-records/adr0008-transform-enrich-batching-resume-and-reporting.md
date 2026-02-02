# ADR 0008: Transform Enrich Batching, Resume, and Reporting

Date: 2026-02-01

## Status

Accepted

## Context

Transform Enrich can take hours for large datasets and should be safe to interrupt and resume. Operators need visibility into progress and an easy way to restart.

## Decision

Transform Enrich processes input in batches with explicit controls (`batch_start`, `batch_count`, `batch_size`). Progress is recorded to:
- `companies_house_checkpoint.csv` (processed orgs)
- `companies_house_resume_report.json` (run metadata and timing)

The resume report includes timing, overall batch range, processed counts, and a prebuilt resume command.

Transform Enrich is fail‑fast on authentication, rate‑limit exhaustion, circuit breaker open, and unexpected HTTP errors (including profile fetch failures). Resumable artefacts are written before exit so operators can fix the issue and continue safely.

When `--no-resume` is used, Transform Enrich writes outputs into a new timestamped subdirectory under the chosen output directory to avoid stale data reuse.

## Consequences

- Long-running jobs can be resumed safely.
- Progress is auditable and measurable per run.
- Operators can slice runs to match rate limits or time windows.
- Errors are explicit and early; recovery is via `--resume` using the resume report command.
