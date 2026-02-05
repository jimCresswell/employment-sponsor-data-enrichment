# Companies House File Source

This document records the file-first Companies House lookup strategy used when
`CH_SOURCE_TYPE=file`. It applies to cache-only runs and snapshot-backed enrichment.

## Snapshot Artefacts

The file source reads these snapshot artefacts (under `data/cache/snapshots/companies_house/<YYYY-MM-DD>/`):

- `clean.csv` (canonical `ch_clean_v1` rows)
- `index_tokens_<bucket>.csv` (token → company number index buckets)
- `profiles_<bucket>.csv` (bucketed profiles using canonical headers)

## Token Index

- Token source: `normalise_org_name(company_name)`.
- Tokens are split on whitespace and de-duplicated; tokens shorter than 2 characters
  are dropped.
- Bucket by first character: `a-z`, `0-9`, and `_` for all other characters.
- Index files are CSV with headers `token,company_number`.

## Candidate Retrieval Rules

- Build a token set from all sponsor organisations using `generate_query_variants`
  and `normalise_org_name`.
- Load only the index buckets required for the token set.
- Count token hits per company number.
- Minimum hits: 2 for queries with 2+ tokens, otherwise 1.
- Order candidates by hit count (descending), then `company_number` for stability.
- Cap results at `CH_FILE_MAX_CANDIDATES` (default 500).

## Profile Lookup

- Profiles are stored in bucketed `profiles_<bucket>.csv` files using canonical headers.
- Buckets are loaded on demand, not all at once.
- A full in-memory profile map is optional and only used when memory headroom is proven.

## Configuration

- `CH_SOURCE_TYPE=file`
- `CH_CLEAN_PATH` (optional override for `clean.csv`)
- `CH_TOKEN_INDEX_DIR` (optional override for the snapshot directory)
- `CH_FILE_MAX_CANDIDATES` (candidate cap; default 500)
