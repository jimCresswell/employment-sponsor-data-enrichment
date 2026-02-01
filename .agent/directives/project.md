# Project Definition: UK Sponsor → Tech Hiring Pipeline

## Purpose

Produce a reproducible, auditable shortlist of UK sponsor‑licensed companies likely to hire senior engineers who require visa sponsorship. The goal is to replace manual scanning with a transparent, explainable pipeline.

## Read Order

- `AGENT.md` → `rules.md` → this file.

## Vision

- A clear, explainable pipeline that can be rerun and audited.
- A focused scope that avoids unnecessary systems or interfaces.
- Engineering quality that enables safe iteration and refactoring.

## Principles

- Reproducible runs with stable, staged artefacts.
- Clear audit trail at every stage.
- Fail fast with helpful errors; no silent failures.
- No compatibility layers; remove legacy paths.
- Tests are fully network‑isolated.

## Pipeline Summary (High Level)

1. **download** → fetch latest GOV.UK sponsor register data.
2. **stage1** → filter Skilled Worker + A‑rated and aggregate by organisation.
3. **stage2** → enrich with Companies House data using reliable, rate‑limited access.
4. **stage3** → score for tech‑likelihood and produce a shortlist with explainability.

## Non‑Goals

- No dashboard/reporting UI.
- No plugin architecture.
- No SQLite persistence layer.

## Operational Details

Operational usage, commands, outputs, and configuration live in `README.md` and `docs/`.
