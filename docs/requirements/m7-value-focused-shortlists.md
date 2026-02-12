# Requirements: M7 Value-Focused Shortlists

Date: 2026-02-12  
Owner: Milestone 7 (`M7-B1` to `M7-B5`)

## Scope

Define requirements needed to satisfy the value stories for:

1. tech-job targeting by area,
1. tech-job targeting at large employers (`>= 1000` employees),
1. profile-based workflow reuse,
1. deterministic, auditable operation.

## Functional Requirements

1. `FR-1` (US-1): Keep the current location-targeting contract explicit.
1. Supported controls remain: profile selection, threshold, one region, postcode prefixes.
1. Multi-region inputs remain fail-fast by contract.
1. `FR-2` (US-2): Add a deterministic large-employer filter contract.
1. Define `min_employee_count` semantics with integer comparison (`>=`).
1. Baseline large-employer targeting for this story is `min_employee_count = 1000`.
1. `FR-3` (US-2): Introduce a durable employee-count data signal keyed by company number.
1. The signal must be snapshot-backed and versioned like other pipeline inputs.
1. The signal must include provenance fields (source, snapshot date) for audit output.
1. `FR-4` (US-2): Define unknown-size behaviour explicitly.
1. Unknown employee-count rows must not be silently mixed with known-size rows.
1. CLI/config must make unknown handling explicit (for example include or exclude unknown).
1. `FR-5` (US-3): Preserve profile-selection behaviour and deterministic scoring outcomes.
1. Existing default profile behaviour must remain unchanged unless explicitly overridden.
1. `FR-6` (US-4): Preserve deterministic artefact behaviour and validation evidence capture.
1. Existing deterministic rerun and validation contracts remain mandatory.

## Non-Functional Requirements

1. Keep runtime file-only for Companies House mode and existing dependency direction unchanged.
1. Maintain strict fail-fast error paths for invalid config/filter values.
1. Keep tests network-isolated and fully typed.
1. Keep documentation and contracts synchronised with implementation.
1. Run full quality gates (`uv run check`) on each completed batch.

## Verification Requirements

1. Add/adjust tests for size-filter parsing and fail-fast invalid values.
1. Add/adjust tests proving deterministic shortlist filtering with known and unknown employee counts.
1. Add/adjust tests for snapshot/manifest validation of the new employee-count input artefacts.
1. Extend validation scripts/contracts as needed to cover new required columns.
1. Record one validation run evidence entry after implementation batches complete.

## Current Contract Gaps (2026-02-12)

1. Scored/shortlist contracts now include employee-count and provenance fields, but
   shortlist filtering logic has not yet consumed them.
1. Current usage filtering supports threshold + single-region/postcode filtering only.
1. Scoring profile schema contains `size_signals`, but runtime scoring currently does not consume them.

## Directives-Aligned Delivery Approach

1. Batch-first, contract-first sequence:
1. `M7-B2`: add config/CLI/schema contracts and fail-fast validation for employee-count filters.
1. `M7-B3`: add a snapshot-backed company-size input boundary and deterministic join by company number.
1. `M7-B4`: apply size filtering in `usage-shortlist` and expose explainability columns.
1. `M7-B5`: close out docs, validation evidence, and milestone status.
1. Introduce a new ADR only when a new cross-cutting boundary is finalised (for example, external size-data source strategy).
1. Keep behavioural scope minimal in each batch; no speculative cross-feature expansion.

## Traceability

- User stories: `docs/user-stories/us-m7-value-focused-shortlists.md`
- Existing runtime contracts: `docs/data-contracts.md`
- Active execution queue: `.agent/plans/linear-delivery-plan.md`
