> Archived Plan Notice (2026-02-11): this file is historical reference only.
> Do not execute this plan directly.
> Active execution queue: `.agent/plans/linear-delivery-plan.md`.
> Durable contracts and operational guidance live in `README.md`, `docs/`, and `docs/architectural-decision-records/`.

# Plan: File-Only Runtime, DI IO Boundaries, and Onboarding Hardening

Status: Promoted (mapped to Milestone 0 in `.agent/plans/linear-delivery-plan.md`)
Owner: Jim + Codex
Last updated: 2026-02-06

## Purpose

Apply a focused architecture simplification pass to improve reliability and onboarding:

1. Enforce file-based Companies House operations for runtime pipeline steps.
2. Ensure all IO flows through injected protocol boundaries for testability.
3. Keep geographic filtering single-region for now.
4. Improve user/developer onboarding docs so first-run and first-contribution paths are explicit and accurate.

## Decisions Captured

1. Runtime Companies House source should be file-based only for now.
2. All IO should be performed via DI-backed protocols.
3. Geographic filtering should support a single region at this stage.
4. Architecture should prefer the simplest maintainable shape with clean boundaries and fail-fast behaviour.

## Architectural Recommendation

The best architectural direction now is a strict file-first runtime with a narrow boundary surface:

1. One runtime source mode for enrich/run-all: file snapshots only.
2. One place for network access: refresh commands (link discovery and snapshot acquisition).
3. One IO contract path: application code depends on protocols only; infrastructure owns concrete filesystem/network operations.
4. One geographic contract: single region + optional postcode prefixes.
5. One onboarding path: a short default workflow that is copy-paste correct and mirrors real behaviour.

This removes low-value branching and makes behaviour easier to reason about for both developers and data scientists.

## Scope

### In Scope

1. File-only enforcement for enrich and run-all code paths.
2. Protocol-first IO refactor where direct path/file operations exist in application modules.
3. Geographic filtering contract simplification and docs alignment.
4. Onboarding and user docs corrections, including broken examples and contradictory guidance.
5. Tooling hygiene directly affecting onboarding confidence (CI, version consistency, dependency hygiene).

### Out of Scope

1. Re-introducing API mode in this phase.
2. New product features not tied to architecture simplification or onboarding.
3. Dashboard/UI work.

## Workstreams and Milestones

## Milestone A: Enforce File-Only Runtime Source

### Objective

Remove runtime ambiguity by enforcing file-only Companies House source for transform-enrich and run-all.

### Implementation Tasks

1. Remove API selection branches from runtime orchestration where not required.
2. Replace `CH_SOURCE_TYPE` runtime branching with explicit file-source behaviour for enrich/run-all.
3. Update configuration and CLI validation to fail fast on unsupported source types.
4. Keep refresh command networking intact (this remains valid pipeline-owned acquisition).
5. Remove or quarantine obsolete API-runtime wiring code paths that become dead.

### Primary Files

1. `src/uk_sponsor_pipeline/config.py`
2. `src/uk_sponsor_pipeline/cli.py`
3. `src/uk_sponsor_pipeline/composition.py`
4. `src/uk_sponsor_pipeline/application/transform_enrich.py`
5. `src/uk_sponsor_pipeline/application/companies_house_source.py`
6. `tests/application/test_transform_enrich.py`
7. `tests/cli/test_cli.py`
8. `tests/composition/test_composition.py`

### Acceptance Criteria

1. `run-all` and `transform-enrich` cannot run in API mode.
2. Runtime path is deterministic and file-based.
3. Existing file-source behaviour remains correct.
4. `uv run check` passes.

## Milestone B: Complete IO Boundary Through DI

### Objective

Remove direct application-layer filesystem calls and route all IO via `FileSystem`/protocol interfaces.

### Implementation Tasks

1. Identify direct file operations in application modules (especially Companies House refresh/clean paths).
2. Extend protocol surface minimally where needed for streamed CSV and ZIP handling.
3. Implement protocol additions in `LocalFileSystem` and test fakes.
4. Refactor application modules to use injected protocol methods only.
5. Add contract-style tests proving protocol behaviour for new methods.

### Primary Files

1. `src/uk_sponsor_pipeline/protocols.py`
2. `src/uk_sponsor_pipeline/infrastructure/io/filesystem.py`
3. `tests/fakes/filesystem.py`
4. `src/uk_sponsor_pipeline/application/refresh_companies_house.py`
5. `tests/infrastructure/test_filesystem.py`
6. `tests/application/test_refresh_companies_house.py`

### Acceptance Criteria

1. Application modules do not perform direct filesystem IO.
2. IO-heavy behaviour remains covered by network-isolated tests with simple fakes.
3. `uv run check` passes.

## Milestone C: Single-Region Geographic Contract

### Objective

Make single-region semantics explicit and consistent across env vars, config parsing, CLI, and docs.

### Implementation Tasks

1. Standardise on a single-region config contract.
2. Rename configuration variables if needed for clarity (clean break allowed).
3. Update parsing/validation and tests.
4. Update docs/examples to remove multi-region suggestions.

### Primary Files

1. `src/uk_sponsor_pipeline/config.py`
2. `.env.example`
3. `README.md`
4. `docs/validation-protocol.md` (if references exist)
5. `tests/config/test_config.py`
6. `tests/cli/test_cli.py`

### Acceptance Criteria

1. Region filtering behaviour is unambiguous and documented as single-region.
2. Docs and runtime behaviour are consistent.
3. `uv run check` passes.

## Milestone D: Onboarding and User Docs Hardening

### Objective

Treat user docs as onboarding docs; ensure first run and first contribution workflows are accurate, minimal, and copy-paste safe.

### Implementation Tasks

1. Fix broken programmatic examples and incorrect signatures.
2. Remove duplicated or contradictory command blocks.
3. Add a short "First 15 Minutes" path for developers and data scientists.
4. Ensure docs reflect real cache-only and file-only behaviour.
5. Fix dead links and clarify active-plan references.
6. Add a concise troubleshooting decision tree for common first-run failures.

### Primary Files

1. `README.md`
2. `docs/snapshots.md`
3. `docs/validation-protocol.md`
4. `docs/troubleshooting.md`
5. `docs/architectural-decision-records/README.md` (if index updates are needed)

### Acceptance Criteria

1. New developers can run end-to-end from docs without hidden steps.
2. Programmatic examples are executable and type-correct.
3. No contradictions between README and operational docs.
4. `uv run check` passes.

## Milestone E: Tooling and Metadata Hygiene for Onboarding Confidence

### Objective

Align tooling/metadata so local and CI experiences match and artefact metadata is meaningful.

### Implementation Tasks

1. Add CI workflow for full quality gates.
2. Align Python/version declarations across tooling where inconsistent.
3. Remove unused dependencies that add install burden without value.
4. Define and expose package version source used by manifests and CLI.
5. Update docs to describe CI and version behaviour.

### Primary Files

1. `.github/workflows/` (new/updated workflow files)
2. `pyproject.toml`
3. `src/uk_sponsor_pipeline/__init__.py`
4. `src/uk_sponsor_pipeline/application/snapshots.py`
5. `README.md`

### Acceptance Criteria

1. CI runs full gate sequence on push/PR.
2. Version metadata is consistent and visible.
3. Dependency list is lean and justified.
4. `uv run check` passes.

## Execution Batches (Recommended)

Execute as small, mergeable increments:

1. `R-B1`: File-only runtime enforcement.
2. `R-B2`: DI IO boundary refactor (protocol + infra + app).
3. `R-B3`: Geographic contract simplification.
4. `R-B4`: README/docs onboarding hardening.
5. `R-B5`: CI/tooling/version hygiene.
6. `R-B6`: Final reconciliation pass (docs + ADR updates + closeout).

## TDD and Verification Protocol

For every batch:

1. Write/adjust failing tests first.
2. Implement minimal code to pass tests.
3. Refactor while keeping tests green.
4. Update docs in the same batch when behaviour changes.
5. Run `uv run check` before closeout.

## Risks and Mitigations

1. Risk: file-only cut removes workflows some users still rely on.
   Mitigation: clean fail-fast errors and explicit migration notes in README.
2. Risk: protocol expansion for IO could overcomplicate interfaces.
   Mitigation: add only methods required by current application needs.
3. Risk: docs drift during refactor.
   Mitigation: documentation update is an explicit batch exit criterion.

## Done Definition

This plan is complete when:

1. Runtime path is file-only for enrich/run-all.
2. Application IO is protocol-driven and testable with fakes.
3. Geographic filtering contract is single-region and consistent.
4. Onboarding docs are accurate, concise, and executable.
5. CI/tooling/metadata are aligned and `uv run check` is green.

## Promotion Rule

This plan is an improvement proposal until promoted. Before implementation begins, map accepted items into `.agent/plans/linear-delivery-plan.md` batches and status tracking.
