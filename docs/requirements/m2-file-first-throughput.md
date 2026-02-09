# Requirements: M2 File-First Throughput Unblock

Date: 2026-02-08  
Owner: Milestone 2 (`M2-B1`)

## Scope

Define concrete implementation and validation requirements for unblocking the
file-first operational baseline run.

## Functional Requirements

1. File-mode profile lookup must avoid repeated full scans of `profiles_<bucket>.csv`
   during a single enrich run.
1. Runtime output contracts must remain unchanged:
1. matched organisations in `sponsor_enriched.csv`
1. unmatched organisations in `sponsor_unmatched.csv`
1. candidate audit output and resume report behaviour unchanged
1. CLI command interfaces must remain unchanged for this batch.

## Non-Functional Requirements

1. Runtime steps (`transform-enrich` → `transform-score` → `usage-shortlist`) must run
   unattended on baseline live snapshot scale.
1. Quality gates must pass (`uv run check`).
1. Tests must stay network-isolated.

## Verification Requirements

1. Add or update tests proving the new profile-loading strategy and fail-fast behaviour.
1. Execute the Milestone 2 validation protocol steps with real snapshot dates/URLs
   captured in the run log.
1. Confirm snapshot/output validation scripts pass after runtime completion.

## Escalation Rule

If Option 1 cannot satisfy unattended runtime expectations for baseline live snapshot
scale, or repeated reruns on unchanged snapshots become routine, escalate to Option 2
offset-index implementation per ADR 0023.

## Traceability

- User story: `docs/user-stories/us-m2-file-first-throughput.md`
- Architecture decision: `docs/architectural-decision-records/adr0023-file-mode-enrichment-throughput-strategy.md`
- Execution plan: `.agent/plans/linear-delivery-plan.md`
