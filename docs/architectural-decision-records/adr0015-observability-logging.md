# ADR 0015: Standardised Observability Logging

Date: 2026-02-02

## Status

Accepted

## Context

Logging existed in multiple modules with inconsistent formats. This made it harder to compare runs, trace failures across steps, and keep observability consistent when refactoring the pipeline. We need a single, reusable logging standard that can be applied across application steps and infrastructure.

## Decision

- Use a shared logger factory in `uk_sponsor_pipeline.observability.logging` for all pipeline logs.
- Emit UTC timestamps and a consistent line format to support auditability and reproducibility.
- Allow optional structured context fields to standardise key metadata across steps.

## Consequences

- Log output is consistent across the pipeline.
- Application steps and infrastructure can share the same observability conventions.
- Future refactors have a single, documented logging standard to follow.
