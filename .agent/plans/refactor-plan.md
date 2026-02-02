# Refactor Plan: Domain-Core ETL + Usage Pipeline (Standalone Entry Point)

## Entry Point (Read This First)

This document is the **single source of truth** for the refactor. Assume no other context.

- Read `.agent/directives/AGENT.md`, then `.agent/directives/rules.md`.
- Ensure the current baseline is green before any new changes:
  - `uv sync --group dev`
  - `uv run format`
  - `uv run typecheck`
  - `uv run lint`
  - `uv run test`
  - `uv run coverage`
  - (Shortcut: `uv run check` runs the full sequence.)
- Scope: changes are within `src/uk_sponsor_pipeline` and must preserve CLI behaviour.
- Refactor constraints apply: no compatibility shims; the pipeline must be excellent at the end of each phase.
- Public APIs must be documented in module docstrings (with examples) and referenced in README(s) and ADRs in the same phase.

## Current Status (2026-02-02)

- Phase 0–4 are complete and gated.
- Phase 5 (Domain Extraction: Scoring) is complete and gated.
- Phase 6 is optional; Phase 7 is the near-term docs/ADR audit; Phase 11 is the final cleanup/docs audit phase.
- Domain is the core: domain code must not import application, CLI, stages, or infrastructure.

## Target End State (Acceptance Criteria)

These criteria define the final, measurable outcomes for this plan:

- No usage of the word “stage” in `src/`, `tests/`, `README.md`, or `docs/` (except historical ADR archives under `docs/architectural-decision-records/archive/` if created).
- CLI commands and help text use semantic ETL/usage naming (no `stage*` commands).
- Artefact names and directories are semantic (no `stage*` filenames).
- ETL transforms produce immutable artefacts; usage/query steps only read artefacts and write usage outputs.
- Domain is core and remains free of application/CLI/stages/infrastructure imports (import-linter passes).
- Full gates pass: `format → typecheck → lint → test → coverage`.
- A repo-wide scan exists at `reports/stage-usage.txt` to guide renames; it is not exhaustive and must not replace comprehensive validation.

## Latest Completed Work (Phase 4 Summary)

- `normalization.py` removed; replaced by `domain/organisation_identity.py` (includes `simple_similarity`).
- Stage 1 rules moved into `domain/sponsor_register.py`; Stage 1 delegates to domain.
- Town/county now handled as structured collections in core logic; flattened only at IO boundaries.
- README updated to reflect new module layout.
- New tests: `tests/test_domain_sponsor_register.py`; `tests/test_normalization.py` now targets the domain module.
- Full gates passed via `uv run check`.

## Current Structure Snapshot (Required Context for Fresh Session)

- Application layer exists and owns core logic:
  - `src/uk_sponsor_pipeline/application/download.py`
  - `src/uk_sponsor_pipeline/application/stage1.py`
  - `src/uk_sponsor_pipeline/application/stage2_companies_house.py`
  - `src/uk_sponsor_pipeline/application/stage3_scoring.py`
- `stages/` are thin delegates only (no business logic). Do not re‑refactor them.
- Infrastructure IO boundaries are centralised in:
  - `src/uk_sponsor_pipeline/infrastructure/io/http.py`
  - `src/uk_sponsor_pipeline/infrastructure/io/filesystem.py`
  - `src/uk_sponsor_pipeline/infrastructure/io/validation.py`
- Companies House HTTP client construction is centralised in infrastructure via
  `build_companies_house_client` (no `requests` imports in application/stages).
- Domain modules now include `organisation_identity.py`, `sponsor_register.py`, and `scoring.py`.

## Remaining Work Summary (Fresh Session Checklist)

- Phase 6 (optional): consolidate use‑cases into `application/pipeline.py`.
- Phase 7: docs/ADR audit + test renames (current structure); keep scaffolding tests.
- Phase 8: location aliases (London/Manchester) and wiring into geographic filtering.
- Phase 9: remove stage terminology across the repo with semantic replacements.
- Phase 10: split ETL transforms from usage/query logic with independent usage execution.
- Phase 11: final tidy up (remove scaffolding tests, final docs/ADR/terminology sweep).

## Current State and Decisions (2026-02-01)

This plan is the authoritative entry point for the refactor. It captures the key decisions and changes made so far; assume no other context.

- Stages are **artefact boundaries only**. Architecture is application‑owned orchestration with shared infrastructure (ADR 0012). ADR 0003 is superseded.
- Configuration is read once at the CLI entry point and passed through. Stage entry points require `PipelineConfig`.
- Stage 2 fails fast on auth/rate‑limit/circuit‑breaker and unexpected HTTP errors; resumable artefacts are written before exit.
- If `resume=False`, Stage 2 must write to a new output directory to avoid stale data reuse.
- All linting runs via `uv run lint` (ruff + import‑linter); no separate lint entry points.
- British spelling throughout docs; code identifiers use British spelling unless constrained by external names.
- Test doubles will live in `tests/fakes/`; `conftest.py` provides fixtures only.
- `Any` is allowed only at IO boundaries; external data is validated into strict `TypedDict`/dataclass shapes immediately after ingestion (ADR 0013).
- Ruff `ANN` (incl. `ANN401`) is enabled; per-file ignores are limited to IO boundary modules and tests.
- Import-linter contracts are enforced in `uv run lint`/`uv run check`.
- Domain is the core: domain code must not import application, CLI, stages, or infrastructure.
- Reproducibility is mandatory: avoid hidden time dependencies unless explicitly accepted (age-based scoring uses `datetime.now()` by decision).
- User-facing text and documentation use British spelling; enforce via shared strings/constants where practical.

### Changes already applied in the repo

- `run_stage2` and `run_stage3` now require `PipelineConfig`; the CLI loads config once and passes it through.
- Stage 2 search errors are fail‑fast with clear messages; resume artefacts are still written.
- New tests cover config preservation and fail‑fast behaviour (`tests/test_config.py`, Stage 2/3 tests).
- ADR 0012 added; ADR 0003 marked superseded; README updated with architecture direction and config pass‑through guidance.
- Phase 0 complete: characterisation tests added under `tests/characterisation/` with a local README.
- Phase 1 complete: shared logger factory in `src/uk_sponsor_pipeline/observability/logging.py`; Stage 1–3 logging standardised; README and ADR 0012 updated.
- Phase 2 complete: infrastructure split into `src/uk_sponsor_pipeline/infrastructure/io/` plus `resilience.py`; resilience protocols added to `protocols.py`; test fakes moved to `tests/fakes/`; README and ADR 0005 updated.
- Phase 3 complete: Companies House candidate scoring and mapping extracted to `src/uk_sponsor_pipeline/domain/companies_house.py` with new domain tests; Stage 2 now delegates to the domain module; README updated with domain structure.
- Strict typing added: `src/uk_sponsor_pipeline/types.py` defines internal `TypedDict` contracts; Stage 2 coerces/validates Companies House payloads at IO boundaries; Stage 3 consumes typed rows.
- ADR 0013 added (Strict Internal Typing After IO Boundaries).
- Import-linter wired into `uv run lint`/`uv run check` with contracts that block domain→infrastructure/CLI/stages and infrastructure→domain/types.
- Application layer added: `src/uk_sponsor_pipeline/application/*` hosts Stage 1–3 and download use-cases. `stages/` are now thin delegates only.
- Companies House HTTP client construction centralised in `infrastructure/io/http.py` via `build_companies_house_client`.
- ADR 0014 updated to match IO consolidation + validation.
- Boundary‑neutral IO contracts added in `io_contracts.py`; infrastructure validation no longer imports `types.py`.
- Stage 2 profile fetch errors are now fail‑fast; no `profile_error` continuation.
- `resume=False` now writes to a timestamped output subdirectory to avoid stale data reuse.
- Region filtering enforces a single region; multiple regions are rejected with a clear error.
- Phase 4 complete: `normalization.py` removed, `organisation_identity.py` added (including `simple_similarity`); Stage 1 rules moved into `domain/sponsor_register.py`; Stage 1 now flattens structured locations at IO boundaries only; README updated; new domain tests added.

### Resumption checklist (fresh session)

- Read `.agent/directives/AGENT.md` and `.agent/directives/rules.md`.
- Run the full gates (`uv run check`) before starting Phase 0 or any new phase.
- Confirm ADR 0012 is present and ADR 0003 is marked superseded.
- Confirm characterisation tests live under `tests/characterisation/` and are marked as temporary scaffolding.
- Use this plan as the single source of truth; update it if the repo state diverges.

### Known Divergences (Must Address Early)

- None currently known.

## Immediate Work Order (Linear, for the three requested fixes)

1) IO contracts boundary (unblocks import‑linter; minimal surface area). ✅ Completed
2) Stage 2 fail‑fast on profile fetch errors + new output directory when `resume=False` (behavioural changes + tests). ✅ Completed
3) Single‑region filtering enforcement in CLI/config/stage3 + docs/tests. ✅ Completed

Each step includes tests and docs updates for that change, then full gates.

### Clarified Plan — IO Contracts Boundary (Before Phase 4)

Goal: infrastructure must not import domain/internal types; validation uses IO contracts only.
Status: ✅ Completed.

1) Create `src/uk_sponsor_pipeline/io_contracts.py` with TypedDicts for inbound/outbound IO payloads used by infrastructure:
   - `SearchAddressIO`, `SearchItemIO`, `SearchResponseIO`
   - `RegisteredOfficeAddressIO`, `CompanyProfileIO`
2) Update `infrastructure/io/validation.py` to:
   - import IO contracts from `io_contracts.py`
   - validate inbound payloads into IO contracts
   - return IO contract shapes from `parse_companies_house_search` and `parse_companies_house_profile`
3) Update application/domain call sites to convert IO contracts into internal types in `types.py` at the IO boundary (Stage 2 uses existing coercion/validation patterns).
4) Add/adjust tests for IO validation to assert:
   - infrastructure depends only on IO contracts
   - parsing output shapes are stable
5) Run full gates.

DoD:
- Import-linter passes with infrastructure not importing `types.py`.
- No behavioural changes to Stage 2 outputs.

### Clarified Plan — Single-Region Filtering

Goal: region filtering accepts exactly one region; multiple regions are a user error.
Status: ✅ Completed.

1) CLI: validate `--region` so multiple values raise a clear error before running Stage 3.
2) Config: store a single region value (or empty), not a tuple, for Stage 3.
3) Stage 3: update filter logic to accept a single region string and remove tuple iteration.
4) Tests: add/adjust tests to cover:
   - multiple regions error
   - single region passes
   - no region behaves as today
5) Update docs (README/module docstrings) to show single-region usage.
6) Run full gates.

## Scope

Refactor the pipeline into explicit domains, reusable infrastructure modules, and a shared observability layer while preserving behaviour. TDD is mandatory; every change starts with tests. Clean breaks only: remove legacy code paths in the same phase they are replaced so there is a single source of truth.

## Refactor Constraints

- It is acceptable for the pipeline to be temporarily broken while a phase is in progress.
- The pipeline must be fully working and excellent at the end of each phase.
- No compatibility shims at any point.
- Documentation is never deferred: inline docs, README(s), and ADRs are updated in the same phase as the code change and remain cross-referenced and DRY.
- Stages are conceptual labels for artefact boundaries, not architectural boundaries. Prefer application pipeline steps/use-cases and shared infrastructure; keep `stages/` thin or remove it once the application layer owns orchestration.
- ETL transforms must be separated from usage/query steps. Usage reads artefacts and filters; it does not mutate upstream artefacts.
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

- `src/uk_sponsor_pipeline/infrastructure/io/http.py`
  - `CachedHttpClient`, HTTP response handling, and `build_companies_house_client`.
- `src/uk_sponsor_pipeline/infrastructure/io/filesystem.py`
  - `LocalFileSystem` + `DiskCache` (production only; `InMemoryFileSystem` lives in `tests/fakes/`).
- `src/uk_sponsor_pipeline/infrastructure/io/validation.py`
  - IO boundary validation helpers.
- `src/uk_sponsor_pipeline/infrastructure/resilience.py`
  - `RateLimiter`, `RetryPolicy`, `CircuitBreaker`, backoff + jitter helpers.
- `src/uk_sponsor_pipeline/infrastructure/__init__.py`
  - Only final, canonical exports.

### Protocols (DI Contracts)

- `src/uk_sponsor_pipeline/protocols.py` defines abstract interfaces for all injectable dependencies and is the only place application and domain code import DI contracts:
  - `HttpClient`, `Cache`, `FileSystem` (existing).
  - `RateLimiter`, `CircuitBreaker`, `RetryPolicy` (add in Phase 2 for testability; `CachedHttpClient` depends on these protocols, not concrete implementations).

### IO Contracts (Boundary-Neutral)

- `src/uk_sponsor_pipeline/io_contracts.py` (or `src/uk_sponsor_pipeline/contracts/io.py`)
  - TypedDict shapes for inbound/outbound IO payloads used by infrastructure.
  - Infrastructure validates against these shapes only.
  - Domain/application convert validated IO shapes into internal domain contracts in `types.py`.

## Semantic Pipeline Labels (ETL + Usage)

This plan replaces stage labels with semantic names while keeping artefact boundaries and CLI compatibility.

### Canonical Naming Scheme (Target)

- CLI commands:
  - `extract` (download raw sponsor register)
  - `transform-register` (filter + aggregate sponsor register)
  - `transform-enrich` (Companies House enrichment)
  - `transform-score` (score artefacts)
  - `usage-shortlist` (apply filters, produce shortlist/explain)
  - `run-all` (semantic pipeline orchestration)
- Artefact directories:
  - `data/raw/` (extract outputs)
  - `data/interim/` (transform outputs)
  - `data/processed/` (usage outputs)
- Artefact filenames:
  - `sponsor_register_raw.csv` (extract)
  - `sponsor_register_filtered.csv` (transform-register)
  - `companies_house_enriched.csv` (transform-enrich)
  - `companies_scored.csv` (transform-score)
  - `companies_shortlist.csv` (usage-shortlist)
  - `companies_explain.csv` (usage-shortlist)

### Extract

- Download sponsor register (raw CSV).
- Companies House API acquisition (search/profile) for enrichment.

### Transform

- Filter/aggregate sponsor register (Skilled Worker + A‑rated).
- Enrich with Companies House and map to typed rows.
- Score tech-likelihood (domain scoring only).

### Usage (Query/Selection)

- Apply geographic filters and thresholds to scored artefacts.
- Produce shortlist/explainability outputs without mutating upstream artefacts.

### Mapping from current labels

- `stage1` → Transform: sponsor register filtering + aggregation.
- `stage2` → Transform: Companies House enrichment.
- `stage3` → Transform (scoring) + Usage (shortlist filtering). Split required in Phase 9.

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
  - Age-based scoring continues to use `datetime.now()`; no `as_of_date` argument.

### Application

- `src/uk_sponsor_pipeline/application/download.py`
- `src/uk_sponsor_pipeline/application/stage1.py`
- `src/uk_sponsor_pipeline/application/stage2_companies_house.py`
- `src/uk_sponsor_pipeline/application/stage3_scoring.py`
  - Use‑case orchestration and core logic live here.
  - `stages/` is a thin delegate layer only.
  - Future consolidation into `application/pipeline.py` is optional if a single orchestration entry point is desired.
  - Region filtering accepts a single region only; multiple regions are rejected with a clear error.

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

- `stages/download.py` → `application/download.py`
- `stages/stage1.py` → `application/stage1.py`
- `stages/stage2_companies_house.py` → `application/stage2_companies_house.py`
- `stages/stage3_scoring.py` → `application/stage3_scoring.py`

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

- Move `normalization.py` → `domain/organisation_identity.py` (mostly a move, not a rewrite).
- Extract `_simple_similarity()` from `application/stage2_companies_house.py` → `domain/organisation_identity.py`.
- Move Stage 1 rules to `domain/sponsor_register.py`.
- Replace pipe-joined town/county handling with structured collections in core logic; flatten to strings only at IO boundaries.
- Delete the old modules immediately after migration.
- TDD: port and expand tests.
- DoD:
  - Stage 1 outputs unchanged.
  - Domain modules are pure (no infra imports).
  - `organisation_identity` contains all name-handling logic.
  - Multi-town/county handling preserves locality/region scoring intent.
- Docs updated (module docstrings + README/ADR references).
- Gates: `format → typecheck → lint → test → coverage`.
- Status: ✅ Completed.

### Phase 5 — Domain Extraction (Scoring)

- Move Stage 3 feature extraction + scoring to `domain/scoring.py`.
- Age-based scoring continues to use `datetime.now()` (no `as_of_date` input).
- Remove legacy code immediately after migration.
- TDD: ensure tests target domain functions directly.
- DoD:
  - Stage 3 outputs unchanged.
  - No infra imports in domain code.
  - Scoring remains time-dependent due to age-based scoring; this is accepted.
  - Docs updated (module docstrings + README/ADR references).
- Gates: `format → typecheck → lint → test → coverage`.
- Status: ✅ Completed.

### Phase 6 — Application Orchestration (Optional Consolidation)

- Optional: consolidate orchestration into `application/pipeline.py`.
- Remove any legacy orchestration paths immediately after migration.
- `stages/` already thin delegates; ensure they stay delegating only.
- TDD: end-to-end test with in-memory FS/HTTP still passes.
- DoD:
  - CLI is thin, orchestration centralised.
  - Resume/batching/reporting owned by application.
  - Config/env read once at the CLI entry point; stages accept config/dependencies only.
  - Docs updated (module docstrings + README/ADR references).
- Gates: `format → typecheck → lint → test → coverage`.
- Status: ⏳ Pending (optional consolidation).

### Phase 7 — Docs + ADR Audit (Now)

- Add/adjust ADRs for new boundaries + observability (only for changes completed so far).
- Update README structure section and cross-references to match current code.
- Rename test files to match new module structure:
  - `test_stage2.py` → `test_domain_companies_house.py` (or mirror: `tests/domain/test_companies_house.py`)
  - `test_infrastructure.py` → split into `test_infrastructure_http.py`, `test_infrastructure_resilience.py`, etc.
- Import-linter already configured and wired in `uv run lint`/`uv run check`.

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

  [importlinter:contract:3]
  name = Domain must not import CLI or stages
  type = forbidden
  source_modules = uk_sponsor_pipeline.domain
  forbidden_modules = uk_sponsor_pipeline.cli, uk_sponsor_pipeline.stages
  ```

- DoD:
  - Docs and ADRs match current code structure.
  - Test files renamed to match current module structure.
  - `import-linter` rules in place and passing via `uv run lint`.
  - Scaffolding characterisation tests remain until Phase 11 completes.
- Gates: `format → typecheck → lint → test → coverage`.
- Status: ⏳ Pending.

### Phase 8 — Location Profiles (Aliases) + Geographic Matching

- Create a location aliases file (e.g. `data/reference/location_aliases.json`) with canonical locations and
  their alias sets (names, regions, localities, postcode prefixes).
- Add domain-level logic to resolve a user location to a canonical profile and expand filters.
- Wire geographic filtering to use the expanded profile (this logic moves to the usage layer in Phase 10):
  - Region/locality matching uses aliases
  - Postcode matching uses defined prefixes (outward codes)
- TDD: unit tests for profile resolution and matching (no network).
- Update README and module docstrings with examples (e.g. `--region London` matches `SW1`, `Greater London`, `City of London`).
- Gates: `format → typecheck → lint → test → coverage`.
- Acceptance criteria:
  - Location aliases exist for London and Manchester in a canonical file.
  - Unit tests cover profile resolution and matching.
  - Stage 3 geographic filtering uses aliases (region/locality/postcode prefixes).
- Status: ⏳ Pending.

### Phase 8.5 — Configurable Companies House Source (API or File)

Assumption: sponsor register remains a file-based extract. Companies House source becomes configurable:
API (current) or file-based (new). File-based inputs must be fetched/cleaned similarly to the sponsor
register file (schema validation + deterministic artefact output).

- Add configuration to select Companies House source (`api` or `file`) and capture file path/URL.
- Introduce a Companies House extract protocol (application layer) with two implementations:
  - API source (current behaviour).
  - File source: fetch if remote, validate, and normalise into the same IO contracts as API outputs.
- This selection is part of the transform/enrichment boundary (not usage), and should remain invisible to domain logic.
- Update CLI/env loading to select source once at entry point and pass through config.
- Add tests:
  - API source remains unchanged.
  - File source loads, validates, and produces equivalent IO contracts.
  - Invalid source selection fails fast with a clear error.
- Update README and ADRs to document the configurable source and required inputs.
- Gates: `format → typecheck → lint → test → coverage`.
- Acceptance criteria:
  - Switching source from API to file is a config-only change.
  - File-based source produces the same typed IO shapes as API source.
  - No application/domain code branches on source type beyond the extract boundary.
- Status: ⏳ Pending.

### Phase 9 — Remove Stage Terminology (Semantic Renames)

- Rename CLI commands and help text from `stage*` to semantic ETL/usage names.
- Remove `stages/` package and adjust imports to application/usage modules directly.
- Rename output artefacts and directories to semantic equivalents (e.g. `score_scored.csv` → `scored.csv`).
- Update config flags, docs, ADRs, and tests to remove all “stage” wording.
- Provide a single, canonical naming scheme across code and documentation.
- TDD: adjust tests and snapshots to the new naming scheme.
- Gates: `format → typecheck → lint → test → coverage`.
- Acceptance criteria:
  - `rg -n "stage"` in `src/`, `tests/`, `README.md`, and `docs/` returns no matches.
  - CLI has no `stage*` commands or help text.
  - Artefact filenames and output directories are semantic (no `stage*`).
- Status: ⏳ Pending.

### Phase 10 — ETL Transform vs Usage Separation

- Split Stage 3 into explicit Transform and Usage steps:
  - Transform: score and write `companies_scored.csv` only.
  - Usage: filter by region/postcodes/location profiles and write shortlist/explain outputs.
- Introduce an application usage module (e.g. `application/usage.py`) with pure selection logic.
- Keep domain scoring pure and shared; usage must not own scoring.
- Add CLI command or subcommand to run usage independently while preserving existing flags.
- TDD: unit tests for usage filters; integration test that usage on scored artefact matches current shortlist output.
- Update README and ADRs to document the ETL vs usage split and semantic labels.
- Gates: `format → typecheck → lint → test → coverage`.
- Acceptance criteria:
  - A usage command can run without recomputing scoring.
  - Scored artefacts are produced without filters; usage filters are applied in a separate step.
  - All usage selection logic lives outside domain scoring and does not mutate transform artefacts.
- Status: ⏳ Pending.

### Phase 11 — Final Tidy Up (Docs + Scaffolding Removal)

- Remove scaffolding characterisation tests once Phases 7–10 are complete and stable.
- Re-audit ADRs and README references for semantic naming consistency (no “stage” terminology).
- Final pass on module docstrings and usage examples to ensure alignment with CLI and artefact names.
- DoD:
  - No scaffolding tests remain; permanent regression/contract tests cover the behaviour.
  - `rg -n "stage"` in `src/`, `tests/`, `README.md`, and `docs/` returns no matches.
  - Docs and ADRs are fully aligned with the final module structure and CLI names.
- Gates: `format → typecheck → lint → test → coverage`.
- Status: ⏳ Pending.

## Acceptance Criteria

- Domain modules are pure and contain no infrastructure imports.
- Infrastructure is reusable across domains.
- Observability is centralised and used by the application pipeline steps.
- Infrastructure uses boundary-neutral IO contracts (no import from `types.py`).
- All tests are network-isolated.
- Characterisation tests prove no behavioural regressions.
- Fail fast with helpful errors; resumable outputs are preserved for recovery.
- Age-based scoring uses `datetime.now()`; time-dependence is accepted.
- `resume=False` uses a fresh output directory; stale outputs are not reused.
- Region filtering accepts a single region only; errors are explicit when violated.
- Public APIs for refactored modules are comprehensively documented in code and README(s).
- British spelling is enforced in user-facing text and documentation.
- No duplicate logic or legacy code paths remain; single source of truth per module.
- All gates pass in order: `format → typecheck → lint → test → coverage`.

## Definition of Done

- Every new boundary has unit tests + protocol/contract tests.
- No `Any` in domain code; use dataclasses/TypedDicts/Protocols.
- CLI uses application orchestration only.
- ADRs updated for new boundaries and observability.
- Public APIs are documented in module docstrings and referenced in README(s).
- Scaffolding characterisation tests removed after stabilisation.
