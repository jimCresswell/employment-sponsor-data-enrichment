# Project Definition: UK Sponsor → Tech Hiring Pipeline

## Purpose
Produce a reproducible, auditable shortlist of UK sponsor‑licensed companies likely to hire senior engineers who require visa sponsorship. The goal is to replace manual scanning with a transparent, explainable pipeline.

## Read Order
- `AGENT.md` → `rules.md` → this file.

## Principles
- Reproducible runs with stable, staged artefacts.
- Clear audit trail at every stage.
- Fail fast with helpful errors; no silent failures.
- No compatibility layers; remove legacy paths.
- Tests are fully network‑isolated.

## Pipeline Summary
1. **download** → fetches latest GOV.UK sponsor register CSV, validates schema, writes a manifest with SHA256 hash.
2. **stage1** → filters Skilled Worker + A‑rated, normalises organisation names, outputs stats.
3. **stage2** → enriches via Companies House with caching, rate limits, retries, and circuit breaker; records top candidates.
4. **stage3** → applies a multi‑feature tech‑likelihood score and produces a shortlist plus explainability output.

## CLI + Key Commands
- Run the full pipeline: `uv run uk-sponsor run-all`
- Individual stages: `uv run uk-sponsor download|stage1|stage2|stage3`
- Quality gates: `uv run format`, `uv run typecheck`, `uv run lint`, `uv run test`, `uv run coverage`
- Install uv if needed: `./scripts/install-uv`

## Repository Structure
- `src/uk_sponsor_pipeline/` pipeline code
  - `cli.py` CLI entry point
  - `config.py` pipeline configuration
  - `protocols.py` interface-style contracts
  - `infrastructure.py` concrete I/O implementations
  - `normalization.py` org name processing
  - `schemas.py` stage column contracts
  - `stages/` stage implementations
- `tests/` pytest tests and fakes (`tests/conftest.py`)
- `data/` pipeline outputs (`raw/`, `interim/`, `processed/`)
- `reports/` manifests and stats
- `scripts/` helper scripts (e.g., `install-uv`)

## Outputs
- `reports/download_manifest.json`
- `reports/stage1_stats.json`
- `data/processed/stage2_enriched_companies_house.csv`
- `data/processed/stage2_unmatched.csv`
- `data/processed/stage2_candidates_top3.csv`
- `data/processed/stage3_scored.csv`
- `data/processed/stage3_shortlist_tech.csv`
- `data/processed/stage3_explain.csv`

## Configuration
Loaded once at the CLI entry point and passed through the pipeline. Values are defined in `.env.example`.

## Security
- Use `.env` for secrets; never commit it.
- Treat cached API responses as sensitive data.

## Current Status
- End‑to‑end pipeline is implemented with robust error handling.
- Tests are isolated from the network and include an in‑memory pipeline run.
- Coverage gate is enforced at 85%.

## Next Priorities
See `.agent/plans/plan.md` for the single consolidated roadmap.

## Non‑Goals
- No dashboard/reporting UI.
- No plugin architecture.
- No SQLite persistence layer.
