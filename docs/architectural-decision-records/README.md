# Architectural Decision Records

This directory contains the ADRs for the UK Sponsor → Hiring Signals Pipeline.

## Index

- `adr0001-record-architecture-decisions.md`
- `adr0002-python-3-14-and-uv-tooling.md`
- `adr0004-config-loaded-at-cli-and-passed-through.md`
- `adr0005-dependency-injection-for-io-and-http.md`
- `adr0006-network-isolated-test-strategy.md`
- `adr0007-companies-house-api-client-guardrails.md`
- `adr0008-transform-enrich-batching-resume-and-reporting.md`
- `adr0009-transform-enrich-matching-and-audit-trail.md`
- `adr0010-transform-score-tech-likelihood-scoring.md`
- `adr0011-no-dashboard-plugins-or-sqlite.md`
- `adr0012-artefact-boundaries-and-orchestration.md`
- `adr0013-strict-internal-typing.md`
- `adr0014-io-boundaries-consolidation.md`
- `adr0015-observability-logging.md`
- `adr0017-usage-shortlist-separation.md`
- `adr0018-linting-rules-architectural-boundaries-and-fail-fast.md`
- `adr0019-cache-first-refresh-and-bulk-companies-house-snapshots.md`
- `adr0020-file-first-companies-house-lookup.md`
- `adr0021-refresh-step-groups-and-staged-acquire-clean.md`
- `adr0022-file-only-runtime-io-boundaries-and-single-region-filtering.md`
- `adr0023-file-mode-enrichment-throughput-strategy.md`

## Superseded

- `superseded/adr0003-csv-artefact-pipeline.md`
- `adr0016-configurable-companies-house-source.md`

## Related Non-ADR Runtime Contracts

- `docs/data-contracts.md` (schema and deterministic validation contracts)
- `docs/validation-protocol.md` (operational runbook and verification commands)
