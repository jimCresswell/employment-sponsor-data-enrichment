# ADR 0009: Transform Enrich Matching and Audit Trail

Date: 2026-02-01

## Status

Accepted

## Context

Sponsor register names are noisy. Matching to Companies House requires a transparent, auditable process to justify how a match was selected and to inspect alternatives.

## Decision

Use a multi-variant query strategy with explicit scoring components. Persist the top candidates for each organisation to `companies_house_candidates_top3.csv` alongside the matched/unmatched outputs. Record match scores and confidence bands in the enriched output.

## Consequences

- Matching is explainable and reviewable.
- Ambiguous cases can be audited without re-running the API.
- Scoring thresholds can be tuned with evidence from the candidate trail.
