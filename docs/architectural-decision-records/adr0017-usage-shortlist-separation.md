# ADR 0017: Usage Shortlist Separation

Date: 2026-02-02

## Status

Accepted

## Context

Transform Score previously produced both scored output and shortlisted/explain outputs. This mixed
ETL transformation with usage selection, which reduced reuse of scored artefacts and blurred the
usage boundary.

## Decision

Split scoring from usage filtering:

- Transform Score produces only `companies_scored.csv`.
- A new usage-shortlist step reads scored output, applies thresholds and geographic filters, and
  writes `companies_shortlist.csv` and `companies_explain.csv`.
- The CLI adds a `usage-shortlist` command, and `run-all` includes the usage step.

## Consequences

- Scored artefacts are immutable and reusable for different usage filters.
- Usage filters can run independently without recomputing scores.
- Transform and usage steps remain cleanly separated.
