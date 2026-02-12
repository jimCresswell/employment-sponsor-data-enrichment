# Operational Discoveries

This document captures durable operational findings promoted from execution-plan sessions.

Planning artefacts should reference this document instead of storing long-form operational
narratives directly.

## 2026-02-08

1. Pipeline orchestration is non-interactive (`run-all`), but strict reproducibility still
   depends on explicit output-state control because `transform-enrich` defaults to resume mode.
1. Sponsor organisations without a qualifying Companies House match are excluded from
   `sponsor_enriched.csv` and retained in `sponsor_unmatched.csv`.
1. Companies House clean parsing supports URI host/path variants and `DD/MM/YYYY`
   incorporation-date inputs.
1. Option 1 profile-loading refactor removed repeated full profile-bucket scans as the main
   runtime blocker.
1. Full live Step 4 run completed unattended in `44m52s` with `100,849` matched and `18,260`
   unmatched organisations.
1. Live snapshot-manifest drift was observed (companies-house manifests without
   `artefacts.manifest`) and resolved in validation contracts.

## 2026-02-09

1. Deterministic enrichment-audit tooling was added with strict/non-strict threshold behaviour.
1. Scenario fixtures and script coverage were expanded for structural output risks.
1. Live audit baseline metrics were captured for enriched/unmatched and warning-threshold checks.
1. Processed artefacts are commit-allowed when intentional and reviewable.

## 2026-02-10

1. Deterministic rerun validation now includes two unchanged `--no-resume` enrich runs and
   resume-zero invariants.
1. Track A runtime optimisation evidence was captured; Option 2 remained deferred by trigger gate.
1. Scoring-profile contracts were externalised and documented with deterministic selection tests.
1. Durable contracts were promoted across `README.md`, `docs/data-contracts.md`,
   `docs/validation-protocol.md`, and `docs/troubleshooting.md`.

## 2026-02-11

1. Repository policy for intentional `data/processed` commits was made explicit.
1. Batch-first execution discipline was hardened in active planning docs.
1. Non-tech starter profile coverage (`care_support`) was added and documented.
1. Recurring validation-evidence cadence guidance was established.

## 2026-02-12

1. Value stories and requirements were promoted to permanent docs (`docs/user-stories/`,
   `docs/requirements/`).
1. Large-employer targeting (`>= 1000` employees) has explicit config/CLI contracts.
1. Size-signal runtime scoring remains a known contract limitation until later Milestone 7 batches.
1. Milestone 7 remains active with next execution batch `M7-B3`.
