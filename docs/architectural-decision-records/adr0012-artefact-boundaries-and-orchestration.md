# ADR 0012: Artefact Boundaries and Application Orchestration

Date: 2026-02-01

## Status

Accepted

## Context

The pipeline uses step CSV outputs for auditability and resumability. However, treating steps as architectural boundaries has led to duplicated infrastructure setup, inconsistent error handling, and configuration being loaded in multiple places. We need a SOLID/DI‑aligned architecture where shared standards (observability, resilience, filesystem, HTTP, error handling) are applied uniformly, while preserving the artefacts that make the pipeline explainable and recoverable.

## Decision

- Keep step CSV artefacts as data contracts and audit checkpoints.
- Treat steps as conceptual labels for outputs, not architectural boundaries.
- Move orchestration and step ownership into an application pipeline (use‑case layer).
- Share infrastructure and observability across all steps via dependency injection.
- Use a shared logger factory in `uk_sponsor_pipeline.observability.logging` for consistent UTC timestamps.
- Read configuration once at the CLI entry point and pass it through.
- Delegate concrete dependency wiring to the composition root (`uk_sponsor_pipeline/composition.py`); the CLI calls it.
- If a legacy wrapper remains, it must be a thin delegate layer that forwards to application steps.

## Consequences

- Auditability and resumability remain intact via step artefacts.
- Architecture is simplified: common standards are enforced in one place.
- Application orchestration becomes the single owner of batching/resume/reporting.
- Requires refactoring existing step modules into application steps (see refactor plan).
- Supersedes ADR 0003’s implication that steps are architectural boundaries.

## Migration Status

In progress: the target architecture is an `application/` use‑case layer. Orchestration now lives in `application/pipeline.py`, and the CLI delegates to it; residual logic should continue to be moved into `application/` until wrapper modules contain no business logic.
