# Linear Delivery Plan (Standalone Session Entry Point)

Status: Active  
Last updated: 2026-02-06

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

## Current Baseline (Already Delivered)

1. Cache-first ingest and file-first Companies House lookup are implemented.
1. Refresh commands support grouped execution:
1. `--only discovery`
1. `--only acquire`
1. `--only clean`
1. `--only all` (default)
1. Architecture/docs state is captured in ADRs and permanent docs.

## Baseline Evidence (Recent Commits)

1. `b1c2cd4` docs: consolidate active planning into linear roadmap.
1. `5f08e4f` feat: add staged refresh acquire and clean groups.
1. `946d2a7` feat: add refresh link discovery and validation protocol.

## Canonical References

1. Architecture decisions:
1. `docs/architectural-decision-records/adr0019-cache-first-refresh-and-bulk-companies-house-snapshots.md`
1. `docs/architectural-decision-records/adr0021-refresh-step-groups-and-staged-acquire-clean.md`
1. Validation/troubleshooting:
1. `docs/validation-protocol.md`
1. `docs/troubleshooting.md`
1. Legacy planning reference:
1. `.agent/plans/archive/overview-cache-first-and-file-first.md`
1. `.agent/plans/archive/ingest-source-expansion.plan.md`
1. `.agent/plans/archive/validation-protocol-implementation.plan.md`
1. `.agent/plans/archive/sector-profiles.plan.md`

## Delivery Order (Do Not Reorder)

1. Milestone 1: Validation tooling implementation.
1. Milestone 2: Validation protocol operational baseline run.
1. Milestone 3: Sector-profile externalisation for scoring.
1. Milestone 4: Config-file support.
1. Milestone 5: Developer ergonomics (optional).

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

## Session Completion Rules (Every Session)

1. Keep this file updated with progress state.
1. Update permanent docs and ADRs when behaviour/architecture changes.
1. Run full gates before commit: `uv run check`.
1. Commit with conventional commit message.
1. Leave working tree clean (`git status --short` empty).

## Status Tracking

1. Milestone 1: Not started.
1. Milestone 2: Not started.
1. Milestone 3: Not started.
1. Milestone 4: Not started.
1. Milestone 5: Not started.
