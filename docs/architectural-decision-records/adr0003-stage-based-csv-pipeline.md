# ADR 0003: Stage-Based CSV Pipeline

Date: 2026-02-01

## Status

Accepted

## Context

The sponsor register and Companies House data must be processed in a transparent, auditable way. The outputs need to be easy to inspect, re-run, and compare between runs.

## Decision

Use a staged pipeline with CSV artifacts at each stage:
- Download → raw CSV
- Stage 1 → filtered + aggregated CSV
- Stage 2 → enriched CSVs (matched, unmatched, candidates)
- Stage 3 → scored and shortlisted CSVs

Artifacts are stored under `data/raw`, `data/interim`, and `data/processed`.

## Consequences

- The pipeline is reproducible and auditable.
- Intermediate data can be validated and inspected.
- Storage is simple and tool-agnostic (CSV-based).
