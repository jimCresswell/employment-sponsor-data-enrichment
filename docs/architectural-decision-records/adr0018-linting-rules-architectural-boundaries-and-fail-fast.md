# ADR 0018: Linting Rules for Architectural Boundaries and Fail-Fast Error Handling

Date: 2026-02-02

## Status

Accepted

## Context

The pipeline relies on strict layering (CLI → application → protocols → infrastructure) and fail-fast
error handling to preserve auditability and operational safety. Prior linting did not fully enforce
boundary cleanliness, timezone-aware datetimes, or exception context preservation.

## Decision

- Add an import‑linter contract that forbids `uk_sponsor_pipeline.cli` from importing
  `uk_sponsor_pipeline.infrastructure` directly.
- Enable Ruff rules:
  - `TRY` (exception context and fail‑fast error handling).
  - `BLE` (no broad `except Exception`).
  - `SLF001` (no private member access across modules).
  - `T20` (no `print` outside the CLI boundary).
  - `DTZ` (timezone‑aware datetime usage).
  - All `TRY` checks apply; failures are fixed by introducing typed, domain‑specific exceptions.

## Consequences

- Boundary violations are caught earlier and prevent architectural drift.
- Exceptions must preserve context and avoid broad catches.
- Any `print` usage outside the CLI fails linting.
- Naive datetimes are disallowed; UTC‑aware timestamps are required.
