# Implementation Plan: Cache-First Refresh + Bulk Companies House Ingest (2026-02-03)

Status: Immediate implementation plan (planning only). Overview and decision notes live in
`.agent/plans/overview-cache-first-and-file-first.md`.

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
1. Read the overview and decision notes:
1. `.agent/plans/overview-cache-first-and-file-first.md`
1. This plan is the implementation entry point; do not implement until it is approved.

## Summary

Introduce refresh commands that download and clean cached snapshots for the
sponsor register and Companies House bulk data. The pipeline reads clean cached
artefacts only and fails fast if they are missing. Companies House enrichment becomes
file-first by default using a token index and on-disk lookup, with the API kept as an
optional source. Legacy CLI commands and the JSON file source are removed.

## Public Interfaces

### CLI

- Add `refresh-sponsor --url <csv-url> [--snapshot-root <path>]`. Progress bar is emitted by the CLI only.
- Add `refresh-companies-house --url <zip-or-csv-url> [--snapshot-root <path>]`. Progress bar is emitted by the CLI only.
- Remove `extract` and `transform-register` commands entirely.
- `run-all` becomes cache-only and fails fast if clean snapshot paths are not resolved.

### Environment and Config

Add new config fields and env vars, read once in the CLI and passed through:

- `SNAPSHOT_ROOT` (default `data/cache/snapshots`).
- `SPONSOR_CLEAN_PATH`.
- `CH_CLEAN_PATH`.
- `CH_TOKEN_INDEX_DIR`.
- Optional `CH_FILE_MAX_CANDIDATES` (default 500).

If paths are not set, the CLI resolves the latest snapshot under `SNAPSHOT_ROOT` and passes resolved paths into application steps.

### Protocols

Extend `HttpSession` and `FileSystem` to support streaming:

- `HttpSession.iter_bytes(url, timeout_seconds, chunk_size)`.
- `FileSystem.write_bytes_stream(path, chunks)`.

### Types and Exceptions

- Add IO contracts for bulk Companies House row inputs and clean row outputs.
- Add exceptions for missing snapshots, URI mismatch, and snapshot directory already exists.

## Artefact Layout

All snapshots live under `data/cache/snapshots/<dataset>/<YYYY-MM-DD>/`.

Sponsor register snapshot directory contains:

- `raw.csv`.
- `clean.csv`.
- `register_stats.json`.
- `manifest.json`.

Companies House snapshot directory contains:

- `raw.zip` (when source is zip).
- `raw.csv`.
- `clean.csv`.
- `index_tokens_<bucket>.csv` (bucketed token index).
- `manifest.json`.

Snapshot directory creation fails fast if the target date already exists.

## Manifest Schema

Each snapshot manifest contains:

- `dataset` (`sponsor` or `companies_house`).
- `snapshot_date` (ISO `YYYY-MM-DD`).
- `source_url`.
- `downloaded_at_utc` (ISO 8601 with UTC offset).
- `last_updated_at_utc` (ISO 8601 with UTC offset).
- `schema_version` (string or semantic version).
- `sha256_hash_raw` and `sha256_hash_clean`.
- `bytes_raw`.
- `row_counts` (raw and clean where applicable).
- `artefacts` (relative paths to raw, clean, index, and stats files).
- `git_sha`.
- `tool_version`.
- `command_line`.

## Refresh and Usage Behaviour

Refresh behaviour:

- `refresh-sponsor` downloads the sponsor register and writes snapshot artefacts.
- `refresh-companies-house` downloads the bulk Companies House file and writes snapshot artefacts.
- Refresh commands may use network IO and fail fast if the target snapshot directory exists.

Usage behaviour:

- `run-all` reads clean snapshot artefacts and fails fast when required paths are missing.
- File-based Companies House enrichment performs no API calls.
- API-based Companies House enrichment is allowed only when `CH_SOURCE_TYPE=api` and a valid key is configured.

## Artefact Writes (Semantic Names)

Sponsor register:

- Sponsor Raw Snapshot Write: `raw.csv`.
- Sponsor Clean Snapshot Write: `clean.csv`.
- Sponsor Register Stats Write: `register_stats.json`.
- Sponsor Snapshot Manifest Write: `manifest.json`.

Companies House:

- Companies House Raw Download Write: `raw.zip` or `raw.csv`.
- Companies House Extracted CSV Write: `raw.csv` when source is a zip.
- Companies House Clean Snapshot Write: `clean.csv`.
- Companies House Token Index Write: `index_tokens_<bucket>.csv`.
- Companies House Snapshot Manifest Write: `manifest.json`.

## Cleaning Rules

### Sponsor Register

- Download raw CSV from the URL input.
- Validate required columns using `RAW_REQUIRED_COLUMNS`.
- Run existing register transform logic to produce `clean.csv`.
- Write `register_stats.json` and `manifest.json` into the snapshot directory.

### Companies House Bulk CSV

- Download the bulk file from the URL input, stream to `raw.zip` or `raw.csv` (never read whole file into memory).
- Progress bar is emitted by the CLI only (byte stream for download, row count for processing).
- If zip, extract the CSV to `raw.csv`.
- Validate all expected columns from `ch-data-product-fields.md`.
- Preserve all columns as strings; blanks are valid and kept as empty strings.
- Preserve `CompanyNumber` exactly as supplied (including prefix and zero padding).
- Validate `URI` equals `http://data.companieshouse.gov.uk/doc/company/{CompanyNumber}`.
- Do not remap SIC codes; keep condensed codes exactly as supplied.
- Produce `clean.csv` with the full schema and stable column order using a standard CSV parser
  that handles quoted fields and embedded newlines.
- Candidate cleaning actions pending first file inspection: trimming outer whitespace and any
  additional normalisation beyond the rules above.

### Field Mapping for Enrichment

When constructing search items and profiles from bulk rows:

- `CompanyName` -> `title` and `company_name`.
- `CompanyNumber` -> `company_number`.
- `CompanyStatus` -> `company_status` (lowercased).
- `CompanyCategory` -> `type` via slugify (lowercase, spaces to hyphens, collapse multiple hyphens). Add `public-limited-company` to company type weights.
- `IncorporationDate` -> `date_of_creation`.
- `SICCode1..4` -> `sic_codes` list (non-empty only).
- `PostTown` -> `address.locality`.
- `County` -> `address.region`.
- `PostCode` -> `address.postal_code`.

## Indexing and Matching

### Token Index

- Token source: `normalise_org_name(CompanyName)`.
- Tokens are split on whitespace; keep tokens with length >= 2.
- Bucket by first character: `a-z`, `0-9`, and `_` for other.
- Index format per bucket: CSV `token,company_number`.

### Candidate Retrieval

- Precompute a token set from all sponsor organisations using `generate_query_variants` and `normalise_org_name`.
- Stream each bucket file once and build a map only for tokens in the set.
- For each query variant, gather candidate company numbers and count token hits.
- Minimum token-hit rule:
  - 2+ tokens: require at least 2 token hits.
  - 1 token: require 1 hit.
- If candidates exceed 500, keep the top 500 by token-hit count, then `company_number` for stability.

### Profile Lookup

- Load `clean.csv` into an in-memory map keyed by `CompanyNumber` using a standard CSV parser.
- Use the in-memory map for profile lookup during enrichment. Memory budget assumes 16 GB RAM.
- Alternative (not implemented now): if memory pressure is observed, explore bucketed profile files
  as a future option, not a parallel mechanism in the initial implementation.

### Scoring

- Use existing `score_candidates` and `CH_MIN_MATCH_SCORE` unchanged.

## Pipeline Changes

- `run-all` no longer performs download or register transform; it loads the clean sponsor register and Companies House snapshot paths (latest by default) and fails fast if missing.
- `build_companies_house_source` supports `api` and `file` (bulk snapshot + index). Remove JSON file handling.
- Remove `extract` and `transform-register` CLI commands.

## Documentation Requirements

- Sponsor refresh flow diagram showing URL input and resulting snapshot artefacts.
- Companies House refresh flow diagram showing download, extraction, cleaning, indexing, and snapshot artefacts.
- Usage flow diagram showing cache-only execution from clean artefacts to outputs.

## Tests and Scenarios

- Refresh sponsor writes `raw.csv`, `clean.csv`, `register_stats.json`, and `manifest.json` with correct hashes and counts.
- Refresh sponsor fails on missing columns.
- Refresh Companies House handles zip and CSV URLs and produces all artefacts.
- Refresh Companies House fails fast on URI mismatch.
- **Network Isolation**: Download logic is tested using `HttpSession` fakes that simulate streaming chunks; no real network calls.
- **Streaming Verification**: Verify `write_bytes_stream` writes small chunks (e.g., 10 bytes) without buffering the full file.
- **CSV Robustness**: Quoted fields with commas, embedded newlines, and UTF-8 characters are parsed correctly.
- **Line Ending Robustness**: CRLF and LF inputs both parse correctly.
- Token index buckets include expected tokens and company numbers.
- Token filtering builds a candidate set with correct hit counts and capping.
- File source `search` returns candidates mapped from bulk rows.
- File source `profile` returns correct profile and fails fast on missing company number.
- `run-all` fails fast when clean snapshot paths are missing.
- Config parsing for new env vars and defaults is correct.

## Assumptions and Defaults

- Snapshot date uses the source filename `YYYY-MM-DD` if present, otherwise download date.
- Latest snapshot is selected when paths are not set.
- API cache remains in `data/cache/companies_house` and is distinct from snapshots.
- SQLite is considered only if file-based matching exceeds ~30 minutes per full run.
- All work is TDD-first, with strict typing and no `Any` outside IO boundaries.
- Snapshot date must be ISO `YYYY-MM-DD`. Manifest timestamps are ISO 8601 with UTC offsets.
- Schema is validated against a canonical header list; do not infer schema from data.
- Download speed may be sub-second, but progress bars are still required.
- Memory pressure triggers exploration of bucketed profile files as a future option,
  not as a parallel mechanism in the initial implementation.
