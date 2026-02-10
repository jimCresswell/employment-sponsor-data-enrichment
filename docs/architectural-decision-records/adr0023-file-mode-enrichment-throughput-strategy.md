# ADR 0023: File-Mode Enrichment Throughput Strategy

Date: 2026-02-08

## Status

Accepted

## Context

Milestone 2 operational baseline execution exposed a throughput failure in file-mode
`transform-enrich` against the live Companies House bulk snapshot (`2026-02-01`):

- `FileCompaniesHouseSource._load_profiles_for_numbers(...)` repeatedly scans full
  `profiles_<bucket>.csv` files for incremental lookup requests.
- Live profile artefacts are large enough that repeated scans make runtime
  operationally impractical for unattended end-to-end runs.
- Primary use case is single-run pipeline execution per upstream refresh cycle, then
  downstream use of produced outputs without repeated enrich reruns.

Two optimisation paths were considered:

1. Option 1: single-pass loading per bucket for required company numbers.
2. Option 2: refresh-time offset index for direct row seeks by company number.

## Decision

- Adopt Option 1 for Milestone 2 unblock:
  - Refactor file-mode profile loading to avoid repeated full scans during one enrich run.
  - Keep all existing artefact contracts and CLI interfaces unchanged.
- Defer Option 2 for now.
- Trigger Option 2 only if Option 1 fails either condition:
  - Step 4 runtime commands (`transform-enrich` → `transform-score` →
    `usage-shortlist`) cannot complete unattended within 6 hours on baseline live
    snapshot scale.
  - Repeated enrich reruns on unchanged snapshots become a normal operational need.

## Consequences

- Lowest-risk path to restore practical unattended pipeline execution for current use
  cases.
- Preserves existing snapshot artefacts, validation scripts, and command contracts.
- Keeps future headroom: offset-index architecture remains an explicit follow-on path
  with objective trigger criteria.

## Decision Gate Review (`M3-P4`, 2026-02-10)

### Trigger Evaluation

1. Trigger: Step 4 runtime commands cannot complete unattended within 6 hours on
   baseline live snapshot scale.
   - Evidence: full live Step 4 baseline run completed in `44m52s` (`transform-enrich`
     for `119,109` sponsor organisations, 2026-02-08 protocol record).
   - Result: **not triggered**.
2. Trigger: repeated enrich reruns on unchanged snapshots become a normal operational
   need.
   - Evidence: deterministic rerun capability is validated in fixture e2e flow, but no
     operational requirement change has been recorded that makes repeated unchanged-input
     reruns a standard workflow.
   - Result: **not triggered**.

### Outcome

- Option 2 remains deferred after `M3-P4`.
- Continue with profile externalisation batches (`M3-B1` onward) while preserving this
  trigger-based re-entry rule for Option 2.
