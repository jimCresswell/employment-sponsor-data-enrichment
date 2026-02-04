# Implementation Plan: Cache-First Refresh + Bulk Companies House Ingest (2026-02-03)

## Start Here (Stand-Alone Entry Point)

Status: **Approved** (2026-02-04)

### Scope Summary

- Add cache-first refresh commands for sponsor register and Companies House bulk data.
- Switch `run-all` to cache-only; fail fast if clean snapshots are missing.
- Replace Companies House JSON file source with bulk CSV snapshots + token index.
- Remove legacy CLI commands `extract` and `transform-register`.

### Immediate First Tasks (TDD)

1. Add streaming IO support to `HttpSession` and `FileSystem`.
1. Add a `ProgressReporter` interface (CLI-owned, injected into application code).
1. Implement `refresh-sponsor` with snapshot layout and manifest.
1. Implement `refresh-companies-house` (download, extract, clean, index).

### Locked Decisions

- Canonical clean schema v1 is defined in this plan.
- Bucketed profile files are the default lookup strategy.
- Seven-part downloads are optional and only for operational reliability.
- JSON file source is removed; only API or bulk snapshot sources remain.

### Out of Scope

- SQLite or any embedded database.
- UI/dashboard/reporting.
- Seven-part downloads unless required for reliability.
- JSON file source compatibility.

### Likely Files to Change

`src/uk_sponsor_pipeline/protocols.py`  
`src/uk_sponsor_pipeline/cli.py`  
`src/uk_sponsor_pipeline/application/*`  
`src/uk_sponsor_pipeline/infrastructure/io/*`  
`src/uk_sponsor_pipeline/config.py`  
`src/uk_sponsor_pipeline/exceptions.py`  
`README.md`  
`docs/` and tests as needed

### Definition of Done

1. `refresh-sponsor` and `refresh-companies-house` produce snapshot artefacts + manifest.
1. `run-all` consumes clean snapshots only and fails fast if missing.
1. Legacy commands removed; docs updated.
1. Tests are network-isolated and pass full quality gates (`uv run check`).

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

## Pre-Plan Decisions (Locked Choices)

These choices are now explicit requirements for the implementation plan.

- Schema validation rule: missing columns are **errors** for sponsor and Companies House
  raw CSVs. This overrides `.agent/research/ch-bulk-data-guidance.md` which treats
  missing columns as non-errors; update that document to align.
- Canonical schema version: `ch_clean_v1`. Define as a constant in code (single source of
  truth) and bump only when canonical columns or normalisation rules change.
- `company_type` slugify: lowercase; replace any non-alphanumeric character with space;
  collapse whitespace to single hyphen; collapse repeated hyphens; trim leading/trailing
  hyphens.
- Snapshot date extraction: use regex `r"(20\\d{2}-\\d{2}-\\d{2})"` against the source
  filename. If no match, use download date in **UTC**. `downloaded_at_utc` is always
  `datetime.now(UTC).isoformat()`.
- Latest snapshot selection: order by `snapshot_date` (ISO) descending, then by `mtime`
  descending as a deterministic tie-break. Fail fast if any required artefact is missing.
- Atomic snapshot writes: write to a staging directory
  `data/cache/snapshots/<dataset>/.tmp-<uuid>` and rename to the final
  `<YYYY-MM-DD>` directory only after all artefacts and the manifest are written.
- Bulk CSV parsing: streaming with Python `csv` using `newline=""`, encoding `utf-8-sig`
  (BOM-safe), RFC-style quoting, and no pandas for bulk ingest.
- Progress reporting: CLI emits progress for three phases: `download` (bytes),
  `clean` (rows), `index` (rows). When total is unknown, pass `total=None` and still emit
  `advance` calls.
- JSON file source removal: remove immediately as part of this change. No compatibility
  shims, no dual-path support.
- Token index generation: generated during refresh only, stored in the snapshot directory,
  and recorded in the manifest; index files must correspond to `schema_version`.
- Manifest metadata: `git_sha` comes from `GIT_SHA` env var if set; otherwise `unknown`.
  `tool_version` comes from `uk_sponsor_pipeline.__version__` if defined; otherwise
  `0.0.0+unknown`.

## Explicit Gaps (Current Repo vs This Plan)

This section lists concrete gaps between the current codebase and the planned work.
Treat each item as a required change before this plan can be marked complete.

### CLI and Orchestration

- Missing `refresh-sponsor` and `refresh-companies-house` commands.
- Legacy `extract` and `transform-register` commands still exist and are wired into the CLI.
- `run-all` still performs download/transform steps (unless `--skip-download` is used);
  it does not run cache-only from clean snapshots and does not fail fast on missing snapshots.

### Snapshot Artefacts and Manifests

- No snapshot layout under `data/cache/snapshots/<dataset>/<YYYY-MM-DD>/`.
- No manifest schema or manifest writing for sponsor or Companies House snapshots.
- No snapshot date derivation from source filename or download date.
- No fail-fast check for existing snapshot directories.

### Configuration and Environment

- No support for `SNAPSHOT_ROOT`, `SPONSOR_CLEAN_PATH`, `CH_CLEAN_PATH`, `CH_TOKEN_INDEX_DIR`.
- No `CH_FILE_MAX_CANDIDATES` limit for file-based matching.
- CLI does not resolve latest snapshots when explicit paths are missing.

### Companies House Source (File-First Bulk CSV)

- File source is currently JSON (`searches` + `profiles`), not bulk CSV snapshots.
- No bulk download flow (zip or CSV) and no extraction to `raw.csv`.
- No header trimming or validation against the trimmed raw header list.
- No canonical clean schema output (`clean.csv`) and no raw → canonical mapping.
- No URI validation for `http://data.companieshouse.gov.uk/doc/company/{CompanyNumber}`.
- No parsing of SIC code prefixes from `SICCode.SicText_1..4`.

### Streaming IO and Progress

- `HttpSession` lacks `iter_bytes`; `FileSystem` lacks `write_bytes_stream`.
- Download path currently buffers full response bytes in memory.
- No injected `ProgressReporter` interface; progress is handled inside `transform-enrich`
  using `tqdm` rather than CLI-owned progress reporting.

### Indexing and Matching

- No token index generation (`index_tokens_<bucket>.csv`) from canonical clean rows.
- No bucketed profile lookup strategy (Option B) or minimal in-memory Option A switch.
- No candidate retrieval based on token-hit counts or capping to 500.

### Types, Schemas, and Exceptions

- No IO contracts or schema definitions for bulk Companies House raw rows or clean rows.
- No exceptions for missing snapshots, URI mismatch, or snapshot directory already exists.
- No schema validation for raw CSV header list or clean CSV canonical header list.

### Documentation and ADRs

- README and ADR 0016 still document JSON file source and legacy CLI commands.
- No refresh flow diagrams or cache-only usage diagrams exist in `docs/`.
- `.agent/research/ch-bulk-data-guidance.md` states missing columns are not errors; this must be
  updated to match the locked decision that missing columns are errors.
- `.agent/directives/project.md` still lists `extract` and `transform-register` in the pipeline
  summary; update it to reflect cache-first refresh and snapshot-only `run-all`.
- Add a new ADR (or supersede ADR 0016) to document cache-first refresh + bulk CSV snapshots
  and the removal of the JSON file source, then align README and troubleshooting docs.

### Tests

- No tests for streaming download, chunked writes, or progress reporting injection.
- No tests for refresh commands, snapshot manifests, header trimming, URI validation,
  SIC prefix parsing, token index generation, or cache-only `run-all`.

## Separation of Concerns (Non-Negotiable)

- **Refresh**: download + validate + write snapshot artefacts. No profiling or heuristic analysis.
- **Cleaning**: deterministic transforms into a canonical schema. No inference from data values.
- **Analysis**: read-only profiling and inspection (separate command or devtool), never mutates snapshots.
- **Usage**: read clean artefacts only; no raw access at runtime.

## Public Interfaces

### CLI

- Add `refresh-sponsor --url <csv-url> [--snapshot-root <path>]`. Progress is emitted by the CLI only.
- Add `refresh-companies-house --url <zip-or-csv-url> [--snapshot-root <path>]`. Progress is emitted by the CLI only.
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

Add an application-neutral progress interface (owned by CLI, injected into application):

- `ProgressReporter.start(label, total)`.
- `ProgressReporter.advance(count)`.
- `ProgressReporter.finish()`.

### Types and Exceptions

- Add IO contracts for bulk Companies House row inputs and clean row outputs.
- Add exceptions for missing snapshots, URI mismatch, and snapshot directory already exists.

## Data Sources and Headers

### Companies House Bulk CSV (Raw Headers)

Raw header names **must be trimmed** (`.strip()`), because the real file contains leading spaces
on multiple columns. The canonical raw header list is the trimmed header list in
`.agent/research/ch-data-product-fields.md` and is repeated here for completeness:

```text
CompanyName
CompanyNumber
RegAddress.CareOf
RegAddress.POBox
RegAddress.AddressLine1
RegAddress.AddressLine2
RegAddress.PostTown
RegAddress.County
RegAddress.Country
RegAddress.PostCode
CompanyCategory
CompanyStatus
CountryOfOrigin
DissolutionDate
IncorporationDate
Accounts.AccountRefDay
Accounts.AccountRefMonth
Accounts.NextDueDate
Accounts.LastMadeUpDate
Accounts.AccountCategory
Returns.NextDueDate
Returns.LastMadeUpDate
Mortgages.NumMortCharges
Mortgages.NumMortOutstanding
Mortgages.NumMortPartSatisfied
Mortgages.NumMortSatisfied
SICCode.SicText_1
SICCode.SicText_2
SICCode.SicText_3
SICCode.SicText_4
LimitedPartnerships.NumGenPartners
LimitedPartnerships.NumLimPartners
URI
PreviousName_1.CONDATE
PreviousName_1.CompanyName
PreviousName_2.CONDATE
PreviousName_2.CompanyName
PreviousName_3.CONDATE
PreviousName_3.CompanyName
PreviousName_4.CONDATE
PreviousName_4.CompanyName
PreviousName_5.CONDATE
PreviousName_5.CompanyName
PreviousName_6.CONDATE
PreviousName_6.CompanyName
PreviousName_7.CONDATE
PreviousName_7.CompanyName
PreviousName_8.CONDATE
PreviousName_8.CompanyName
PreviousName_9.CONDATE
PreviousName_9.CompanyName
PreviousName_10.CONDATE
PreviousName_10.CompanyName
ConfStmtNextDueDate
ConfStmtLastMadeUpDate
```

### Canonical Headers (Clean CSV)

Canonical headers are **internal** and may be a subset of raw headers with improved naming.
Raw headers and canonical headers are **not** the same concept.

Initial canonical v1 (for enrichment and scoring) is a **minimal subset**, subject to review.
Canonical v1 columns (CSV, in order):

```text
company_number
company_name
company_status
company_type
date_of_creation
sic_codes
address_locality
address_region
address_postcode
uri
```

Normalisation rules for canonical v1:

1. `company_number` is preserved exactly as supplied.
1. `company_name` is trimmed but otherwise preserved.
1. `company_status` is lowercased.
1. `company_type` is a slugified form of `CompanyCategory`.
1. `date_of_creation` is ISO `YYYY-MM-DD` parsed from the raw date.
1. `sic_codes` is a semicolon-delimited list of code prefixes only.
1. Address fields are trimmed only (no additional normalisation).
1. `uri` must match the deterministic `CompanyNumber` mapping.

Additional canonical fields may be added deliberately, but only if they are used downstream.
Raw `raw.csv` remains the audit source for all other columns.

### Alternate Source: Seven-File Companies House Export

Companies House also publishes the Basic Company Data in **seven parts** on its download page.
Combined size is similar to the single-file export, but the split enables **sequential streaming**
and per-part cleaning. We should support both forms:

- All-in-one ZIP/CSV (single snapshot).
- Seven-part ZIP set (treated as a single logical snapshot, cleaned in part order).

Recent publication lists parts in the ~69–76 MB range each (about ~0.5 GB total zipped),
which is comparable to the all-in-one ZIP size and does not materially change memory needs.

Seven-part support is optional and only worth implementing if it materially improves operational
reliability; it is not required for memory safety.

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
- Progress is emitted by the CLI only (byte stream for download, row count for processing).
- If zip, extract the CSV to `raw.csv`.
- Trim header names before validation; the raw file contains leading spaces.
- Validate all expected columns using the trimmed raw header list.
- Preserve all columns as strings; blanks are valid and kept as empty strings.
- Preserve `CompanyNumber` exactly as supplied (including prefix and zero padding).
- Validate `URI` equals `http://data.companieshouse.gov.uk/doc/company/{CompanyNumber}`.
- `SICCode.SicText_n` contains **code + description** (e.g., `99999 - Dormant Company`).
  Canonical `sic_codes` should extract the code prefix (split on ` - `) without any external mapping.
- Produce `clean.csv` with the **canonical schema** (not raw headers) in a stable column order,
  using a standard CSV parser that handles quoted fields and embedded newlines.
- Candidate cleaning actions now include: trimming outer whitespace for raw values, and
  explicit parsing of SIC code prefixes for canonical `sic_codes`.

Raw → canonical mapping (v1):

| Canonical | Raw header | Rule |
| --- | --- | --- |
| company_number | CompanyNumber | Preserve exactly. |
| company_name | CompanyName | Trim only. |
| company_status | CompanyStatus | Lowercase. |
| company_type | CompanyCategory | Slugify (lowercase, spaces to hyphens, collapse multiples). |
| date_of_creation | IncorporationDate | Parse and emit ISO `YYYY-MM-DD`. |
| sic_codes | SICCode.SicText_1..4 | Extract code prefix, join with `;`. |
| address_locality | RegAddress.PostTown | Trim only. |
| address_region | RegAddress.County | Trim only. |
| address_postcode | RegAddress.PostCode | Trim only. |
| uri | URI | Must match canonical mapping. |

### Field Mapping for Enrichment

When constructing search items and profiles from **canonical clean rows**:

- `company_name` -> `title` and `company_name`.
- `company_number` -> `company_number`.
- `company_status` -> `company_status`.
- `company_type` -> `type` (already slugified). Add `public-limited-company` to weights.
- `date_of_creation` -> `date_of_creation`.
- `sic_codes` -> `sic_codes` list (split on `;`).
- `address_locality` -> `address.locality`.
- `address_region` -> `address.region`.
- `address_postcode` -> `address.postal_code`.

## Indexing and Matching

### Token Index

- Token source: `normalise_org_name(company_name)` from the canonical clean schema.
- Tokens are split on whitespace; keep tokens with length >= 2.
- Bucket by first character: `a-z`, `0-9`, and `_` for other.
- Index format per bucket: CSV `token,company_number`.

### Candidate Retrieval

- Precompute a token set from all sponsor organisations using `generate_query_variants` and `normalise_org_name`.
- Stream each bucket file once and build a map only for tokens in the set.
- For each query variant, gather candidate company numbers and count token hits.
- Minimum token-hit rule: for 2+ tokens require at least 2 token hits; for 1 token require 1 hit.
- If candidates exceed 500, keep the top 500 by token-hit count, then `company_number` for stability.

### Profile Lookup

- Do **not** assume full-schema in-memory loading is viable.
- Use one of these approaches (default to the simplest that fits memory constraints).
- Option A: minimal in-memory profile map keyed by `company_number`, holding only canonical fields.
- Option B: bucketed profile files keyed by first character or hash bucket, loaded on demand.
- Default: **Option B** (bucketed profiles). Option A is enabled only when memory profiling
  shows safe headroom for the target environment.
- Keep the canonical schema small and stable to make the minimal in-memory option viable.

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
- **Header Trimming**: Raw headers with leading spaces are normalised before schema validation.
- Token index buckets include expected tokens and company numbers.
- Token filtering builds a candidate set with correct hit counts and capping.
- File source `search` returns candidates mapped from bulk rows.
- File source `profile` returns correct profile and fails fast on missing company number.
- `run-all` fails fast when clean snapshot paths are missing.
- Config parsing for new env vars and defaults is correct.

## Memory and Performance Notes (Observed)

Preliminary sampling on `BasicCompanyDataAsOneFile-2026-02-01.csv`:

- Full raw row stored as a Python dict averages ~4.2 KB per row.
- Minimal 12-field row averages ~1.1 KB per row.
- At ~5.68M rows, full in-memory would be **~24 GB** (before additional map overhead).
- Minimal in-memory would be **~6–7 GB** (before map overhead).

Conclusion: full-schema in-memory is not viable on 16 GB machines. A minimal canonical
schema may be viable but must be validated with a full test and overhead included.

## Location Aliases (Usage Filters)

Location aliases are configured in `data/reference/location_aliases.json`.
Current coverage includes London and Manchester with region names, borough/locality lists,
and postcode prefixes. Usage filters should continue to consume this file.

## Memory Profiling (Dev Note)

Use this to validate in-memory feasibility before committing to a lookup strategy.

1. Sample a fixed number of rows (e.g. 20,000) from the raw CSV with a standard CSV parser.
1. Build two mappings per row:
1. Full raw row mapping using trimmed raw headers.
1. Minimal canonical mapping using only the fields required for enrichment.
1. Estimate per-row size with `sys.getsizeof(dict) + sum(sys.getsizeof(value) for value in dict.values())`.
1. Extrapolate to total rows and add headroom for map overhead (treat estimates as lower bounds).
1. If estimated total exceeds available memory, default to bucketed profile files.

## Assumptions and Defaults

- Snapshot date uses the source filename `YYYY-MM-DD` if present, otherwise download date.
- Latest snapshot is selected when paths are not set.
- API cache remains in `data/cache/companies_house` and is distinct from snapshots.
- SQLite is considered only if file-based matching exceeds ~30 minutes per full run.
- All work is TDD-first, with strict typing and no `Any` outside IO boundaries.
- Snapshot date must be ISO `YYYY-MM-DD`. Manifest timestamps are ISO 8601 with UTC offsets.
- Schema is validated against explicit header lists. Raw CSV uses the trimmed raw header list.
  Clean CSV uses the canonical internal header list. Do not infer schema from data.
- Download speed may be sub-second, but progress bars are still required.
- Memory pressure triggers exploration of bucketed profile files as a future option,
  not as a parallel mechanism in the initial implementation.
