# Implementation Plan: Validation Protocol Tooling (File-First) (2026-02-05)

Planning note: milestone sequencing and acceptance gating are tracked in
`.agent/plans/linear-delivery-plan.md`.

## Status

Draft (planning only).

## Entry Instructions (Read First)

1. `.agent/directives/AGENT.md`
1. `.agent/directives/rules.md`
1. `.agent/directives/project.md`
1. `.agent/directives/python3.practice.md`

## Scope Summary

Implement the minimal infrastructure, scripts, and commands needed to run the
validation protocol in `docs/validation-protocol.md`. This is file-first only and
includes an e2e fixture run that exercises the CLI on small, local fixtures.

## Non-Goals

- API-source validation (`CH_SOURCE_TYPE=api`).
- Any change to pipeline behaviour, scoring logic, or snapshot schemas.
- Adding new third-party dependencies for validation tooling.
- Pipeline-owned source discovery, download, and unzip (these must already exist
  in the pipeline and are validated via snapshot checks).

## Locked Decisions

- File-first only: `CH_SOURCE_TYPE=file`.
- No new third-party libraries; use standard library parsing and existing
  infrastructure protocols.
- Tests remain network-isolated; any network access is in operator-run scripts only.
- e2e fixture run is a script, not part of the unit test suite.

## Required Tooling

1. **Snapshot validation**
   - A command that validates required artefacts, manifest fields, and schema headers
     for both sponsor and Companies House snapshots.

2. **Pipeline output validation**
   - A command that validates transform outputs for required columns and presence.

3. **e2e fixture run**
   - A script that generates tiny fixtures, serves them locally, runs refresh and
     pipeline steps via the CLI, and asserts expected outputs.
   - Marked as e2e and not part of pytest.

## Proposed Commands

- `uv run python scripts/validation_check_snapshots.py --snapshot-root <path>`
- `uv run python scripts/validation_check_outputs.py --out-dir <path>`
- `uv run python scripts/validation_e2e_fixture.py`

## TDD Implementation Tasks (Ordered)

1. Add unit tests for snapshot validation rules (manifest fields, headers, artefacts).
1. Implement snapshot validation helpers in `src/uk_sponsor_pipeline/devtools/`.
1. Add unit tests for output validation rules (transform outputs, resume report).
1. Implement output validation helpers in `src/uk_sponsor_pipeline/devtools/`.
1. Implement scripts under `scripts/` that call the helpers with argparse and
   provide clear, fail-fast errors.
1. Implement the e2e fixture script using a local HTTP server and the CLI.
1. Update `docs/validation-protocol.md` to reference the new commands and expected
   outputs.

## Likely Files

- `src/uk_sponsor_pipeline/devtools/validation_snapshots.py`
- `src/uk_sponsor_pipeline/devtools/validation_outputs.py`
- `scripts/validation_check_snapshots.py`
- `scripts/validation_check_outputs.py`
- `scripts/validation_e2e_fixture.py`
- `tests/devtools/` (new test suite for validation helpers)
- `docs/validation-protocol.md`

## Definition of Done

1. All validation commands run end-to-end on file-first runs without manual steps
   beyond providing URLs to pipeline refresh commands if required.
1. Snapshot and output validation scripts fail fast on missing artefacts or schema
   mismatches.
1. e2e fixture run completes and asserts output presence and column contracts.
1. Full quality gates pass: `uv run check`.
