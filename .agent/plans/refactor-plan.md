# Refactor Plan: Domain + Infrastructure + Observability

## Scope
Refactor the pipeline into explicit domains, reusable infrastructure modules, and a shared observability layer while preserving behavior. TDD is mandatory; every change starts with tests.

## Proposed Module Splits

### Observability
- `src/uk_sponsor_pipeline/observability/logging.py`
  - Standard logger factory with UTC timestamps and consistent line format.
  - Optional context helper for structured fields.

### Infrastructure
- `src/uk_sponsor_pipeline/infrastructure/http.py`
  - `CachedHttpClient` and HTTP response handling.
- `src/uk_sponsor_pipeline/infrastructure/cache.py`
  - `DiskCache`, `InMemoryCache`.
- `src/uk_sponsor_pipeline/infrastructure/resilience.py`
  - `RateLimiter`, `RetryPolicy`, `CircuitBreaker`, backoff + jitter helpers.
- `src/uk_sponsor_pipeline/infrastructure/filesystem.py`
  - `LocalFileSystem`, `InMemoryFileSystem`.
- `src/uk_sponsor_pipeline/infrastructure/__init__.py`
  - Backward-compatible exports only during refactor (then remove).

### Domains
- `src/uk_sponsor_pipeline/domain/sponsor_register/`
  - Stage 1 parsing, filtering, aggregation rules.
- `src/uk_sponsor_pipeline/domain/organization_identity/`
  - Normalization, query variants, similarity scoring.
- `src/uk_sponsor_pipeline/domain/companies_house/`
  - Candidate scoring, match selection, profile-to-row mapping.
- `src/uk_sponsor_pipeline/domain/scoring/`
  - Stage 3 feature extraction + scoring rules.

### Application
- `src/uk_sponsor_pipeline/application/pipeline.py`
  - Orchestration, batching, resume/reporting.

## Phased Plan (TDD First)

### Phase 0 — Baseline Characterization
- Add characterization tests for Stage 2 matching outputs and resume report fields.
- DoD:
  - Tests capture current behavior.
  - No production code changes.
- Gates: `format → typecheck → lint → test`.

### Phase 1 — Observability Extraction
- Create `observability/logging.py` and replace direct logging in Stage 2.
- TDD: unit test for logger format and usage.
- DoD:
  - Log lines use standard UTC format.
  - No functional behavior changes.
- Gates after completion.

### Phase 2 — Infrastructure Split
- Move cache/resilience/http/filesystem into new modules.
- Keep stable imports through `infrastructure/__init__.py` during transition.
- TDD: update tests and add contract tests for resilience primitives.
- DoD:
  - Tests green with new module layout.
  - No behavior changes.
- Gates after each extraction.

### Phase 3 — Domain Extraction (Companies House)
- Extract candidate scoring, match selection, and mapping logic.
- TDD: unit tests for scoring components and match selection.
- DoD:
  - Stage 2 outputs unchanged.
  - Domain code has no infra imports.
- Gates after extraction.

### Phase 4 — Domain Extraction (Identity + Stage 1)
- Move normalization + query variants to `organization_identity`.
- Move Stage 1 rules to `sponsor_register`.
- TDD: port and expand tests.
- DoD:
  - Stage 1 outputs unchanged.
  - Domain modules are pure.
- Gates after each move.

### Phase 5 — Domain Extraction (Scoring)
- Move Stage 3 feature extraction + scoring to `scoring` domain.
- TDD: ensure tests target domain functions directly.
- DoD:
  - Stage 3 outputs unchanged.
  - No infra imports in domain code.
- Gates after extraction.

### Phase 6 — Application Orchestration
- Extract orchestration to `application/pipeline.py`.
- TDD: end-to-end test with in-memory FS/HTTP still passes.
- DoD:
  - CLI is thin, orchestration centralized.
  - Resume/batching/reporting owned by application.
- Gates after extraction.

### Phase 7 — Docs + ADR Updates
- Add/adjust ADRs for new boundaries + observability.
- Update README structure section.
- DoD:
  - Docs and ADRs match code structure.
- Gates: full suite including coverage.

## Acceptance Criteria
- Domain modules are pure and contain no infrastructure imports.
- Infrastructure is reusable across domains.
- Observability is centralized and used by stages.
- All tests are network-isolated.
- Characterization tests prove no behavioral regressions.
- Public APIs for refactored modules are comprehensively documented in code and README(s).
- All gates pass in order: `format → typecheck → lint → test → coverage`.

## Definition of Done
- Every new boundary has unit tests + protocol/contract tests.
- No `Any` in domain code; use dataclasses/TypedDicts/Protocols.
- CLI uses application orchestration only.
- ADRs updated for new boundaries and observability.
- Public APIs are documented in module docstrings and referenced in README(s).
