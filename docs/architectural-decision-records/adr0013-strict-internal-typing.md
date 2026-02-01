# ADR 0013: Strict Internal Typing After IO Boundaries

Date: 2026-02-01

## Status

Accepted

## Context

The pipeline ingests untrusted data from disk (CSV/JSON) and the network (Companies House). While Python is dynamic, we need stable, auditable behaviour and strict contracts inside the system. Allowing `Any` to flow beyond IO boundaries discards structure, weakens tooling, and makes refactors riskier.

## Decision

- Treat external data as untrusted at IO boundaries only.
- Validate and coerce external data into strict `TypedDict` or dataclass shapes immediately after ingestion.
- Avoid `Any` outside IO boundary modules (infrastructure and CLI entry points).
- Domain and application layers must use strict, explicit types.

## Consequences

- Clearer internal contracts and safer refactors.
- More explicit validation code at boundaries.
- Additional type definitions for structured data (e.g., stage rows and API payloads).

## Enforcement Options

- Enable Ruff’s `ANN401` to ban `Any`, with per-file ignores only for IO boundary modules.
- Keep IO boundary code in a small, explicit module set (e.g., `infrastructure/` and CLI) to make per-file ignores precise.
- Add import-linter contracts to prevent boundary types leaking into domain/application packages.
- Tighten mypy settings for domain/application packages over time.
