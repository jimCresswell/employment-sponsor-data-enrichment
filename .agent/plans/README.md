# Plans Index

This directory contains planning documents for active and historical work.

## Active Plans

| File | Purpose | Status | Owner | Last Updated |
| --- | --- | --- | --- | --- |
| `.agent/plans/linear-delivery-plan.md` | Single ordered execution path with milestone requirements and acceptance criteria. | Active (Milestone 7 complete; `Next batch to execute: M8-B1`; Milestone 8 queued for grouped `admin`/`search` CLI + denormalised search views) | Jim + Codex | 2026-02-12 |
| `.agent/plans/deferred-features.md` | Backlog items not in the active linear path. | Active backlog (currently empty) | Jim + Codex | 2026-02-10 |

## Archived Completed Plans

| File | Purpose | Status | Owner | Last Updated |
| --- | --- | --- | --- | --- |
| `.agent/plans/archive/file-only-di-onboarding-improvement.plan.md` | Source proposal mapped into Milestone 0 execution batches in the linear plan. | Archived (completed/promotion finished) | Jim + Codex | 2026-02-06 |

## Archived Reference Plans

Legacy or completed planning artefacts live in `.agent/plans/archive/` and are reference-only.
Do not execute directly without explicitly promoting requirements into
`.agent/plans/linear-delivery-plan.md`.
Each archived file carries an explicit archive banner.

## Operating Rule

1. Start from `.agent/plans/linear-delivery-plan.md` for current implementation.
1. Use `.agent/plans/deferred-features.md` for backlog capture only.
1. Keep archived plans immutable except for historical clarification notes.
1. Keep durable operational records in `docs/validation-run-evidence.md` and
   `docs/operational-discoveries.md` rather than active plans.

## Batch-First Discipline

1. Treat `.agent/plans/linear-delivery-plan.md` as the authoritative execution queue.
1. Start implementation from `Next batch to execute` unless a batch is already `In progress`.
1. Keep only one `In progress` batch at a time.
1. Update batch state, status board, and closeout log in the same change that completes a batch.
1. Do not execute backlog or archived plan items directly without promoting them into the active linear plan.
