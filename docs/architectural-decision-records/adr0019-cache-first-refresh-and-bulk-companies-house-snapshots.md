# ADR 0019: Cache-First Refresh and Bulk Companies House Snapshots

Date: 2026-02-04

## Status

Accepted

## Context

The pipeline needs reproducible, cache-only runs with a clear audit trail and without
per-run network fetches. The existing JSON file source and legacy CLI commands
(`extract`, `transform-register`) conflict with the cache-first design and add
unnecessary dual-path behaviour. Companies House bulk CSV snapshots provide a stable
source of truth, but they require streaming IO, explicit schema validation, and indexed
lookups to remain practical at scale.

## Decision

- Add `refresh-sponsor` and `refresh-companies-house` commands that download, validate,
  and write snapshot artefacts under `data/cache/snapshots/<dataset>/<YYYY-MM-DD>/`,
  including a manifest.
- Make `run-all` cache-only and fail fast when required clean snapshots are missing.
- Replace the JSON file source with bulk CSV snapshots using the canonical clean schema
  `ch_clean_v1` and a token index; keep the API source as an explicit opt-in.
- Require streaming download and write paths, plus CLI-owned progress reporting, for
  bulk ingest and cleaning.
- Treat missing required columns in raw CSVs as errors (fail fast) and validate against
  explicit header lists.
- Derive snapshot dates from source filenames using `r"(20\\d{2}-\\d{2}-\\d{2})"` and
  fall back to the download date in UTC when no match exists.
- Write snapshots atomically via a staging directory (`.tmp-<uuid>`) and rename to the
  final `<YYYY-MM-DD>` directory only after artefacts and the manifest are written.
- Resolve the latest snapshot by sorting on `snapshot_date` (descending) with manifest
  mtime as a deterministic tie-breaker.
- Snapshot manifests must include dataset metadata, hashes, row counts, artefact paths,
  timestamps, `git_sha` (from `GIT_SHA` or `unknown`), and `tool_version` (package
  version or `0.0.0+unknown`).

## Consequences

- Legacy CLI commands (`extract`, `transform-register`) are removed.
- Snapshot manifests and atomic writes provide repeatability and auditability.
- Documentation and troubleshooting guidance must be updated to describe refresh
  commands and cache-only runs.
- New tests are required for streaming IO, snapshot manifests, header trimming,
  URI validation, and token index generation.
