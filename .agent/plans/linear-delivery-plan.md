# Linear Delivery Plan (Standalone Session Entry Point)

Status: Active  
Last updated: 2026-02-06
Handoff readiness: Ready
Current batch in progress: none
Next batch to execute: `R-B5`

## Start Here (No Prior Chat Context Assumed)

1. Read repository directives in this exact order:
1. `.agent/directives/AGENT.md`
1. `.agent/directives/rules.md`
1. `.agent/directives/project.md`
1. `.agent/directives/python3.practice.md`
1. Confirm repository state:
1. `git status --short` must be empty before new implementation work.
1. Read this file completely.
1. Use this file as the only active execution plan.
1. Use `.agent/plans/deferred-features.md` for backlog only.
1. Use `.agent/plans/archive/` for historical reference only.

## Fast Resume (Next Session)

1. Run `git status --short` and confirm working tree is clean before implementation work.
1. Re-read this file fully, then go directly to:
1. `Execution Batch Protocol (Recorded Standard)`
1. `Execution Batches (Milestone 0)`
1. Start the first non-complete batch in order (currently `R-B5`).
1. Set that batch status to `In progress` before writing code.
1. Execute using TDD and complete the full batch lifecycle.
1. On batch completion:
1. Set batch status to `Complete`.
1. Record closeout in `Batch Closeout Log`.
1. Update `Status Tracking` if milestone state changed.

## Session Entry Decision Rule

When starting any new session, choose work using this deterministic rule:

1. If any batch is `In progress`, resume that batch first.
1. Otherwise, select the earliest batch in milestone order with status `Planned`.
1. Do not start a later batch while an earlier dependent batch is incomplete.
1. If blocked, set status to `Blocked`, record blocker + unblock action, then stop or resolve blocker explicitly.

## Current Baseline (Already Delivered)

1. Cache-first ingest and file-first Companies House lookup are implemented.
1. Refresh commands support grouped execution:
1. `--only discovery`
1. `--only acquire`
1. `--only clean`
1. `--only all` (default)
1. Architecture/docs state is captured in ADRs and permanent docs.

## Baseline Evidence (Recent Commits)

1. `e6a2f7f` docs(onboarding): strengthen project intent and contributor runbooks.
1. `9ef6e7e` feat(config): lock geographic filtering to single-region contract.
1. `c0a091e` feat(filesystem): protocolise streamed file handles for CH refresh.
1. `906ae95` feat(cli): enforce file-only runtime and record milestone execution plan.

## Canonical References

1. Architecture decisions:
1. `docs/architectural-decision-records/adr0019-cache-first-refresh-and-bulk-companies-house-snapshots.md`
1. `docs/architectural-decision-records/adr0021-refresh-step-groups-and-staged-acquire-clean.md`
1. `docs/architectural-decision-records/adr0022-file-only-runtime-io-boundaries-and-single-region-filtering.md`
1. Runtime mode archive:
1. `docs/archived-api-runtime-mode.md`
1. Validation/troubleshooting:
1. `docs/validation-protocol.md`
1. `docs/troubleshooting.md`
1. Legacy planning reference:
1. `.agent/plans/archive/overview-cache-first-and-file-first.md`
1. `.agent/plans/archive/ingest-source-expansion.plan.md`
1. `.agent/plans/archive/validation-protocol-implementation.plan.md`
1. `.agent/plans/archive/sector-profiles.plan.md`

## Delivery Order (Do Not Reorder)

1. Milestone 0: File-only runtime, DI IO boundaries, and onboarding hardening.
1. Milestone 1: Validation tooling implementation.
1. Milestone 2: Validation protocol operational baseline run.
1. Milestone 3: Sector-profile externalisation for scoring.
1. Milestone 4: Config-file support.
1. Milestone 5: Developer ergonomics (optional).

## Milestone 0: File-Only Runtime, DI IO Boundaries, and Onboarding Hardening

Source: `.agent/plans/file-only-di-onboarding-improvement.plan.md`

### Requirements

1. Enforce file-based Companies House operations for runtime pipeline steps (`transform-enrich`, `run-all`).
1. Route all application-layer IO through injected protocol boundaries for testability.
1. Keep geographic filtering single-region for now and align config/docs accordingly.
1. Harden onboarding docs (user docs == onboarding docs) so first-run and first-contribution workflows are accurate and executable.
1. Align CI/tooling/version metadata required for onboarding confidence.

### Acceptance Criteria

1. `run-all` and `transform-enrich` fail fast for non-file runtime source mode.
1. Application modules do not perform direct filesystem IO; IO is protocol-backed.
1. Geographic filtering contract is explicitly single-region across env/config/CLI/docs.
1. Root README and core docs are internally consistent and copy-paste safe for first-time users.
1. CI runs full quality gates on push/PR, and version metadata is surfaced consistently.
1. `uv run check` passes.

### Implementation Order (TDD)

1. Add and adjust tests for file-only runtime enforcement (`config`, `cli`, `transform_enrich`, composition wiring).
1. Implement runtime enforcement and remove obsolete API runtime branches.
1. Add tests for protocol-backed IO additions and application usage.
1. Refactor direct application filesystem operations to injected protocol calls.
1. Align single-region filtering contract in config/env/CLI/docs with tests.
1. Fix onboarding docs and examples, including programmatic usage, workflow steps, and link accuracy.
1. Add/align CI full-gate workflow and version metadata handling.
1. Run full gates: `uv run check`.

## Milestone 1: Validation Tooling Implementation

Source: `.agent/plans/archive/validation-protocol-implementation.plan.md`

### Requirements

1. Implement snapshot validation tooling for sponsor and Companies House snapshots.
1. Implement processed-output validation tooling for enrich, score, and usage outputs.
1. Implement a fixture-driven e2e validation script that exercises CLI flow on local fixtures.
1. Keep unit tests fully network-isolated.
1. Emit clear fail-fast errors for every invalid-state path.

### Acceptance Criteria

1. `uv run python scripts/validation_check_snapshots.py --snapshot-root <path>` exits `0` on valid snapshots and non-zero on invalid snapshots.
1. `uv run python scripts/validation_check_outputs.py --out-dir <path>` exits `0` on valid outputs and non-zero on invalid outputs.
1. `uv run python scripts/validation_e2e_fixture.py` runs refresh + pipeline CLI steps against fixtures and validates artefacts and required columns.
1. Unit tests cover happy paths and fail-fast paths for validation helpers.
1. `uv run check` passes.

### Implementation Order (TDD)

1. Add tests for snapshot validation helpers in `tests/devtools/`.
1. Implement snapshot validation helper module in `src/uk_sponsor_pipeline/devtools/`.
1. Add tests for output validation helpers in `tests/devtools/`.
1. Implement output validation helper module in `src/uk_sponsor_pipeline/devtools/`.
1. Add CLI scripts in `scripts/` for snapshot/output checks.
1. Implement fixture e2e script in `scripts/`.
1. Update permanent docs to include exact command usage.
1. Run full gates: `uv run check`.

## Milestone 2: Validation Protocol Operational Baseline

Source: `docs/validation-protocol.md`

### Requirements

1. Execute one full protocol run in file-first mode using grouped refresh flow.
1. Produce an auditable run record using the protocol template.
1. Align protocol and troubleshooting guidance based on real run results.

### Acceptance Criteria

1. Protocol commands work end-to-end without undocumented manual steps.
1. Run log template is complete and reproducible.
1. `docs/validation-protocol.md` and `docs/troubleshooting.md` remain consistent.
1. `uv run check` passes if code/docs changed.

## Milestone 3: Sector Profile Externalisation (Scoring)

Source: `.agent/plans/archive/sector-profiles.plan.md`

### Requirements

1. Externalise scoring signals (SIC mappings, keywords, weights, thresholds).
1. Preserve current tech profile behaviour as default.
1. Add CLI/env selection for profile path/name.
1. Validate profile schema with explicit fail-fast errors.

### Acceptance Criteria

1. Default run output remains unchanged with no profile override.
1. A custom profile changes scoring deterministically.
1. Profile selection works through CLI and env.
1. Profile schema and examples are documented.
1. `uv run check` passes.

## Milestone 4: Config-File Support

Source: `.agent/plans/deferred-features.md`

### Requirements

1. Add config-file support for key CLI and environment-backed settings.
1. Define and implement precedence: CLI > config file > env > defaults.

### Acceptance Criteria

1. A single config file can run refresh and pipeline steps with minimal CLI flags.
1. Precedence behaviour is covered by tests.
1. Documentation reflects supported config structure and precedence.
1. `uv run check` passes.

## Milestone 5: Developer Ergonomics (Optional)

Source: `.agent/plans/deferred-features.md`

### Requirements

1. Add GitHub Actions CI for quality gates.
1. Add CLI `--version` flag.

### Acceptance Criteria

1. CI runs full gate sequence on push/PR and fails on gate failure.
1. `uk-sponsor --version` returns tool version and exits `0`.
1. `uv run check` passes.

## Detailed TODO List (Next Steps)

This checklist expands the delivery milestones into concrete implementation tasks.
Follow in order. Do not reorder milestones.

### Milestone 0 TODO (File-Only + DI + Onboarding Hardening)

1. Enforce file-only runtime mode for `transform-enrich` and `run-all`; retain refresh networking only.
1. Add fail-fast validation and tests for unsupported runtime source mode.
1. Remove dead or obsolete runtime API branches once file-only runtime enforcement is in place.
1. Identify all direct filesystem IO in application modules and replace with protocol-backed operations.
1. Extend `FileSystem` protocol minimally for missing operations required by application modules.
1. Implement protocol additions in infrastructure and test fakes.
1. Add unit and contract tests for new protocol methods and refactored application paths.
1. Align geographic filtering to a single-region contract in `.env.example`, `PipelineConfig`, CLI behaviour, and docs.
1. Correct onboarding-critical docs: first-run workflow, programmatic example signatures, duplicated/contradictory command blocks, and dead plan links.
1. Add a concise developer/data-scientist onboarding path in `README.md` with copy-paste commands.
1. Add CI workflow for full quality gates on push/PR.
1. Align tool/version metadata and dependency hygiene that directly affect onboarding confidence.
1. Update ADR/docs if boundary direction or runtime behaviour changes.
1. Run `uv run check`.
1. Mark Milestone 0 status as in progress or complete in this file based on outcome.

### Milestone 1 TODO (Validation Tooling Implementation)

1. Add snapshot validation unit tests in `tests/devtools/` for valid sponsor and Companies House snapshots.
1. Add snapshot validation unit tests for fail-fast paths: missing snapshot dirs, missing artefacts, missing/invalid manifest fields, wrong schema versions, and missing required headers.
1. Add output validation unit tests in `tests/devtools/` for valid enrich/score/usage output sets.
1. Add output validation unit tests for fail-fast paths: missing processed files, missing required columns, malformed resume report, and invalid status values.
1. Implement snapshot validation helpers in `src/uk_sponsor_pipeline/devtools/validation_snapshots.py` with typed result objects and clear error messages.
1. Implement output validation helpers in `src/uk_sponsor_pipeline/devtools/validation_outputs.py` with typed result objects and clear error messages.
1. Add `scripts/validation_check_snapshots.py` to parse `--snapshot-root`, call helper validation, print concise pass/fail output, and return non-zero on failure.
1. Add `scripts/validation_check_outputs.py` to parse `--out-dir`, call helper validation, print concise pass/fail output, and return non-zero on failure.
1. Add `scripts/validation_e2e_fixture.py` to build tiny local fixtures, run grouped refresh + pipeline commands, and assert required artefacts and column contracts.
1. Keep e2e fixture execution outside pytest and ensure tests remain network-isolated.
1. Update `docs/validation-protocol.md` with exact validation command usage and expected pass/fail behaviours.
1. Update `docs/troubleshooting.md` with validation script failure modes and fixes.
1. Run `uv run check`.
1. Mark Milestone 1 status as in progress or complete in this file based on outcome.

### Milestone 2 TODO (Validation Protocol Operational Baseline)

1. Run one full file-first validation protocol using grouped refresh flow exactly as documented.
1. Capture an auditable run log using the template in `docs/validation-protocol.md`.
1. Record concrete snapshot dates, input URLs used, and output artefact locations from the run.
1. Reconcile any undocumented manual steps by updating `docs/validation-protocol.md`.
1. Add or refine corresponding recovery guidance in `docs/troubleshooting.md`.
1. Confirm protocol and troubleshooting docs are mutually consistent.
1. Run `uv run check` if code or docs changed.
1. Mark Milestone 2 status as in progress or complete in this file based on outcome.

### Milestone 3 TODO (Sector Profile Externalisation)

1. Add characterisation tests that lock current scoring behaviour as the default tech profile baseline.
1. Define a strict profile schema for SIC prefixes, keyword signals, weights, and thresholds.
1. Add profile parsing and fail-fast validation tests for missing fields, unknown keys, wrong types, and invalid ranges.
1. Implement profile model and loader module under `src/uk_sponsor_pipeline/domain/` or `src/uk_sponsor_pipeline/application/` with clear boundary ownership.
1. Externalise current hard-coded scoring signals from `src/uk_sponsor_pipeline/domain/scoring.py` into a default profile file while preserving default output.
1. Add CLI options for profile selection on `transform-score` (`--sector-profile` and `--sector`) and wire env fallbacks.
1. Extend `PipelineConfig` and config loading to carry profile path/name without re-reading env outside entry points.
1. Add deterministic tests proving a custom profile changes scoring output in expected ways.
1. Add docs for profile schema, defaults, and override examples in `README.md` and docs.
1. Run `uv run check`.
1. Mark Milestone 3 status as in progress or complete in this file based on outcome.

### Milestone 4 TODO (Config-File Support)

1. Choose config file format using standard library support and repository constraints.
1. Define config schema covering refresh and pipeline options that currently require repeated CLI/env flags.
1. Add parser tests for valid configs and fail-fast paths (missing file, invalid schema, invalid values).
1. Implement precedence logic with tests: CLI > config file > env > defaults.
1. Add CLI option to pass config file path and integrate it at the entry point only.
1. Ensure resolved config is passed through existing `PipelineConfig` without global lookups.
1. Document supported config structure, precedence examples, and migration guidance in `README.md`.
1. Run `uv run check`.
1. Mark Milestone 4 status as in progress or complete in this file based on outcome.

### Milestone 5 TODO (Optional Developer Ergonomics)

1. Add CI workflow file `.github/workflows/ci.yml` running full gates on push and pull request.
1. Ensure CI uses `uv` and fails on the first quality gate failure.
1. Add CLI `--version` flag with tests to return package version and exit `0`.
1. Wire version source from `uk_sponsor_pipeline.__version__` or explicit fallback.
1. Update docs for CI behaviour and version command usage.
1. Run `uv run check`.
1. Mark Milestone 5 status as in progress or complete in this file based on outcome.

### Session-Level Execution Checklist

1. Before coding: confirm `git status --short` is clean and re-read this plan file.
1. During coding: follow strict TDD (tests first, implementation second, refactor third).
1. After each milestone chunk: update docs and this plan status before moving to the next chunk.
1. Before commit: run `uv run check` and fix all failures at root cause.
1. After commit: ensure `git status --short` is empty.

## Execution Batch Protocol (Recorded Standard)

Use this protocol for every future execution batch in this plan.

### Batch Definition

1. One batch is one mergeable, test-green increment with a single primary objective.
1. A batch may touch multiple files, but all changes must serve the same objective.
1. Every batch must preserve TDD, strict typing, fail-fast behaviour, and network-isolated tests.

### Batch Lifecycle (Mandatory)

1. Define batch record using the template below before coding.
1. Confirm dependency readiness (upstream batches complete, required fixtures/docs available).
1. Implement with TDD (write/adjust tests first, then implementation, then refactor).
1. Update relevant docs/ADRs in the same batch when behaviour or architecture changes.
1. Run `uv run check`.
1. Record closeout notes and update statuses in this plan file.

### Batch Record Template

Use this structure for each new batch:

```text
Batch ID:
Milestone:
Objective:
Status: Planned | In progress | Blocked | Complete
Depends on:
Scope (in):
Scope (out):
Primary files:
TDD tasks:
Implementation tasks:
Docs/tasks updates:
Verification commands:
Exit criteria:
Notes:
```

### Status Rules

1. Allowed statuses: `Planned`, `In progress`, `Blocked`, `Complete`.
1. Only one batch may be `In progress` at a time.
1. If blocked, add a concrete blocker note and the next unblock action.
1. On completion, record what shipped and any follow-up tasks moved to the next batch.

## Execution Batches (Milestone 0)

The following batches are the approved execution slices for Milestone 0.

### Batch R-B1

1. Batch ID: `R-B1`
1. Objective: Enforce file-only runtime source mode for `transform-enrich` and `run-all`.
1. Status: `Complete`
1. Depends on: none
1. Scope (in): config/CLI/runtime enforcement and fail-fast errors for unsupported runtime modes.
1. Scope (out): IO boundary refactor, docs hardening, CI/version hygiene.
1. Primary files:
1. `src/uk_sponsor_pipeline/config.py`
1. `src/uk_sponsor_pipeline/cli.py`
1. `src/uk_sponsor_pipeline/application/transform_enrich.py`
1. `src/uk_sponsor_pipeline/application/companies_house_source.py`
1. `tests/application/test_transform_enrich.py`
1. `tests/cli/test_cli.py`
1. Exit criteria:
1. Runtime operations are file-only and deterministic.
1. Unsupported mode fails fast with clear error messaging.

### Batch R-B2

1. Batch ID: `R-B2`
1. Objective: Refactor application filesystem usage to protocol-backed DI boundaries.
1. Status: `Complete`
1. Depends on: `R-B1`
1. Scope (in): protocol additions, infrastructure/fake support, application refactor.
1. Scope (out): geographic contract and docs/CI hardening.
1. Primary files:
1. `src/uk_sponsor_pipeline/protocols.py`
1. `src/uk_sponsor_pipeline/infrastructure/io/filesystem.py`
1. `tests/fakes/filesystem.py`
1. `src/uk_sponsor_pipeline/application/refresh_companies_house.py`
1. `tests/infrastructure/test_filesystem.py`
1. `tests/application/test_refresh_companies_house.py`
1. Exit criteria:
1. Application modules avoid direct filesystem operations.
1. Protocol behaviour is covered by tests with simple fakes.

### Batch R-B3

1. Batch ID: `R-B3`
1. Objective: Align and lock single-region geographic filtering contract.
1. Status: `Complete`
1. Depends on: `R-B2`
1. Scope (in): env/config/CLI/docs consistency for single-region behaviour.
1. Scope (out): broader docs and CI/version hygiene.
1. Primary files:
1. `.env.example`
1. `src/uk_sponsor_pipeline/config.py`
1. `src/uk_sponsor_pipeline/cli.py`
1. `tests/config/test_config.py`
1. `tests/cli/test_cli.py`
1. Exit criteria:
1. Single-region contract is explicit and consistent.
1. Tests and docs reflect the same behaviour.

### Batch R-B4

1. Batch ID: `R-B4`
1. Objective: Harden onboarding and user docs for first-run accuracy.
1. Status: `Complete`
1. Depends on: `R-B3`
1. Scope (in): README + core docs correctness, copy-paste safety, workflow clarity.
1. Scope (out): CI/version/dependency hygiene.
1. Primary files:
1. `README.md`
1. `docs/snapshots.md`
1. `docs/validation-protocol.md`
1. `docs/troubleshooting.md`
1. Exit criteria:
1. Onboarding workflow is explicit and contradiction-free.
1. Programmatic examples match actual API signatures.

### Batch R-B5

1. Batch ID: `R-B5`
1. Objective: Add CI full-gate workflow and align version/tooling metadata.
1. Status: `Planned`
1. Depends on: `R-B4`
1. Scope (in): CI workflow, version source consistency, dependency hygiene.
1. Scope (out): Milestone 1 validation tooling work.
1. Primary files:
1. `.github/workflows/` (new/updated)
1. `pyproject.toml`
1. `src/uk_sponsor_pipeline/__init__.py`
1. `src/uk_sponsor_pipeline/application/snapshots.py`
1. `README.md`
1. Exit criteria:
1. CI runs full quality gates on push/PR.
1. Version metadata and onboarding guidance are aligned.

### Batch R-B6

1. Batch ID: `R-B6`
1. Objective: Milestone 0 closeout and reconciliation.
1. Status: `Planned`
1. Depends on: `R-B5`
1. Scope (in): docs/ADR reconciliation, final gate run, milestone status updates.
1. Scope (out): Milestone 1 implementation.
1. Primary files:
1. `.agent/plans/linear-delivery-plan.md`
1. `README.md`
1. `docs/architectural-decision-records/` (if required)
1. Exit criteria:
1. Milestone 0 acceptance criteria are met and documented.
1. `uv run check` passes.
1. Milestone 0 status updated to `Complete`.

## Execution Batches (Milestone 1)

The following batches are the approved execution slices for Milestone 1.

### Batch M1-B1

1. Batch ID: `M1-B1`
1. Objective: Implement snapshot validation helper module with full unit coverage.
1. Status: `Planned`
1. Depends on: none
1. Scope (in): snapshot artefact checks, manifest required fields, schema/header checks, fail-fast errors.
1. Scope (out): output validation, CLI scripts, fixture e2e runner.
1. Primary files:
1. `tests/devtools/` (new snapshot validation tests)
1. `src/uk_sponsor_pipeline/devtools/validation_snapshots.py` (new)
1. Exit criteria:
1. Snapshot helper tests pass.
1. Helper fails fast on all invalid-state paths in milestone requirements.

### Batch M1-B2

1. Batch ID: `M1-B2`
1. Objective: Implement processed-output validation helper module with full unit coverage.
1. Status: `Planned`
1. Depends on: `M1-B1`
1. Scope (in): enrich/score/usage artefact presence, required column checks, resume report validation.
1. Scope (out): CLI scripts, fixture e2e runner.
1. Primary files:
1. `tests/devtools/` (new output validation tests)
1. `src/uk_sponsor_pipeline/devtools/validation_outputs.py` (new)
1. Exit criteria:
1. Output helper tests pass.
1. Helper returns clear non-ambiguous fail-fast errors for invalid outputs.

### Batch M1-B3

1. Batch ID: `M1-B3`
1. Objective: Add CLI validation scripts for snapshots and processed outputs.
1. Status: `Planned`
1. Depends on: `M1-B1`, `M1-B2`
1. Scope (in): argparse wiring, helper integration, exit-code contract (`0` valid, non-zero invalid).
1. Scope (out): fixture e2e runner.
1. Primary files:
1. `scripts/validation_check_snapshots.py` (new)
1. `scripts/validation_check_outputs.py` (new)
1. `tests/devtools/` or `tests/scripts/` (script behaviour tests as needed)
1. Exit criteria:
1. Both commands satisfy acceptance criteria for valid/invalid inputs.
1. Command usage/output is concise and deterministic.

### Batch M1-B4

1. Batch ID: `M1-B4`
1. Objective: Implement fixture-driven e2e validation script and supporting fixtures.
1. Status: `Planned`
1. Depends on: `M1-B3`
1. Scope (in): local fixture setup, grouped refresh execution, pipeline execution, artefact and column assertions.
1. Scope (out): operational baseline run documentation updates beyond Milestone 1 command docs.
1. Primary files:
1. `scripts/validation_e2e_fixture.py` (new)
1. `tests/` support files only if required for deterministic script behaviour
1. Exit criteria:
1. Script runs end-to-end locally and validates required outputs.
1. Script remains outside pytest suite and keeps unit tests network-isolated.

### Batch M1-B5

1. Batch ID: `M1-B5`
1. Objective: Finalise docs and milestone closeout gates.
1. Status: `Planned`
1. Depends on: `M1-B4`
1. Scope (in): docs updates for validation commands and troubleshooting, milestone status update, final quality gates.
1. Scope (out): Milestone 2 operational run execution.
1. Primary files:
1. `docs/validation-protocol.md`
1. `docs/troubleshooting.md`
1. `.agent/plans/linear-delivery-plan.md` (status updates)
1. Exit criteria:
1. Documentation matches implemented tooling exactly.
1. `uv run check` passes.
1. Milestone 1 status updated from `Not started` to `Complete` when done.

## Batch Status Board

Use this as the canonical live tracker for batch execution state.

### Milestone 0

1. `R-B1`: Complete
1. `R-B2`: Complete
1. `R-B3`: Complete
1. `R-B4`: Complete
1. `R-B5`: Planned
1. `R-B6`: Planned

### Milestone 1

1. `M1-B1`: Planned
1. `M1-B2`: Planned
1. `M1-B3`: Planned
1. `M1-B4`: Planned
1. `M1-B5`: Planned

### Milestone 2

1. `M2-B1`: Planned
1. `M2-B2`: Planned
1. `M2-B3`: Planned

### Milestone 3

1. `M3-B1`: Planned
1. `M3-B2`: Planned
1. `M3-B3`: Planned
1. `M3-B4`: Planned
1. `M3-B5`: Planned

### Milestone 4

1. `M4-B1`: Planned
1. `M4-B2`: Planned
1. `M4-B3`: Planned
1. `M4-B4`: Planned

### Milestone 5

1. `M5-B1`: Planned
1. `M5-B2`: Planned
1. `M5-B3`: Planned

## Future Batch Index (Milestones 2-5)

Use the recorded protocol to define and execute these batches when Milestone 1 is complete.

1. `M2-B1`: Run full file-first validation protocol and capture run log.
1. `M2-B2`: Align protocol/troubleshooting docs from real run findings.
1. `M2-B3`: Milestone 2 closeout (`uv run check`, status updates).
1. `M3-B1`: Characterisation tests for current scoring behaviour baseline.
1. `M3-B2`: Profile schema + loader + validation tests.
1. `M3-B3`: CLI/env profile selection wiring.
1. `M3-B4`: Custom profile deterministic output tests + docs.
1. `M3-B5`: Milestone 3 closeout.
1. `M4-B1`: Config-file schema/parser and fail-fast tests.
1. `M4-B2`: Precedence implementation (CLI > config > env > defaults) + tests.
1. `M4-B3`: CLI entry-point integration + docs.
1. `M4-B4`: Milestone 4 closeout.
1. `M5-B1`: GitHub Actions CI quality gate workflow.
1. `M5-B2`: CLI `--version` implementation + tests.
1. `M5-B3`: Milestone 5 closeout.

## Batch Closeout Log

Record each completed or blocked batch here for session-to-session continuity.

```text
Date:
Batch ID:
Status:
Summary:
Quality gates:
Docs updated:
Follow-ups:
```

```text
Date: 2026-02-06
Batch ID: R-B1
Status: Complete
Summary: Enforced file-only runtime mode for `transform-enrich` and `run-all` with fail-fast CLI errors for unsupported source mode.
Quality gates: uv run check (pass)
Docs updated: README.md, docs/troubleshooting.md, docs/archived-api-runtime-mode.md, .env.example
Follow-ups: Execute R-B2 (protocol-backed filesystem refactor for application refresh paths).
```

```text
Date: 2026-02-06
Batch ID: R-B2
Status: Complete
Summary: Added streamed file-handle methods to `FileSystem`, implemented them in local and in-memory filesystem implementations, and refactored Companies House refresh application flow to use protocol-backed opens.
Quality gates: uv run check (pass)
Docs updated: .agent/plans/linear-delivery-plan.md
Follow-ups: Execute R-B3 (single-region geographic filtering contract alignment).
```

```text
Date: 2026-02-06
Batch ID: R-B3
Status: Complete
Summary: Standardised geographic filtering on a single-region contract by replacing GEO_FILTER_REGIONS with GEO_FILTER_REGION, enforcing fail-fast parsing for comma-separated values, and extending CLI/config coverage.
Quality gates: uv run check (pass)
Docs updated: README.md, .env.example, .agent/plans/linear-delivery-plan.md
Follow-ups: Execute R-B4 (onboarding and user-doc hardening).
```

```text
Date: 2026-02-06
Batch ID: R-B4
Status: Complete
Summary: Reworked onboarding and operational documentation to emphasise project intent, first-run success, contributor workflow, and auditable validation and recovery runbooks.
Quality gates: uv run check (pass)
Docs updated: README.md, docs/snapshots.md, docs/validation-protocol.md, docs/troubleshooting.md, .agent/plans/linear-delivery-plan.md
Follow-ups: Execute R-B5 (CI full-gate workflow and version/tooling alignment).
```

## Session Completion Rules (Every Session)

1. Keep this file updated with progress state.
1. Update permanent docs and ADRs when behaviour/architecture changes.
1. Run full gates before commit: `uv run check`.
1. Commit with conventional commit message.
1. Leave working tree clean (`git status --short` empty).

## Status Tracking

1. Milestone 0: In progress.
1. Milestone 1: Not started.
1. Milestone 2: Not started.
1. Milestone 3: Not started.
1. Milestone 4: Not started.
1. Milestone 5: Not started.
