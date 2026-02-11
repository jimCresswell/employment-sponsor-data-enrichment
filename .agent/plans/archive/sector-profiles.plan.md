> Archived Plan Notice (2026-02-11): this file is historical reference only.
> Do not execute this plan directly.
> Active execution queue: `.agent/plans/linear-delivery-plan.md`.
> Durable contracts and operational guidance live in `README.md`, `docs/`, and `docs/architectural-decision-records/`.

# Plan: Sector Profiles for Transform-Score (Configurable)

Planning note: milestone sequencing and acceptance gating are tracked in
`.agent/plans/linear-delivery-plan.md`.

## Goal

Make transform-score sector‑agnostic by externalising scoring signals (SIC mappings, keywords,
weights, thresholds) into profiles that can be selected via CLI or environment, while preserving
current tech behaviour as the default profile.

Note: we should also look into defining location profiles, e.g. mapping London to a town, city, collection of postcodes, etc. so that the user idea of "London" is consistent with the varied data we have.

## Non‑Goals

- No change to extract, transform-register, or transform-enrich behaviour.
- No new UI or database features.

## Proposed Design

### Config Format

- Add a profile file (YAML or JSON) that defines:
  - `sector_name`
  - `sic_positive_prefixes` (prefix → weight)
  - `sic_negative_prefixes` (prefix → weight)
  - `keyword_positive` (list)
  - `keyword_negative` (list)
  - `weights` for non‑SIC signals (status, age, type, keyword caps)
  - `thresholds` for bucket boundaries and shortlist cutoff
- Provide a default `tech` profile file that matches current behaviour.

### CLI + Env

- Add `--sector-profile` (path) and `--sector` (named profile) to transform-score.
- Add env var `SECTOR_PROFILE` (path) and `SECTOR_NAME` (named profile).
- Default: current tech profile if none provided.

### Code Structure (aligned with refactor plan)

- `domain/scoring/` consumes a `ScoringProfile` object.
- A loader module reads profile files and validates schema.
- Transform-score uses the loader, then passes the profile into scoring.

## TDD Strategy

- Add characterization tests for current scoring output (tech profile).
- Add tests for profile loading and validation (invalid keys, missing fields).
- Add tests that a custom profile changes scoring outcomes as expected.

## Acceptance Criteria

- Default behaviour is unchanged when no profile is specified.
- A profile file can override SIC/keyword/weight logic.
- CLI and env options select the intended profile.
- All tests remain network‑isolated.
- Quality gates pass.

## Definition of Done

- Profile schema documented in README.
- At least one non‑tech example profile included in `docs/`.
- Stage 3 scoring is fully driven by the profile object.
- `uv run check` passes.
