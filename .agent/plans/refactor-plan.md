# Refactor Plan: Domain + Infrastructure + Observability

## Entry Point (Read This First)

- Read `.agent/directives/AGENT.md`, then `.agent/directives/rules.md`.
- Ensure the current baseline is green before starting Phase 0:
  - `uv sync --extra dev`
  - `uv run format`
  - `uv run typecheck`
  - `uv run lint`
  - `uv run test`
  - `uv run coverage`
  - (Shortcut: `uv run check` runs the full sequence.)
- Scope: changes are within `src/uk_sponsor_pipeline` and must preserve CLI behaviour.
- Refactor constraints apply: no compatibility shims; the pipeline must be excellent at the end of each phase.
- Public APIs must be documented in module docstrings (with examples) and referenced in README(s) and ADRs in the same phase.

## Current State and Decisions (2026-02-01)

This plan is the authoritative entry point for the refactor. It captures the key decisions and changes made so far; assume no other context.

- Stages are **artefact boundaries only**. Architecture is application‑owned orchestration with shared infrastructure (ADR 0012). ADR 0003 is superseded.
- Configuration is read once at the CLI entry point and passed through. Stage entry points require `PipelineConfig`.
- Stage 2 fails fast on auth/rate‑limit/circuit‑breaker and unexpected HTTP errors; resumable artefacts are written before exit.
- All linting runs via `uv run lint` (ruff + import‑linter); no separate lint entry points.
- British spelling throughout docs; code identifiers use British spelling unless constrained by external names.
- Test doubles will live in `tests/fakes/`; `conftest.py` provides fixtures only.
- `Any` is allowed only at IO boundaries; external data is validated into strict `TypedDict`/dataclass shapes immediately after ingestion (ADR 0013).
- Ruff `ANN` (incl. `ANN401`) is enabled; per-file ignores are limited to IO boundary modules and tests.
- Import-linter contracts are enforced in `uv run lint`/`uv run check`.

### Changes already applied in the repo

- `run_stage2` and `run_stage3` now require `PipelineConfig`; the CLI loads config once and passes it through.
- Stage 2 search errors are fail‑fast with clear messages; resume artefacts are still written.
- New tests cover config preservation and fail‑fast behaviour (`tests/test_config.py`, Stage 2/3 tests).
- ADR 0012 added; ADR 0003 marked superseded; README updated with architecture direction and config pass‑through guidance.
- Phase 0 complete: characterisation tests added under `tests/characterisation/` with a local README.
- Phase 1 complete: shared logger factory in `src/uk_sponsor_pipeline/observability/logging.py`; Stage 1–3 logging standardised; README and ADR 0012 updated.
- Phase 2 complete: infrastructure split into `src/uk_sponsor_pipeline/infrastructure/`; resilience protocols added to `protocols.py`; test fakes moved to `tests/fakes/`; README and ADR 0005 updated.
- Phase 3 complete: Companies House candidate scoring and mapping extracted to `src/uk_sponsor_pipeline/domain/companies_house.py` with new domain tests; Stage 2 now delegates to the domain module; README updated with domain structure.
- Strict typing added: `src/uk_sponsor_pipeline/types.py` defines internal `TypedDict` contracts; Stage 2 coerces/validates Companies House payloads at IO boundaries; Stage 3 consumes typed rows.
- ADR 0013 added (Strict Internal Typing After IO Boundaries).
- Import-linter wired into `uv run lint`/`uv run check` with contracts that block domain→infrastructure/CLI/stages and infrastructure→domain/types.

### Resumption checklist (fresh session)

- Read `.agent/directives/AGENT.md` and `.agent/directives/rules.md`.
- Run the full gates (`uv run check`) before starting Phase 0 or any new phase.
- Confirm ADR 0012 is present and ADR 0003 is marked superseded.
- Confirm characterisation tests live under `tests/characterisation/` and are marked as temporary scaffolding.
- Use this plan as the single source of truth; update it if the repo state diverges.

## Scope

Refactor the pipeline into explicit domains, reusable infrastructure modules, and a shared observability layer while preserving behaviour. TDD is mandatory; every change starts with tests. Clean breaks only: remove legacy code paths in the same phase they are replaced so there is a single source of truth.

## Refactor Constraints

- It is acceptable for the pipeline to be temporarily broken while a phase is in progress.
- The pipeline must be fully working and excellent at the end of each phase.
- No compatibility shims at any point.
- Documentation is never deferred: inline docs, README(s), and ADRs are updated in the same phase as the code change and remain cross-referenced and DRY.
- Stages are conceptual labels for pipeline steps and outputs, not architectural boundaries. Prefer application pipeline steps/use-cases and shared infrastructure; keep `stages/` thin or remove it once the application layer owns orchestration.
- All standards (observability, resilience, filesystem, HTTP, error handling) are shared across the pipeline; no stage-specific infrastructure.
- All linting (ruff + import-linter) runs via `uv run lint`; no separate lint gate.

## Test Harness Constraints

- Tests are network-isolated via socket blocking in `tests/conftest.py`; no real HTTP calls.
- Characterisation and refactor tests must use `FakeHttpClient`, `InMemoryFileSystem`, or MagicMock sessions.
- All fixtures/data used for tests must be local and deterministic.
- Test fakes live in `tests/fakes/` (not in production code); `conftest.py` provides fixtures that instantiate them:

  ```text
  tests/
  ├── conftest.py              # pytest fixtures only
  ├── fakes/
  │   ├── __init__.py          # export all fakes
  │   ├── http.py              # FakeHttpClient
  │   ├── filesystem.py        # InMemoryFileSystem
  │   ├── cache.py             # InMemoryCache
  │   └── resilience.py        # FakeRateLimiter, FakeCircuitBreaker
  └── ...
  ```

## Proposed Module Splits

### Observability

- `src/uk_sponsor_pipeline/observability/logging.py`
  - Standard logger factory with UTC timestamps and consistent line format.
  - Optional context helper for structured fields.

### Infrastructure

- `src/uk_sponsor_pipeline/infrastructure/http.py`
  - `CachedHttpClient` and HTTP response handling.
- `src/uk_sponsor_pipeline/infrastructure/cache.py`
  - `DiskCache` (production only; `InMemoryCache` lives in `tests/fakes/`).
- `src/uk_sponsor_pipeline/infrastructure/resilience.py`
  - `RateLimiter`, `RetryPolicy`, `CircuitBreaker`, backoff + jitter helpers.
- `src/uk_sponsor_pipeline/infrastructure/filesystem.py`
  - `LocalFileSystem` (production only; `InMemoryFileSystem` lives in `tests/fakes/`).
- `src/uk_sponsor_pipeline/infrastructure/__init__.py`
  - Only final, canonical exports.

### Protocols (DI Contracts)

- `src/uk_sponsor_pipeline/protocols.py` defines abstract interfaces for all injectable dependencies and is the only place application and domain code import DI contracts:
  - `HttpClient`, `Cache`, `FileSystem` (existing).
  - `RateLimiter`, `CircuitBreaker`, `RetryPolicy` (add in Phase 2 for testability; `CachedHttpClient` depends on these protocols, not concrete implementations).

### Domains

- `src/uk_sponsor_pipeline/domain/sponsor_register.py`
  - Stage 1 parsing, filtering, aggregation rules.
- `src/uk_sponsor_pipeline/domain/organisation_identity.py`
  - Move existing `normalization.py` here + extract `_simple_similarity()` from Stage 2.
  - Contains: `NormalizedName`, `normalize_org_name()`, `generate_query_variants()`, `simple_similarity()`.
- `src/uk_sponsor_pipeline/domain/companies_house.py`
  - Candidate scoring (uses `simple_similarity` from `organisation_identity`), match selection, profile-to-row mapping.
- `src/uk_sponsor_pipeline/domain/scoring.py`
  - Stage 3 feature extraction + scoring rules.

### Application

- `src/uk_sponsor_pipeline/application/pipeline.py`
  - Orchestration, batching, resume/reporting.
  - Pipeline steps are owned here (not in `stages/`).
  - Config/env read once at the entry point; pass config and dependencies through.

## Target Structure (SOLID/DI)

### Application Steps (use-cases)

Application owns the pipeline steps; stages (if kept) are thin wrappers only.

- `download_register(...) -> DownloadResult`
  - Wraps GOV.UK fetch + schema validation.
- `build_sponsor_register_snapshot(...) -> Stage1Result`
  - Filters Skilled Worker + A‑rated, aggregates by org.
- `enrich_with_companies_house(...) -> Stage2Outputs`
  - Search + match + profile fetch + resume reporting.
- `score_tech_likelihood(...) -> Stage3Outputs`
  - Feature extraction + scoring + shortlist + explainability.

### Mapping from Current Modules

- `stages/download.py` → `application.pipeline.download_register`
- `stages/stage1.py` → `application.pipeline.build_sponsor_register_snapshot`
- `stages/stage2_companies_house.py` → `application.pipeline.enrich_with_companies_house`
- `stages/stage3_scoring.py` → `application.pipeline.score_tech_likelihood`

If `stages/` remains, each function must be a pure delegate to the application step and contain no infrastructure setup beyond dependency wiring for CLI.

### Shared Standards (Applied Everywhere)

- Error handling: fail fast with clear, domain‑specific errors; write resumable artefacts before exiting.
- Observability: standard logger + structured context; no ad‑hoc logging.
- Infrastructure: single implementations of HTTP/cache/resilience/filesystem, injected via protocols.
- Configuration: read once at the CLI entry point and pass through to all application steps.

## Phased Plan (TDD First)

### Phase 0 — Baseline Characterization

- Add characterisation tests for Stage 1, Stage 2, and Stage 3 outputs.
- Add characterisation tests for Stage 2 error handling (auth/rate limit/circuit breaker on search vs profile fetch) so any changes are explicit.
- Split tests into:
  - **Core behaviour** (must remain after refactor).
  - **Scaffolding** (temporary to guard the refactor; remove once the target module is stable).
- Use the network-blocked test harness: no live HTTP, use fakes/in-memory FS.
- DoD:
  - Tests capture current behaviour.
  - No production code changes.
- Gates: `format → typecheck → lint → test → coverage`.
 - Status: ✅ Completed.

### Phase 1 — Observability Extraction

- Create `observability/logging.py` and replace direct logging in Stages 1, 2, and 3.
- TDD: unit test for logger format and usage.
- DoD:
  - Log lines use standard UTC format.
  - No functional behaviour changes.
  - Docs updated (module docstrings + README/ADR references).
- Gates: `format → typecheck → lint → test → coverage`.
 - Status: ✅ Completed.

### Phase 2 — Infrastructure Split

- Move cache/resilience/http/filesystem into new modules.
- Update all imports and delete the old module(s) in the same phase.
- Add protocols for resilience primitives (`RateLimiter`, `CircuitBreaker`, `RetryPolicy`) to enable DI and testability.
- Create `tests/fakes/` directory and move test doubles from `conftest.py`:
  - `tests/fakes/http.py` — `FakeHttpClient`
  - `tests/fakes/filesystem.py` — `InMemoryFileSystem`
  - `tests/fakes/cache.py` — `InMemoryCache`
  - `tests/fakes/resilience.py` — `FakeRateLimiter`, `FakeCircuitBreaker`
- Update `conftest.py` to import fakes and provide fixtures.
- TDD: update tests and add contract tests for resilience primitives (protocol conformance + behaviour).
- DoD:
  - Tests green with new module layout.
  - No behaviour changes.
  - Resilience protocols defined and implemented.
  - Test fakes separated into `tests/fakes/`.
  - Docs updated (module docstrings + README/ADR references, including testing guidance for `tests/fakes/`).
- Gates: `format → typecheck → lint → test → coverage`.
- Status: ✅ Completed.

### Phase 3 — Domain Extraction (Companies House)

- Extract candidate scoring, match selection, and mapping logic.
- Remove legacy implementations immediately after migration.
- TDD: unit tests for scoring components and match selection.
- DoD:
  - Stage 2 outputs unchanged.
  - Domain code has no infra imports.
  - Docs updated (module docstrings + README/ADR references).
- Gates: `format → typecheck → lint → test → coverage`.
 - Status: ✅ Completed.

### Phase 4 — Domain Extraction (Identity + Stage 1)

- Move `normalization.py` → `domain/organisation_identity.py` (this is mostly a move, not a rewrite).
- Extract `_simple_similarity()` from `stage2_companies_house.py` → `domain/organisation_identity.py`.
- Move Stage 1 rules to `domain/sponsor_register.py`.
- Delete the old modules immediately after migration.
- TDD: port and expand tests.
- DoD:
  - Stage 1 outputs unchanged.
  - Domain modules are pure (no infra imports).
  - `organisation_identity` contains all name-handling logic.
  - Docs updated (module docstrings + README/ADR references).
- Gates: `format → typecheck → lint → test → coverage`.

### Phase 5 — Domain Extraction (Scoring)

- Move Stage 3 feature extraction + scoring to `scoring` domain.
- Remove legacy code immediately after migration.
- TDD: ensure tests target domain functions directly.
- DoD:
  - Stage 3 outputs unchanged.
  - No infra imports in domain code.
  - Docs updated (module docstrings + README/ADR references).
- Gates: `format → typecheck → lint → test → coverage`.

### Phase 6 — Application Orchestration

- Extract orchestration to `application/pipeline.py`.
- Remove any legacy orchestration paths immediately after migration.
- Eliminate or reduce `stages/` to thin wrappers (if kept, they must be pure delegates to application steps).
- TDD: end-to-end test with in-memory FS/HTTP still passes.
- DoD:
  - CLI is thin, orchestration centralised.
  - Resume/batching/reporting owned by application.
  - Config/env read once at the CLI entry point; stages accept config/dependencies only.
  - Docs updated (module docstrings + README/ADR references).
- Gates: `format → typecheck → lint → test → coverage`.

### Phase 7 — Docs + ADR Audit

- Add/adjust ADRs for new boundaries + observability.
- Record the application‑owned pipeline decision (ADR 0012) and mark ADR 0003 as superseded.
- Update README structure section and cross-references.
- Rename test files to match new module structure:
  - `test_stage2.py` → `test_domain_companies_house.py` (or mirror: `tests/domain/test_companies_house.py`)
  - `test_infrastructure.py` → split into `test_infrastructure_http.py`, `test_infrastructure_resilience.py`, etc.
- Add `import-linter` configuration to enforce architectural boundaries and wire it into `uv run lint` (single lint entry point):
  - Add `import-linter` as a dev dependency.
  - Update `uk_sponsor_pipeline.devtools:lint` to run `import-linter` after ruff.

  ```ini
  [importlinter:contract:1]
  name = Domain must not import infrastructure
  type = forbidden
  source_modules = uk_sponsor_pipeline.domain
  forbidden_modules = uk_sponsor_pipeline.infrastructure

  [importlinter:contract:2]
  name = Domain must not import application
  type = forbidden
  source_modules = uk_sponsor_pipeline.domain
  forbidden_modules = uk_sponsor_pipeline.application
  ```

- DoD:
  - Docs and ADRs match code structure.
  - Test files renamed to match module structure.
  - `import-linter` rules in place and passing via `uv run lint`.
  - Scaffolding characterisation tests removed.
- Gates: `format → typecheck → lint → test → coverage`.

## Acceptance Criteria

- Domain modules are pure and contain no infrastructure imports.
- Infrastructure is reusable across domains.
- Observability is centralised and used by the application pipeline steps.
- All tests are network-isolated.
- Characterisation tests prove no behavioural regressions.
- Fail fast with helpful errors; resumable outputs are preserved for recovery.
- Public APIs for refactored modules are comprehensively documented in code and README(s).
- No duplicate logic or legacy code paths remain; single source of truth per module.
- All gates pass in order: `format → typecheck → lint → test → coverage`.

## Definition of Done

- Every new boundary has unit tests + protocol/contract tests.
- No `Any` in domain code; use dataclasses/TypedDicts/Protocols.
- CLI uses application orchestration only.
- ADRs updated for new boundaries and observability.
- Public APIs are documented in module docstrings and referenced in README(s).
- Scaffolding characterisation tests removed after stabilisation.
