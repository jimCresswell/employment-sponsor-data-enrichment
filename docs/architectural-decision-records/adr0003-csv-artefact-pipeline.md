# ADR 0003: CSV Artefact Pipeline

Date: 2026-02-01

## Status

Superseded by ADR 0012

## Context

The sponsor register and Companies House data must be processed in a transparent, auditable way. The outputs need to be easy to inspect, re-run, and compare between runs.

## Decision

Use a step-based pipeline with CSV artefacts at each boundary:
- Extract → raw CSV
- Transform Register → filtered + aggregated CSV
- Transform Enrich → enriched CSVs (matched, unmatched, candidates)
- Transform Score → scored and shortlisted CSVs

Artifacts are stored under `data/raw`, `data/interim`, and `data/processed`.

## Consequences

- The pipeline is reproducible and auditable.
- Intermediate data can be validated and inspected.
- Storage is simple and tool-agnostic (CSV-based).
- Steps are treated as artefact boundaries, not architectural boundaries (see ADR 0012).
