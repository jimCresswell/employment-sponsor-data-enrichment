# ADR 0010: Stage 3 Tech-Likelihood Scoring

Date: 2026-02-01

## Status

Accepted

## Context

The pipeline needs an explainable mechanism to rank companies by likelihood of hiring senior engineers. A single signal is insufficient and can bias results.

## Decision

Use a multi-feature scoring model based on Companies House profile data and name heuristics. Features include SIC codes, company status, company age, company type, and name keywords. The model outputs a numeric score and a bucketed classification (strong/possible/unlikely).

## Consequences

- Rankings are explainable and feature-driven.
- Scores can be tuned with minimal structural changes.
- Output supports both filtered shortlists and broader reviews.
