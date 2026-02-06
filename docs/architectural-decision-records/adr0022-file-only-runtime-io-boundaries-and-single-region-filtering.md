# ADR 0022: File-Only Runtime, Protocol IO Boundaries, and Single-Region Filtering

Date: 2026-02-06

## Status

Accepted

## Context

Milestone 0 locked in three cross-cutting behaviours that were previously spread across
implementation changes, tests, and plan notes:

1. Runtime pipeline commands must be deterministic and cache-only.
2. Application-layer filesystem access must remain protocol-backed and testable.
3. Geographic filtering must stay explicitly single-region for now.

Without a durable architecture record, these constraints risk drifting during future
feature work (for example, reintroducing direct `Path.open(...)` calls in application
modules, or silently expanding region filtering semantics).

## Decision

- Runtime CLI commands `transform-enrich` and `run-all` require
  `CH_SOURCE_TYPE=file` and fail fast for non-file values.
- Application modules must not call direct filesystem open/read/write operations on
  `pathlib.Path`; filesystem IO must go through `FileSystem` protocol methods.
- `FileSystem` includes streamed handle methods for application workflows that need file
  handles:
  - `open_text(...)`
  - `open_binary(...)`
- Local and in-memory filesystem implementations must support the same handle semantics
  so tests stay representative of production usage.
- Geographic filtering contract is singular:
  - CLI: one `--region` value only
  - Env: `GEO_FILTER_REGION` (single value only)
  - Comma-separated multi-region values fail fast.
- Runtime API wiring notes remain archived documentation only:
  `docs/archived-api-runtime-mode.md`.

## Consequences

- Runtime behaviour is simpler and more predictable for operators.
- IO contracts are enforceable through protocol tests and fakes, improving refactor
  safety.
- Contributor onboarding is clearer because runtime expectations are explicit.
- The old plural env variable (`GEO_FILTER_REGIONS`) is no longer part of the active
  contract.
- If runtime API mode or multi-region filtering are revisited, a new ADR must supersede
  this decision explicitly.
