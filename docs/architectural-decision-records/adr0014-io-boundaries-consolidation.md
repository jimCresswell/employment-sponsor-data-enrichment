# ADR 0014: Consolidate Incoming IO Boundaries

Date: 2026-02-01

## Status

Accepted

## Context

Incoming filesystem and network IO boundaries were spread across multiple modules (stage modules and cache helpers). This made it harder to enforce the “unknown only at IO boundaries” rule and to audit where untrusted data enters the system.

## Decision

Consolidate incoming IO boundaries into two infrastructure files:

- `infrastructure/io/filesystem.py` for all filesystem reads (including cache reads via `DiskCache`)
- `infrastructure/io/http.py` for all network reads (Companies House and GOV.UK fetches)

Stages must use the `FileSystem` and `HttpSession` / `HttpClient` protocols rather than calling `requests` or filesystem APIs directly.

Validation helpers live in `infrastructure/io/validation.py` and are used to convert untrusted payloads into strict types at the boundary.
Stages and application logic must not import `requests` or perform filesystem/network IO directly; they only depend on protocols.

## Consequences

- IO boundaries are explicit and auditable.
- Incoming untrusted data is centralised, making validation and parsing consistent.
- Cache handling is treated as filesystem IO, keeping boundary logic in one place.
