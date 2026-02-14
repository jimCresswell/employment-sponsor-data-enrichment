# Snapshot Artefacts

Snapshots are the contract between refresh commands and cache-only runtime steps.
They are designed for reproducibility, auditability, and safe reruns.

## Why Snapshots Matter

Snapshots provide:

- deterministic inputs for `admin build enrich` and `admin build all`,
- explicit artefact boundaries for auditing and incident recovery,
- fail-fast validation when required files are missing.

## Snapshot Root and Layout

Default root:

```text
data/cache/snapshots/
```

Each dataset writes dated snapshots:

```text
data/cache/snapshots/<dataset>/<YYYY-MM-DD>/
```

### Sponsor Snapshot Artefacts

- `raw.csv`
- `clean.csv`
- `register_stats.json`
- `manifest.json`

### Companies House Snapshot Artefacts

- `raw.zip` (when source is ZIP)
- `raw.csv` (direct source or extracted from ZIP)
- `clean.csv`
- `index_tokens_<bucket>.csv`
- `profiles_<bucket>.csv`
- `manifest.json`

## Refresh Lifecycle (Discovery -> Acquire -> Clean)

Refresh commands support grouped execution:

- `discovery`: resolve source URL only
- `acquire`: download raw artefacts into staging
- `clean`: finalise latest pending acquire into dated snapshot
- `all`: acquire + clean (default)

This allows staged, auditable runs and safe recovery after partial failures.

## Atomic Snapshot Commit

Snapshots are written to staging first:

```text
data/cache/snapshots/<dataset>/.tmp-<uuid>/
```

The staging directory is renamed to `<YYYY-MM-DD>` only after all artefacts and
`manifest.json` are written. This prevents partially-written snapshots from being
used by runtime pipeline steps.

## Snapshot Date Derivation

1. First match of `r"(20\d{2}-\d{2}-\d{2})"` in source filename.
2. Fallback: download date in UTC.

## Latest Snapshot Resolution

When explicit paths are not provided, the latest snapshot is resolved by:

1. `snapshot_date` descending (`YYYY-MM-DD`)
2. `manifest.json` mtime descending (tie-breaker)

`admin build enrich` and `admin build all` rely on this behaviour when only `SNAPSHOT_ROOT`
is provided.

## Manifest Contract

Each snapshot includes `manifest.json` with:

- `dataset`
- `snapshot_date`
- `source_url`
- `downloaded_at_utc` (ISO 8601, timezone-aware)
- `last_updated_at_utc` (ISO 8601, timezone-aware)
- `schema_version`
- `sha256_hash_raw`
- `sha256_hash_clean`
- `bytes_raw`
- `row_counts`
- `artefacts` (relative paths)
- `git_sha` (`GIT_SHA` or `unknown`)
- `tool_version` (package version or `0.0.0+unknown`)
- `command_line`

## Runtime Consumption Rules

Cache-only runtime steps consume clean snapshot artefacts only:

- Sponsor: `clean.csv`
- Companies House: `clean.csv` plus token/profile index files

Raw artefacts remain for audit and troubleshooting but are not required by runtime
processing once clean artefacts are available.

## Manual Verification Checklist

After refresh completes:

1. Confirm dated directories exist under both datasets.
2. Confirm expected artefacts exist for each dataset.
3. Open `manifest.json` and verify `schema_version` and `snapshot_date`.
4. Confirm `clean.csv` headers match `docs/data-contracts.md`.
5. Run `uv run uship admin build all` to validate cache-only consumption.

## Recovery Notes

- If `--only clean` fails because no pending snapshot exists, run `--only acquire` first.
- If runtime steps fail with missing snapshot artefacts, rerun refresh commands or set
  explicit `SPONSOR_CLEAN_PATH`, `CH_CLEAN_PATH`, and `CH_TOKEN_INDEX_DIR`.
- See `docs/troubleshooting.md` for failure-mode-specific recovery paths.
