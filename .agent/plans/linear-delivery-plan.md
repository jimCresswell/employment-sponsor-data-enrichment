# Linear Delivery Plan (Single Source of Truth)

Status: Active (2026-02-06)

## Purpose

Provide one clear, ordered delivery path across the existing plan documents, with explicit
requirements and acceptance criteria for each milestone.

## Inputs Reviewed

1. `.agent/plans/archive/overview-cache-first-and-file-first.md`
1. `.agent/plans/archive/ingest-source-expansion.plan.md`
1. `.agent/plans/archive/validation-protocol-implementation.plan.md`
1. `.agent/plans/archive/sector-profiles.plan.md`
1. `.agent/plans/deferred-features.md`

## Current State

1. Cache-first ingest and file-first Companies House pipeline: complete.
1. Grouped refresh execution (`discovery`, `acquire`, `clean`, `all`): complete.
1. Validation protocol exists, but validation tooling scripts are not yet implemented.
1. Sector profiles for scoring are planned, not implemented.
1. Config-file support and CI are deferred.

## Linear Path Forward

## Milestone 1: Validation Tooling Implementation

Source: `.agent/plans/archive/validation-protocol-implementation.plan.md`

### Requirements

1. Implement snapshot validation tooling for sponsor and Companies House snapshot artefacts.
1. Implement processed-output validation tooling for enrich, score, and usage outputs.
1. Implement a fixture-driven e2e validation script that runs the CLI on tiny local fixtures.
1. Keep tooling file-first and network-isolated in tests.
1. Add clear fail-fast errors for all validation failures.

### Acceptance Criteria

1. `uv run python scripts/validation_check_snapshots.py --snapshot-root <path>` exits `0`
   on valid snapshots and non-zero with clear errors on invalid snapshots.
1. `uv run python scripts/validation_check_outputs.py --out-dir <path>` exits `0`
   on valid outputs and non-zero with clear errors on invalid outputs.
1. `uv run python scripts/validation_e2e_fixture.py` runs refresh + pipeline CLI steps
   against fixtures and asserts required artefacts and column contracts.
1. Unit tests cover validation helpers and failure paths.
1. `uv run check` passes.

## Milestone 2: Validation Protocol Operational Baseline

Source: `docs/validation-protocol.md`

### Requirements

1. Run the full protocol once in file-first mode using the grouped refresh flow.
1. Record a reproducible run log template and expected artefact locations.
1. Align troubleshooting guidance with common protocol failures.

### Acceptance Criteria

1. Protocol can be executed end-to-end using documented commands only.
1. Run log template is complete and reflects grouped refresh semantics.
1. `docs/validation-protocol.md` and `docs/troubleshooting.md` are consistent.

## Milestone 3: Sector Profile Externalisation (Scoring)

Source: `.agent/plans/archive/sector-profiles.plan.md`

### Requirements

1. Externalise scoring profile signals (SIC mappings, keywords, weights, thresholds).
1. Preserve current tech scoring as the default profile.
1. Add CLI and env selection for profile name/path.
1. Validate profile schema with fail-fast errors.

### Acceptance Criteria

1. No-profile runs produce identical scoring outputs to current baseline.
1. A custom profile can change scoring outputs deterministically.
1. CLI/env profile selection works as documented.
1. Profile schema and examples are documented.
1. `uv run check` passes.

## Milestone 4: Config-File Support

Source: `deferred-features.md`

### Requirements

1. Add config-file support for CLI arguments and key environment-backed settings.
1. Preserve current precedence rules clearly (CLI > config file > env > defaults).

### Acceptance Criteria

1. A single config file can run refresh and pipeline steps without large CLI argument sets.
1. Precedence rules are tested and documented.
1. `uv run check` passes.

## Milestone 5: Developer Ergonomics (Optional)

Source: `deferred-features.md`

### Requirements

1. Add CI workflow for quality gates.
1. Add CLI `--version` flag.

### Acceptance Criteria

1. CI runs full checks on push/PR and enforces gate failures.
1. `uk-sponsor --version` returns tool version and exits `0`.

## Sequencing Rules

1. Execute milestones in order; do not start Milestone 3 before Milestone 1 is complete.
1. Each milestone must end with:
   - Updated permanent docs
   - Updated/added ADR if architecture or cross-cutting behaviour changed
   - Passing `uv run check`
1. No archived plans should be reactivated without explicit status change in this file.

## Notes

1. Existing ingest plans remain as historical implementation detail in `.agent/plans/archive/`.
1. This file is the planning entry point for active work.
