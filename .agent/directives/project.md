# Project Definition: UK Sponsor → Hiring Signals Pipeline

## Purpose

Produce a reproducible, auditable shortlist of UK sponsor‑licensed companies likely to hire for target job types that require visa sponsorship. The goal is to replace manual scanning with a transparent, explainable pipeline.

Current scoring defaults are tech-role focused as an early proof of concept. The target product
direction is broader filtering and ranking across job type, sector, location, and organisation
size.

## Read Order

- `AGENT.md` → `rules.md` → this file.

## Vision

- A clear, explainable pipeline that can be rerun and audited.
- A focused scope that avoids unnecessary systems or interfaces.
- Engineering quality that enables safe iteration and refactoring.

## Principles

- Reproducible runs with stable artefacts at each step.
- Clear audit trail at every step.
- Fail fast with helpful errors; no silent failures.
- No compatibility layers; remove legacy paths.
- Tests are fully network‑isolated.

## Pipeline Summary (High Level)

1. **refresh-sponsor** → download and clean the GOV.UK sponsor register snapshot.
2. **refresh-companies-house** → download, clean, and index the bulk Companies House snapshot.
3. **transform-enrich** → enrich sponsor data using Companies House (file-first by default).
4. **transform-score** → score with the active role/profile model and write the scored artefact.
5. **usage-shortlist** → apply threshold, geographic, and size filters, then produce shortlist + explainability.

Pipeline runs (for example `run-all`) consume clean snapshots only and fail fast if required
artefacts are missing.

## Non‑Goals

- No dashboard/reporting UI.
- No plugin architecture.
- No SQLite persistence layer.

## Operational Details

Operational usage, commands, outputs, and configuration live in `README.md` and `docs/`.
