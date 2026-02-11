# UK Sponsor -> Hiring Signals Pipeline

This project turns public UK sponsor and Companies House data into a reproducible shortlist of
organisations likely to hire for target job types that require visa sponsorship.

The goal is practical impact: reduce manual searching, keep every decision auditable, and make
improvements easy for contributors to ship safely.

Current scoring defaults are tech-role focused as an early proof of concept. The intended
direction is broader: user-selectable job-type, sector, location, and size filters.

## Project Intent

We are building a pipeline that is:

- **Reproducible**: the same inputs and config produce the same artefacts.
- **Auditable**: every step writes explicit artefacts and manifests.
- **Actionable**: outputs are ready for outreach and prioritisation.
- **Contributor-friendly**: architecture and tooling are strict but straightforward.

## Who This Is For

- Engineers who need a reliable shortlist generation workflow.
- Data practitioners who want to refine matching/scoring quality.
- Contributors who care about improving hiring access and transparency.

## Runtime Model (Important)

- Runtime commands are **file-only** for Companies House (`CH_SOURCE_TYPE=file`).
- Network access is owned by refresh commands (`refresh-sponsor`, `refresh-companies-house`).
- `transform-enrich` and `run-all` fail fast unless `CH_SOURCE_TYPE=file`.
- Archived runtime API wiring notes live in `docs/archived-api-runtime-mode.md`.

## Pipeline Overview

```text
GOV.UK Sponsor Register -> refresh-sponsor -> sponsor snapshot (clean.csv)
Companies House Bulk CSV -> refresh-companies-house -> CH snapshot (clean.csv + index + profiles)
Snapshots -> transform-enrich -> transform-score -> usage-shortlist
```

| Step | Input | Output | Purpose |
| --- | --- | --- | --- |
| `refresh-sponsor` | Sponsor CSV URL | `data/cache/snapshots/sponsor/<YYYY-MM-DD>/...` | Discover, download, clean, snapshot sponsor data |
| `refresh-companies-house` | Companies House ZIP/CSV URL | `data/cache/snapshots/companies_house/<YYYY-MM-DD>/...` | Discover, download/extract, clean, index, snapshot CH data |
| `transform-enrich` | Clean snapshots | `data/processed/sponsor_*.csv` | Match sponsor organisations to CH entities |
| `transform-score` | Enriched CSV | `data/processed/companies_scored.csv` | Apply default role-likelihood scoring profile (currently tech-focused) |
| `usage-shortlist` | Scored CSV | `data/processed/companies_shortlist.csv`, `data/processed/companies_explain.csv` | Apply thresholds and geo filters for final shortlist |

## Quick Start (First Successful Run)

### 1. Prerequisites

- Python 3.14+
- [`uv`](https://github.com/astral-sh/uv)

### 2. Environment Setup

```bash
git clone <repository-url>
cd uk_sponsor_tech_hiring_pipeline_repo

# Install uv if not already available
./scripts/install-uv

uv venv
uv sync --group dev
cp .env.example .env
```

### 3. Configure `.env`

Set at least:

```bash
CH_SOURCE_TYPE=file
SNAPSHOT_ROOT=data/cache/snapshots
```

You can usually leave other values at defaults for the first run.

### 4. Build Snapshots

```bash
uv run uk-sponsor refresh-sponsor
uv run uk-sponsor refresh-companies-house
```

### 5. Run Cache-Only Pipeline

```bash
uv run uk-sponsor run-all
```

### 6. Check Outputs

Expected files in `data/processed/`:

- `sponsor_enriched.csv`
- `sponsor_unmatched.csv`
- `sponsor_match_candidates_top3.csv`
- `sponsor_enrich_checkpoint.csv`
- `sponsor_enrich_resume_report.json`
- `companies_scored.csv`
- `companies_shortlist.csv`
- `companies_explain.csv`

## Command Guide

### Refresh Commands (Grouped Execution)

`refresh-sponsor` and `refresh-companies-house` support:

- `--only discovery`: resolve source URL only
- `--only acquire`: download raw payload (and ZIP extract for CH)
- `--only clean`: finalise latest pending acquire snapshot
- `--only all`: acquire + clean (default)

Examples:

```bash
uv run uk-sponsor refresh-sponsor --only discovery
uv run uk-sponsor refresh-sponsor --only acquire
uv run uk-sponsor refresh-sponsor --only clean

uv run uk-sponsor refresh-companies-house --only discovery
uv run uk-sponsor refresh-companies-house --only acquire
uv run uk-sponsor refresh-companies-house --only clean
```

You can bypass discovery with explicit URLs:

```bash
uv run uk-sponsor refresh-sponsor --url <sponsor-csv-url>
uv run uk-sponsor refresh-companies-house --url <companies-house-zip-url>
```

### Runtime and Processing Commands

```bash
uv run uk-sponsor transform-enrich
uv run uk-sponsor transform-score
uv run uk-sponsor usage-shortlist
uv run uk-sponsor run-all
```

Print installed tool version:

```bash
uv run uk-sponsor --version
```

Optional scoring profile selection:

```bash
uv run uk-sponsor transform-score \
  --sector-profile data/reference/scoring_profiles.json \
  --sector tech
```

By default, `transform-score` always loads `data/reference/scoring_profiles.json` and resolves
the catalogue `default_profile` when no profile override is supplied.

`run-all` supports `--only`:

- `all` (default)
- `transform-enrich`
- `transform-score`
- `usage-shortlist`

### Transform Enrich Resume and Batching

```bash
# Run first two batches after resume filtering
uv run uk-sponsor transform-enrich --batch-count 2

# Start at batch three and run two batches
uv run uk-sponsor transform-enrich --batch-start 3 --batch-count 2

# Override batch size for this run
uv run uk-sponsor transform-enrich --batch-size 50
```

Resume artefacts:

- `data/processed/sponsor_enrich_checkpoint.csv`
- `data/processed/sponsor_enrich_resume_report.json`

When running with `--no-resume`, outputs are written to a timestamped subdirectory under the
selected output directory.
`run-all` uses resume mode for enrich by default, so repeated unchanged-input runs may report
zero additional processed organisations.

### Geographic Filtering (Single Region Contract)

CLI examples:

```bash
uv run uk-sponsor usage-shortlist --region London
uv run uk-sponsor usage-shortlist --postcode-prefix EC --postcode-prefix SW
uv run uk-sponsor run-all --region London --threshold 0.50
```

Environment variables:

```bash
GEO_FILTER_REGION=London
GEO_FILTER_POSTCODES=EC,SW
```

Notes:

- `--region` accepts one value only.
- `GEO_FILTER_REGION` accepts one value only.
- Comma-separated region values fail fast.

## Configuration Reference

Set via `.env` or environment variables:

```bash
CH_SOURCE_TYPE=file
SNAPSHOT_ROOT=data/cache/snapshots
SPONSOR_CLEAN_PATH=
CH_CLEAN_PATH=
CH_TOKEN_INDEX_DIR=
CH_FILE_MAX_CANDIDATES=500

CH_API_KEY=your_companies_house_api_key  # Archived runtime API reference only
CH_SLEEP_SECONDS=0.2
CH_MAX_RPM=600
CH_TIMEOUT_SECONDS=30
CH_MAX_RETRIES=3
CH_BACKOFF_FACTOR=0.5
CH_BACKOFF_MAX_SECONDS=60
CH_BACKOFF_JITTER_SECONDS=0.1
CH_CIRCUIT_BREAKER_THRESHOLD=5
CH_CIRCUIT_BREAKER_TIMEOUT_SECONDS=60
CH_BATCH_SIZE=250
CH_MIN_MATCH_SCORE=0.72
CH_SEARCH_LIMIT=10

TECH_SCORE_THRESHOLD=0.55
SECTOR_PROFILE=
SECTOR_NAME=
GEO_FILTER_REGION=
GEO_FILTER_POSTCODES=
LOCATION_ALIASES_PATH=data/reference/location_aliases.json
```

## Config File Support

You can supply a TOML config file at the CLI entry point:

```bash
uv run uk-sponsor --config config/pipeline.toml run-all
```

Precedence is fixed:

1. CLI command options
2. config file values
3. environment variables (`.env`)
4. built-in defaults

Config files must use this structure:

```toml
schema_version = 1

[pipeline]
ch_source_type = "file"
snapshot_root = "data/cache/snapshots"
ch_batch_size = 250
ch_min_match_score = 0.72
ch_search_limit = 10
tech_score_threshold = 0.55
geo_filter_region = "London"
geo_filter_postcodes = ["EC", "SW"]
sector_profile_path = "data/reference/scoring_profiles.json"
sector_name = "tech"
location_aliases_path = "data/reference/location_aliases.json"
```

Supported `[pipeline]` keys:

- `ch_source_type`
- `snapshot_root`
- `sponsor_clean_path`
- `ch_clean_path`
- `ch_token_index_dir`
- `ch_file_max_candidates`
- `ch_batch_size`
- `ch_min_match_score`
- `ch_search_limit`
- `tech_score_threshold`
- `sector_profile_path`
- `sector_name`
- `geo_filter_region`
- `geo_filter_postcodes`
- `location_aliases_path`

## Programmatic Usage

The CLI is the normal entry point, but library usage is supported.

```python
from pathlib import Path

from uk_sponsor_pipeline.application.pipeline import run_pipeline
from uk_sponsor_pipeline.application.snapshots import resolve_latest_snapshot_path
from uk_sponsor_pipeline.composition import build_cli_dependencies
from uk_sponsor_pipeline.config import PipelineConfig

config = PipelineConfig.from_env()
deps = build_cli_dependencies(
    config=config,
    cache_dir=Path("data/cache/companies_house"),
    build_http_client=False,
)

register_path = resolve_latest_snapshot_path(
    snapshot_root=Path(config.snapshot_root),
    dataset="sponsor",
    filename="clean.csv",
    fs=deps.fs,
)

result = run_pipeline(
    config=config,
    register_path=register_path,
    fs=deps.fs,
    http_client=deps.http_client,
)

print(result.usage["shortlist"])
```

## Contributing for Impact

Contributions are expected to improve either:

- **Pipeline quality**: correctness, reproducibility, fail-fast guarantees.
- **Decision quality**: better matching, scoring, profile selection, and explainability.
- **Operational quality**: clearer onboarding, safer runbooks, stronger validation.

### High-Impact Contribution Areas

1. Data quality checks for refresh and transform outputs.
2. Role/profile improvements (job type first, then sector/location/size) and shortlist explainability.
3. Documentation and onboarding improvements for first-time contributors.
4. Validation tooling and reproducibility checks.

### Contributor Workflow

1. Read `.agent/directives/AGENT.md`, `.agent/directives/rules.md`, `.agent/directives/project.md`, and `.agent/directives/python3.practice.md`.
2. Choose work from `.agent/plans/linear-delivery-plan.md` (current execution roadmap).
3. Follow strict TDD: tests first, implementation second, refactor third.
4. Keep behaviour, tests, and docs aligned in the same change.
5. Run full gates before commit: `uv run check`.
6. Use conventional commits.

### Definition of Done for a Change

- Behaviour implemented with strict typing.
- Tests added or updated and network-isolated.
- Docs updated where behaviour or workflows changed.
- `uv run check` passes locally.

## Engineering Constraints

- No compatibility layers or legacy shims.
- Domain/application code must not import infrastructure directly.
- Environment variables are read at entry points and passed via `PipelineConfig`.
- Application I/O is protocol-backed for testability.
- Tests block real network calls.

## Developer Commands

```bash
uv run format
uv run format-check
uv run typecheck
uv run lint
uv run test
uv run coverage
uv run check
```

Install Git hooks for pre-commit and pre-push quality checks:

```bash
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

## CI and Version Metadata

- GitHub Actions runs the full gate sequence on every push and pull request via
  `.github/workflows/ci.yml`.
- CI installs dependencies with `uv sync --group dev` and executes `uv run check`.
- Snapshot manifests record `tool_version` from `uk_sponsor_pipeline.__version__`.
- If package metadata is unavailable, `tool_version` falls back to `0.0.0+unknown`.

## Validation Tooling

Run contract checks against snapshot and processed artefacts:

```bash
uv run python scripts/validation_check_snapshots.py --snapshot-root data/cache/snapshots
uv run python scripts/validation_check_outputs.py --out-dir data/processed
uv run python scripts/validation_audit_enrichment.py --out-dir data/processed
```

`validation_audit_enrichment.py` contract:

- exit `0`: pass (or warnings in non-strict mode),
- exit `1`: structural/data-contract failure,
- exit `2`: strict mode threshold breach.

Use strict audit mode to fail on warning-threshold breaches:

```bash
uv run python scripts/validation_audit_enrichment.py --out-dir data/processed --strict
```

Run fixture-driven e2e CLI validation (outside pytest):

```bash
uv run python scripts/validation_e2e_fixture.py
```

`validation_e2e_fixture.py` contract:

- runs grouped refresh once,
- runs `transform-enrich --no-resume` twice on unchanged snapshots,
- asserts deterministic byte-identical enrich outputs,
- reruns `transform-enrich --resume` and requires `status=complete`,
  `processed_in_run=0`, and `remaining=0`,
- runs score and shortlist on validated outputs.

## Documentation Map

- `docs/snapshots.md`: snapshot lifecycle, layout, and manifests
- `docs/validation-protocol.md`: reproducible validation runbook
- `docs/troubleshooting.md`: common failure modes and recovery
- `docs/architectural-decision-records/README.md`: architecture decision index and ADR history
- `docs/data-contracts.md`: schema, output partition, and validation contracts
- `docs/companies-house-file-source.md`: file-source lookup/index rules
- `docs/refresh-and-run-all-diagrams.md`: refresh and cache-only flow diagrams
- `docs/archived-api-runtime-mode.md`: archived runtime API wiring notes

## Troubleshooting and Recovery

If you hit issues, start with `docs/troubleshooting.md`. Common causes are:

- missing snapshots for cache-only runs,
- non-file runtime mode,
- invalid geographic filter configuration,
- missing location aliases path.

## Data Sources

- Sponsor Register: <https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers>
- Companies House bulk data: <https://download.companieshouse.gov.uk/en_output.html>
- Companies House API docs (archived runtime reference only): <https://developer.company-information.service.gov.uk/>

## Security and Data Handling

- Never commit `.env` (already gitignored).
- Treat cached payloads as potentially sensitive operational data.
- `data/processed` outputs are reproducible run artefacts and may be committed when intentional.
- Before committing generated processed artefacts, run validation commands and review row-count
  and content diffs for unexpected changes.
- Rotate API keys immediately if exposed.
