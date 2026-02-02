# ADR 0016: Configurable Companies House Source (API or File)

Date: 2026-02-02

## Status

Accepted

## Context

Stage 2 currently depends on the Companies House API for search and profile data. For reproducibility, offline runs, and controlled fixtures, we need a file-based source that produces the same validated IO shapes as the API while preserving the current behaviour by default.

## Decision

- Introduce a Companies House source abstraction with two implementations:
  - API source (current behaviour).
  - File source backed by a JSON file containing search responses and profiles.
- Select the source via configuration (`CH_SOURCE_TYPE` and `CH_SOURCE_PATH`).
- Validate file inputs at IO boundaries and convert to the same internal shapes as API outputs.

## Consequences

- Default API behaviour remains unchanged.
- Offline or deterministic runs can use a file source without changing application logic.
- File inputs are validated consistently with API responses.
