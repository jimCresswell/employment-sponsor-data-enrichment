# ADR 0003: Stage-Based CSV Pipeline

Date: 2026-02-01

## Status

Superseded by ADR 0012

## Context

The sponsor register and Companies House data must be processed in a transparent, auditable way. The outputs need to be easy to inspect, re-run, and compare between runs.

## Decision

Use a staged pipeline with CSV artefacts at each stage:
- Download → raw CSV
- Stage 1 → filtered + aggregated CSV
- Stage 2 → enriched CSVs (matched, unmatched, candidates)
- Stage 3 → scored and shortlisted CSVs

Artifacts are stored under `data/raw`, `data/interim`, and `data/processed`.

## Consequences

- The pipeline is reproducible and auditable.
- Intermediate data can be validated and inspected.
- Storage is simple and tool-agnostic (CSV-based).
- Stages are now treated as artefact boundaries, not architectural boundaries (see ADR 0012).
