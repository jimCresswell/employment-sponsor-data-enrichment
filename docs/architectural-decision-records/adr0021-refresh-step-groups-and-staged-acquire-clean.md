# ADR 0021: Refresh Step Groups and Staged Acquire/Clean

Date: 2026-02-06

## Status

Accepted

## Context

Operators need to validate refresh behaviour in isolated actions (discovery, download/extract,
clean) without manually reproducing pipeline internals. ADR 0019 established cache-first
refresh snapshots with atomic commits, but the refresh commands only exposed one-shot execution.
We need grouped CLI execution while preserving immutable final snapshots and cache-only `run-all`
behaviour.

## Decision

- Add grouped refresh execution for both `refresh-sponsor` and `refresh-companies-house` via
  `--only`:
  - `all` (default): acquire + clean
  - `discovery`: resolve source URL only
  - `acquire`: download raw payload (and ZIP extract for Companies House)
  - `clean`: finalise latest pending acquire into the dated snapshot
- Persist acquire outputs in dataset staging directories (`.tmp-<uuid>`) with `pending.json`
  metadata (`snapshot_date`, `source_url`, `downloaded_at_utc`, `bytes_raw`).
- Commit to final snapshot directories (`<YYYY-MM-DD>`) only during clean-finalise.
- `--only clean` fails fast when no pending acquire exists.
- `run-all` remains cache-only and continues to consume clean snapshots only.

## Consequences

- Refresh behaviour is testable in isolated groups without bypassing pipeline ownership.
- Partial acquire runs do not produce partial final snapshots, preserving clean artefact
  resolution for cache-only steps.
- New failure mode is explicit: missing pending acquire for clean-finalise.
- Documentation and validation protocol must describe grouped refresh execution.

