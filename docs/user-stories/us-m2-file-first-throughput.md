# User Story: File-First Pipeline Throughput (Milestone 2)

Date: 2026-02-08  
Status: Active

## Story

As a contributor who checks out the repository and runs the pipeline end-to-end,  
I want the file-first pipeline to complete unattended in practical time,  
so that I can use the enriched/scored/shortlist outputs without manual intervention.

## Operational Context

- Typical workflow:
  1. Refresh snapshots from upstream sources.
  1. Run `run-all` (or equivalent staged runtime commands).
  1. Consume produced outputs.
- Repeat frequency:
  - Usually only when upstream datasets change.
- Non-goal:
  - Optimising for frequent reruns on unchanged snapshots.

## Acceptance Criteria

1. Runtime commands complete unattended on baseline live snapshot scale:
1. `transform-enrich`
1. `transform-score`
1. `usage-shortlist`
1. Unmatched sponsor organisations are excluded from enriched output and retained in
   unmatched output for analysis.
1. Existing CLI contracts and output file contracts remain stable.
1. Validation scripts continue to pass for snapshot/output contract checks.

## Notes

- This story is implemented under Milestone 2 (`M2-B1`) and governed by ADR 0023.
- If throughput remains outside acceptable runtime after Option 1 refactor, escalate to
  Option 2 as defined in ADR 0023.
