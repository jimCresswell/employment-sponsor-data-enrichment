# Plan Overview: Cache-First Ingest + File-First Enrichment (Overview + Decisions)

Status: Draft (planning only). Implementation work lives in
`.agent/plans/ingest-source-expansion.plan.md`.

## Entry Instructions (Read First)

1. Read directives in order:
1. `.agent/directives/AGENT.md`
1. `.agent/directives/rules.md`
1. `.agent/directives/project.md`
1. `.agent/directives/python3.practice.md`
1. Read research:
1. `.agent/research/ch-bulk-data-guidance.md`
1. `.agent/research/ch-data-product-fields.md`
1. `.agent/research/ch-sic-codes.md`
1. Follow all requirements therein (TDD, strict typing, fail fast, British spelling, clean breaks).

## Source Documents (Current)

1. `.agent/plans/ingest-source-expansion.plan.md`
1. `.agent/plans/sector-profiles.plan.md`
1. `.agent/plans/deferred-features.md`

## Context

We are moving to cache-first ingest for both Sponsor Register and Companies House data.
Refresh happens only via refresh commands; there is no per-run fetch. The pipeline reads
clean artefacts only. Companies House API remains optional, but file-backed data is the
default.

Staleness of 1–2 months is acceptable in exchange for reproducibility and performance.

## Goals

1. Deterministic, cache-only pipeline runs using clean artefacts.
1. File-first Companies House enrichment with on-disk indices.
1. Refresh commands for both datasets.
1. Fail-fast validation with a clear audit trail.

## Non-Goals

1. SQLite or other embedded databases (unless file indexing exceeds the performance threshold).
1. UI, dashboards, or reporting interfaces.
1. Compatibility layers for legacy commands or data formats.

## Architectural Principles

1. Preserve validated schemas declared in code (do not infer schema from data).
1. Keep IO at the boundaries only (no direct filesystem/network IO in application or domain).
1. Prefer reproducible artefacts and deterministic outputs.
1. Fail fast on schema or URI mismatches.
1. Minimise moving parts (CSV + index before any DB escalation).

## Decisions Locked

1. Snapshot layout uses dated directories under `data/cache/snapshots`.
1. Clean artefacts are full-schema CSV plus on-disk token indices for Companies House.
1. New commands: `refresh-sponsor` and `refresh-companies-house`.
1. Refresh inputs are URL-only for both datasets.
1. Remove `extract` and `transform-register` CLI commands.
1. Remove the JSON file source and replace it with bulk CSV snapshots.
1. File-based matching uses a token inverted index and existing scoring with `CH_MIN_MATCH_SCORE`.
1. Snapshot date derives from source filename if possible, otherwise download date (ISO `YYYY-MM-DD`).
1. Index format is CSV; SQLite escalation threshold is >30 minutes per full run.
1. Clean Companies House output preserves the full bulk schema.
1. URI validation is fail-fast.
1. Cache root is `data/cache/snapshots` and raw + clean artefacts are retained.
1. Manifest detail is extended (core + counts + git SHA + tool version + command line).
1. Snapshot selection defaults to latest when paths are not set.
1. `CH_SOURCE_TYPE` remains `api` or `file`, where `file` means bulk snapshot + index.
1. File-based access parses `clean.csv` with a standard CSV parser and loads profiles into memory.
1. If memory pressure is observed, bucketed profile files are a future option, not a
   parallel mechanism in the initial implementation.
1. Single-threaded streaming is the default for bulk downloads.
1. Condensed Companies House SIC codes are authoritative and must not be remapped.

## Refresh Behaviour

1. `refresh-sponsor` downloads the sponsor register from a URL and writes snapshot artefacts
   under `data/cache/snapshots/sponsor/<YYYY-MM-DD>/`.
1. `refresh-companies-house` downloads the bulk Companies House file from a URL and writes
   snapshot artefacts under `data/cache/snapshots/companies_house/<YYYY-MM-DD>/`.
1. Refresh commands may use network IO. They fail fast if the target snapshot directory
   already exists for the derived snapshot date.

## Usage Behaviour

1. `run-all` reads the latest clean snapshot artefacts and fails fast if required paths
   are missing.
1. File-based Companies House enrichment performs no API calls.
1. API-based Companies House enrichment is allowed only when `CH_SOURCE_TYPE=api` and a
   valid key is configured.

## Manifest Schema

Each snapshot manifest contains:

1. `dataset` (`sponsor` or `companies_house`).
1. `snapshot_date` (ISO `YYYY-MM-DD`).
1. `source_url`.
1. `downloaded_at_utc` (ISO 8601 with UTC offset).
1. `last_updated_at_utc` (ISO 8601 with UTC offset).
1. `schema_version` (string or semantic version).
1. `sha256_hash_raw` and `sha256_hash_clean`.
1. `bytes_raw`.
1. `row_counts` (raw and clean counts where applicable).
1. `artefacts` (relative paths to raw, clean, token index, and stats files).
1. `git_sha`.
1. `tool_version`.
1. `command_line`.

## Required Diagrams

1. Sponsor refresh flow diagram showing URL input and resulting snapshot artefacts.
1. Companies House refresh flow diagram showing download, extraction, cleaning, indexing,
   and snapshot artefacts.
1. Usage flow diagram showing cache-only execution from clean artefacts to outputs.

## Open Questions

1. Confirm the exact bulk CSV header list (including previous-name fields and ordering).
1. Confirm Companies House bulk filename pattern for deriving snapshot date (ISO `YYYY-MM-DD`).
1. Confirm ZIP layout and encoding expectations for the bulk file.
1. Define the meaning of "clean" for Companies House after inspecting a real bulk file.

## Assumptions and Defaults

1. Bulk Companies House download is ~0.5 GB zipped.
1. Latest snapshot is selected when paths are not set.
1. API cache remains in `data/cache/companies_house` and is distinct from snapshots.
1. All timestamps are ISO 8601 with UTC offsets.

## Performance Threshold

1. Revisit SQLite only if file-based matching exceeds ~30 minutes per full run.

## Related Plans

1. `.agent/plans/sector-profiles.plan.md` covers scoring profile configuration for `transform-score`
   and does not change ingest or snapshot behaviour.
1. `.agent/plans/deferred-features.md` captures backlog items such as config files, CI workflow,
   and a CLI `--version` flag, and is not part of cache-first ingest work.
