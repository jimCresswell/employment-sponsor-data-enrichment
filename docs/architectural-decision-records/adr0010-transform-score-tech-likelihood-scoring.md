# ADR 0010: Transform Score Tech-Likelihood Scoring

Date: 2026-02-01

## Status

Accepted

## Context

The pipeline needs an explainable mechanism to rank companies by likelihood of hiring for target
job types. A single signal is insufficient and can bias results. This ADR records the initial
tech-role scoring profile used for early delivery.

## Decision

Use a multi-feature scoring model based on Companies House profile data and name heuristics.
Features include SIC codes, company status, company age, company type, and name keywords.
Company age uses a UTC-based clock to avoid naive datetime usage. The initial profile outputs a
tech-likelihood score and a bucketed classification (strong/possible/unlikely).
The scoring rules live in the domain layer (`domain/scoring.py`) and are invoked by the Transform Score application use-case. Shortlist and explain outputs are produced by the usage-shortlist step, which applies thresholds and geographic filters to the scored artefact.

## Consequences

- Rankings are explainable and feature-driven.
- Scores can be tuned with minimal structural changes.
- Output supports both filtered shortlists (via usage) and broader reviews (scored artefact).
- Future profile work can extend beyond tech-only scoring without replacing this architecture.
