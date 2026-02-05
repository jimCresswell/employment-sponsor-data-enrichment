# ADR 0020: File-First Companies House Lookup Strategy

Date: 2026-02-05

## Status

Accepted

## Context

Companies House bulk snapshots are large enough that full in-memory loading is not viable
on typical developer machines. The pipeline must support cache-only, reproducible runs
without API calls, while keeping matching deterministic and audit-friendly.

## Decision

- Use a token index stored as CSV buckets: `index_tokens_<bucket>.csv` with headers
  `token,company_number`.
- Tokens are derived from `normalise_org_name(company_name)`, split on whitespace,
  de-duplicated, and filtered to length ≥ 2.
- Bucket by first character: `a-z`, `0-9`, and `_` for all other characters.
- Candidate retrieval counts token hits across all query tokens. Require at least two
  hits when there are two or more tokens, otherwise require one hit.
- Order candidates by hit count (descending) then `company_number` for stability, and
  cap results at `CH_FILE_MAX_CANDIDATES` (default 500).
- Profile lookup is file-backed via bucketed `profiles_<bucket>.csv` files using the
  canonical clean schema (`ch_clean_v1`). Buckets are loaded on demand.
- A full in-memory profile map is optional and only permitted when memory headroom is
  proven; the default remains bucketed profiles.

## Consequences

- File-first matching is deterministic, cache-only, and memory-safe.
- Refresh commands must generate token index buckets and profile buckets as snapshot
  artefacts, and include them in the manifest.
- API access remains available but is explicitly opt-in when `CH_SOURCE_TYPE=api`.
