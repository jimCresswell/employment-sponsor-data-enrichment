# Snapshot Artefacts

Snapshots are cache-first artefacts written by refresh commands and consumed by
cache-only pipeline runs. They provide auditability, determinism, and resumability.

## Snapshot Root and Layout

Snapshots live under `data/cache/snapshots/<dataset>/<YYYY-MM-DD>/`.

Sponsor snapshot:

- `raw.csv`
- `clean.csv`
- `register_stats.json`
- `manifest.json`

Companies House snapshot:

- `raw.zip` (when source is ZIP)
- `raw.csv` (extracted or direct CSV)
- `clean.csv`
- `index_tokens_<bucket>.csv`
- `profiles_<bucket>.csv`
- `manifest.json`

## Snapshot Date Derivation

- Use the first match of `r"(20\d{2}-\d{2}-\d{2})"` in the source filename.
- If no match is found, fall back to the download date in UTC.

## Atomic Writes

Snapshots are written to a staging directory first:

- `data/cache/snapshots/<dataset>/.tmp-<uuid>`

The directory is renamed to the final `<YYYY-MM-DD>` path only after all artefacts and
`manifest.json` are written.

## Latest Snapshot Resolution

When explicit paths are not provided, the latest snapshot is resolved by:

1. `snapshot_date` descending (ISO `YYYY-MM-DD`)
2. Manifest mtime descending as a deterministic tie-breaker

## Manifest Schema

Each snapshot includes `manifest.json` with these fields:

- `dataset`
- `snapshot_date`
- `source_url`
- `downloaded_at_utc` (ISO 8601, timezone-aware)
- `last_updated_at_utc` (ISO 8601, timezone-aware)
- `schema_version`
- `sha256_hash_raw`
- `sha256_hash_clean`
- `bytes_raw`
- `row_counts` (raw and clean)
- `artefacts` (relative paths)
- `git_sha` (from `GIT_SHA` or `unknown`)
- `tool_version` (package version or `0.0.0+unknown`)
- `command_line`

## Cache-Only Usage

`run-all` and `transform-enrich` (file source) consume clean snapshot artefacts only and
fail fast if required paths are missing. Raw artefacts are retained for audit but are not
used during cache-only runs.
