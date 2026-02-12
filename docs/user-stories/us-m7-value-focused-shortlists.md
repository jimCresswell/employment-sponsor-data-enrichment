# User Stories: Value-Focused Shortlists (Milestone 7)

Date: 2026-02-12  
Status: Active

## Scope

This set defines a minimal, sensible portfolio of user stories for evaluating whether the
pipeline is delivering practical value beyond pure runtime correctness.

## Story US-1: Tech Jobs in My Area

As a user who wants tech jobs in my area,  
I want to filter shortlist results to a tech profile and my target location,  
so that I can target job searches quickly.

### Acceptance Criteria

1. A run with the tech profile and a single region filter produces shortlist and explain outputs.
1. Geographic filtering remains fail-fast for invalid multi-region inputs.
1. Explain output remains usable for prioritisation (`role_fit_score`, `role_fit_bucket`, company fields).

## Story US-2: Tech Jobs at Large Employers

As a user who prioritises larger employers likely to have recurring tech vacancies,  
I want to filter to organisations with at least 1,000 employees,  
so that I can focus outreach on higher-capacity hiring targets.

### Acceptance Criteria

1. Large-employer targeting is explicit and deterministic (`min_employee_count >= 1000`).
1. Unknown employee-count rows are handled explicitly (either excluded by default or controlled by a flag).
1. Explain output includes size evidence and source provenance for auditability.

## Story US-3: Reusable Workflow Across Job Types

As a user evaluating multiple job families,  
I want to switch scoring profile without changing the rest of the workflow,  
so that I can compare opportunities across profiles using one repeatable process.

### Acceptance Criteria

1. Profile selection remains available via CLI and environment (`--sector`, `SECTOR_NAME`).
1. Default behaviour remains stable when no profile override is supplied.
1. Output contracts remain deterministic for identical inputs and profile choice.

## Story US-4: Trustworthy and Repeatable Results

As a contributor reviewing output quality,  
I want deterministic reruns and explicit validation evidence,  
so that I can trust changes and detect regressions early.

### Acceptance Criteria

1. Fixture-based deterministic rerun checks continue to pass.
1. Validation evidence cadence and run-log location remain explicit.
1. Fail-fast validation tooling remains part of normal verification flow.

## Coverage Snapshot (2026-02-12)

1. `US-1`: Delivered (profile + single-region/postcode filtering and explain output remain available).
1. `US-2`: Delivered (employee-count signal is joined, shortlist filtering is explicit, and explain output includes provenance).
1. `US-3`: Delivered (profile switching implemented with deterministic behaviour).
1. `US-4`: Delivered (validation protocol and deterministic e2e checks in place).

## Traceability

- Requirements: `docs/requirements/m7-value-focused-shortlists.md`
- Prior throughput story: `docs/user-stories/us-m2-file-first-throughput.md`
- Execution plan: `.agent/plans/linear-delivery-plan.md`
