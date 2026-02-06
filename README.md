# UK Sponsor → Tech Hiring Pipeline

A data pipeline that transforms the UK Home Office sponsor register into a shortlist of tech companies likely to hire senior engineers who need visa sponsorship.

## Pipeline Overview

```text
GOV.UK Sponsor Register → refresh-sponsor → sponsor snapshot (clean.csv)
Companies House Bulk CSV → refresh-companies-house → CH snapshot (clean.csv + index + profiles)
Snapshots → Transform Enrich → Transform Score → Usage Shortlist
```

| Step               | Input       | Output                                      | What it does                                        |
| ------------------ | ----------- | ------------------------------------------- | --------------------------------------------------- |
| refresh-sponsor    | CSV URL     | `data/cache/snapshots/sponsor/<YYYY-MM-DD>/...` | Downloads, validates, writes raw+clean+manifest     |
| refresh-companies-house | ZIP or CSV URL | `data/cache/snapshots/companies_house/<YYYY-MM-DD>/...` | Downloads/extracts, cleans, indexes, writes profiles + manifest |
| transform-enrich   | Clean snapshots | `data/processed/companies_house_*.csv` | Enriches using file-first or API source             |
| transform-score    | Enriched CSV | `data/processed/companies_scored.csv`      | Scores for tech-likelihood                          |
| usage-shortlist    | Scored CSV   | `data/processed/companies_shortlist.csv` and `data/processed/companies_explain.csv` | Filters scored output into shortlist + explain      |

Steps describe artefact boundaries for audit and resume. They are not architectural boundaries; orchestration and shared standards live in the application pipeline (see `docs/architectural-decision-records/adr0012-artefact-boundaries-and-orchestration.md`).

## Quick Start

### Prerequisites

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) (fast Python package manager)
- Companies House API key (required only for `CH_SOURCE_TYPE=api`)

### Installation

```bash
# Clone and enter directory
cd uk-sponsor-tech-hiring-pipeline

# Install uv (if needed)
./scripts/install-uv

# Create and sync a uv environment
uv venv
uv sync --group dev

# Copy env template and configure source
cp .env.example .env
# Edit .env: set CH_SOURCE_TYPE and, if using the API, set CH_API_KEY
```

### Run the Full Pipeline

```bash
# Refresh snapshots (run when source data changes)
# If --url is omitted, the pipeline discovers links from the source pages.
uv run uk-sponsor refresh-sponsor
uv run uk-sponsor refresh-companies-house

# Discovery-only (prints resolved source URL, no download/clean)
uv run uk-sponsor refresh-sponsor --only discovery
uv run uk-sponsor refresh-companies-house --only discovery

# Acquire-only (download, plus ZIP extract for Companies House)
uv run uk-sponsor refresh-sponsor --only acquire
uv run uk-sponsor refresh-companies-house --only acquire

# Clean-only (finalise latest pending acquire into a snapshot)
uv run uk-sponsor refresh-sponsor --only clean
uv run uk-sponsor refresh-companies-house --only clean

# Or provide explicit URLs
uv run uk-sponsor refresh-sponsor --url <csv-url>
uv run uk-sponsor refresh-companies-house --url <zip-url>

# Cache-only pipeline run
uv run uk-sponsor run-all

# Or run each step individually:
uv run uk-sponsor refresh-sponsor
uv run uk-sponsor refresh-companies-house
uv run uk-sponsor refresh-sponsor --url <csv-url>
uv run uk-sponsor refresh-companies-house --url <zip-url>
uv run uk-sponsor transform-enrich
uv run uk-sponsor transform-score
uv run uk-sponsor usage-shortlist
```

`uv run <command>` executes tools inside the project environment.
`run-all` consumes clean snapshots only and fails fast if required artefacts are missing.
Refresh commands emit progress for download and clean; `refresh-companies-house` also emits index progress.
Download totals can be unknown for some sources, so progress may advance without a fixed total.

`--only` values:

- `refresh-sponsor --only`: `all`, `discovery`, `acquire`, `clean`
- `refresh-companies-house --only`: `all`, `discovery`, `acquire`, `clean`
- `run-all --only`: `all`, `transform-enrich`, `transform-score`, `usage-shortlist`

For `--only clean`, the command consumes the latest pending acquire staging run for that dataset.
If none exists, run `--only acquire` first.

### Transform Enrich Batching and Resume

Transform Enrich runs in batches by default using `CH_BATCH_SIZE`. You can control which batches run:
It consumes clean snapshot artefacts, so refresh snapshots before running.

```bash
# Run only the first 2 batches (after resume filtering)
uv run uk-sponsor transform-enrich --batch-count 2

# Start at batch 3 and run 2 batches
uv run uk-sponsor transform-enrich --batch-start 3 --batch-count 2

# Override batch size for this run
uv run uk-sponsor transform-enrich --batch-size 50
```

Resume data is written to `data/processed/companies_house_checkpoint.csv` and
`data/processed/companies_house_resume_report.json` (includes overall batch range and timing).

Transform Enrich fails fast on authentication, rate limit, circuit breaker, or unexpected HTTP errors. Fix the issue and rerun with `--resume`; the resume report includes a ready‑made command.

When running with `--no-resume`, Transform Enrich writes to a new timestamped subdirectory under the output directory to avoid stale data reuse.

### Companies House Source (API or Snapshot)

Transform Enrich is file-first when `CH_SOURCE_TYPE=file` (recommended for cache-only runs)
and reads Companies House bulk snapshot artefacts.
Snapshot paths are resolved from `SNAPSHOT_ROOT` unless explicit paths are set.

To use the Companies House API instead, set:

```bash
export CH_SOURCE_TYPE=api
export CH_API_KEY=your_companies_house_api_key
```

To use the file snapshot source explicitly, set:

```bash
export CH_SOURCE_TYPE=file
export CH_CLEAN_PATH=data/cache/snapshots/companies_house/<YYYY-MM-DD>/clean.csv
export CH_TOKEN_INDEX_DIR=data/cache/snapshots/companies_house/<YYYY-MM-DD>
```

The legacy JSON file source has been removed.

## Documentation

- `docs/refresh-and-run-all-diagrams.md` (refresh + cache-only flow diagrams)
- `docs/snapshots.md` (snapshot layout, manifests, and resolution)
- `docs/data-contracts.md` (Companies House canonical schema and mapping)
- `docs/companies-house-file-source.md` (file-first token index rules)
- `docs/validation-protocol.md` (file-first validation steps and e2e fixture run)
- `docs/troubleshooting.md` (common failures and recovery)

### Geographic Filtering

Usage shortlist applies geographic filters to scored output (run `transform-score` first or use
`run-all`). Filter the final shortlist by region or postcode (single region only):

```bash
# Filter to London companies only
uv run uk-sponsor usage-shortlist --region London

# Single region only
uv run uk-sponsor usage-shortlist --region London

# Postcode prefix filtering
uv run uk-sponsor usage-shortlist --postcode-prefix EC --postcode-prefix SW

# Adjust score threshold (default: 0.55)
uv run uk-sponsor usage-shortlist --threshold 0.40

# Full pipeline with filters
uv run uk-sponsor run-all --region London --threshold 0.50
```

Location aliases live in `data/reference/location_aliases.json` and expand region/locality/postcode matching
(for example, `--region Manchester` matches Salford and M* postcodes). Override the file location with
`LOCATION_ALIASES_PATH` if needed.

## Architecture

### Architecture Direction

The long‑term direction is an application‑owned pipeline: orchestration and step ownership live in an application layer, domain logic is pure and infrastructure is shared and injected. CSV artefacts remain as audit and resume boundaries. The CLI delegates concrete wiring to the composition root.

Observability is standardised via a shared logger factory with UTC timestamps so pipeline logs remain consistent across steps.

### Project Structure

```text
src/uk_sponsor_pipeline/
├── cli.py              # Typer CLI entry point
├── composition.py      # Composition root for CLI wiring
├── config.py           # Pipeline configuration
├── io_contracts.py     # IO boundary contracts for infrastructure
├── io_validation.py    # Boundary-neutral IO validation helpers
├── protocols.py        # Interface-style contracts
├── application/        # Use-case orchestration
│   ├── companies_house_source.py
│   ├── refresh_sponsor.py
│   ├── refresh_companies_house.py
│   ├── pipeline.py
│   ├── transform_enrich.py
│   ├── transform_score.py
│   └── usage.py
├── infrastructure/     # Concrete implementations (DI pattern)
│   ├── io/
│   │   ├── filesystem.py
│   │   ├── http.py
│   └── resilience.py
├── domain/
│   ├── companies_house.py
│   ├── location_profiles.py
│   ├── organisation_identity.py
│   ├── scoring.py
│   └── sponsor_register.py
├── observability/      # Shared logging helpers
├── schemas.py          # Column contracts per step

tests/
├── application/
├── cli/
├── config/
├── devtools/
├── domain/
├── infrastructure/
├── integration/
├── network/
├── observability/
├── protocols/
└── conftest.py         # Pytest fixtures and fakes
```

Application modules implement pipeline steps and orchestration; the CLI delegates to them via the composition root (see `composition.py`). Track the refactor in `/.agent/plans/refactor-plan.md`.

### Dependency Injection

Dependency injection keeps I/O and external services swappable for tests:

```python
# protocols.py - defines the interface
class HttpClient(Protocol):
    def get_json(self, url: str, cache_key: str) -> Mapping[str, object]: ...

# infrastructure/http.py - production implementation
class CachedHttpClient:
    def get_json(self, url: str, cache_key: str) -> Mapping[str, object]:
        # Real HTTP + caching logic

# tests/fakes/http.py - test implementation
class FakeHttpClient:
    def get_json(self, url: str, cache_key: str) -> Mapping[str, object]:
        return self.responses.get(cache_key, {})
```

Application entry points require a `PipelineConfig` instance and injected dependencies; environment
variables are read once at the CLI entry point and passed through. Cache-only runs expect clean
snapshots (resolved from `SNAPSHOT_ROOT` or explicit paths). For programmatic use:

```python
from uk_sponsor_pipeline.composition import build_cli_dependencies
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.application.pipeline import run_pipeline

config = PipelineConfig.from_env()
deps = build_cli_dependencies(
    config=config,
    cache_dir="data/cache/companies_house",
    build_http_client=(config.ch_source_type == "api"),
)
result = run_pipeline(
    config=config,
    fs=deps.fs,
    http_client=deps.http_client,
    http_session=deps.http_session,
)
```

Test doubles live in `tests/fakes/`; `tests/conftest.py` provides fixtures that instantiate them.

### Running Tests

Note: The test suite blocks all real network access. Use fakes/mocks for HTTP.

```bash
# All tests
uv run test

# Verbose output
uv run test -v

# Specific test file
uv run test tests/domain/test_organisation_identity.py

# Specific test class
uv run test tests/domain/test_scoring.py::TestScoreFromSic

# With coverage (fails if below 85%)
uv run coverage
```

### Project Scripts (uv-backed)

```bash
# Lint
uv run lint

# Format
uv run format

# Format check (CI style)
uv run format-check

# Type check
uv run typecheck

# US spelling check
uv run spelling-check

# Full quality gate run (format → typecheck → lint → test → coverage)
uv run check
```

`uv run lint` is the single lint entry point. It runs ruff, the inline ignore check, the US spelling scan, and import‑linter.
The spelling scan checks identifiers, comments/docstrings, and string literals, but ignores string literals used for comparisons or matching (external tokens) and skips inline/fenced code in docs.
Linting also enforces fail‑fast exception handling (`TRY`, `BLE`), no private member access (`SLF001`), no `print` outside the CLI (`T20`), and timezone‑aware datetimes (`DTZ`).

## Scoring Model (Transform Score)

Companies are scored on multiple features:

| Feature        | Weight Range  | Source                                         |
| -------------- | ------------- | ---------------------------------------------- |
| SIC tech codes | 0.0–0.50      | Companies House profile                        |
| Active status  | 0.0 or 0.10   | Companies House profile                        |
| Company age    | 0.0–0.15      | Date of creation                               |
| Company type   | 0.0–0.10      | Ltd, PLC, LLP, etc.                            |
| Name keywords  | -0.10 to 0.15 | "software", "digital" vs "care", "recruitment" |

**Role-fit buckets:**

- **strong** (≥0.55): High probability tech company
- **possible** (≥0.35): Worth investigating
- **unlikely** (<0.35): Probably not tech

Usage shortlist applies thresholds and geographic filters to the scored artefact to produce the
final shortlist and explainability outputs.

## Output Files

When running Transform Enrich with `--no-resume`, outputs are written under a timestamped
subdirectory of `data/processed/` (paths below reflect the default `--resume` behaviour).

### Snapshot Outputs (Refresh Commands)

**Sponsor snapshot**
| File                                                         | Description                         |
| ------------------------------------------------------------ | ----------------------------------- |
| `data/cache/snapshots/sponsor/<YYYY-MM-DD>/raw.csv`           | Raw sponsor register CSV            |
| `data/cache/snapshots/sponsor/<YYYY-MM-DD>/clean.csv`         | Clean sponsor register CSV          |
| `data/cache/snapshots/sponsor/<YYYY-MM-DD>/register_stats.json` | Filtering statistics              |
| `data/cache/snapshots/sponsor/<YYYY-MM-DD>/manifest.json`     | Snapshot manifest                   |

**Companies House snapshot**
| File                                                         | Description                         |
| ------------------------------------------------------------ | ----------------------------------- |
| `data/cache/snapshots/companies_house/<YYYY-MM-DD>/raw.zip`   | Raw download (when source is ZIP)   |
| `data/cache/snapshots/companies_house/<YYYY-MM-DD>/raw.csv`   | Extracted raw CSV (ZIP sources)     |
| `data/cache/snapshots/companies_house/<YYYY-MM-DD>/clean.csv` | Canonical clean CSV                 |
| `data/cache/snapshots/companies_house/<YYYY-MM-DD>/index_tokens_<bucket>.csv` | Token index buckets |
| `data/cache/snapshots/companies_house/<YYYY-MM-DD>/profiles_<bucket>.csv` | Bucketed profiles |
| `data/cache/snapshots/companies_house/<YYYY-MM-DD>/manifest.json` | Snapshot manifest               |

### Pipeline Outputs (Cache-Only Run)

| File                                                | Description                                   |
| --------------------------------------------------- | --------------------------------------------- |
| `data/processed/companies_house_enriched.csv`        | Matched companies with CH data                |
| `data/processed/companies_house_unmatched.csv`       | Orgs that couldn't be matched                 |
| `data/processed/companies_house_candidates_top3.csv` | Audit trail: top 3 match candidates per org   |
| `data/processed/companies_house_checkpoint.csv`      | Resume checkpoint of processed orgs           |
| `data/processed/companies_house_resume_report.json`  | Resume report for interrupted or partial runs |
| `data/processed/companies_scored.csv`                | All companies with scores                     |
| `data/processed/companies_shortlist.csv`             | Filtered shortlist (usage output)             |
| `data/processed/companies_explain.csv`               | Score breakdown for shortlist (usage output)  |

## Contributing

```bash
uv sync --group dev
uv run format
uv run typecheck
uv run lint
uv run test
uv run coverage
```

Notes:

- Tests block all real network access; use fakes in `tests/conftest.py`.
- Keep behaviour and docs in sync with the CLI and pipeline outputs.
- No compatibility layers; delete replaced code paths.

### Git Hooks (Quality Gates)

Install pre-commit hooks to run the full quality gates on commit and push:

```bash
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

Notes:

- `uv run check` runs the mutating formatter (`ruff format`) first.
- Git hooks run `format-check` (non-mutating) before the other gates.

## Troubleshooting

- **Missing snapshots**: run `refresh-sponsor` and `refresh-companies-house`, or set `SPONSOR_CLEAN_PATH`, `CH_CLEAN_PATH`, and `CH_TOKEN_INDEX_DIR` explicitly. See `docs/troubleshooting.md`.
- **Companies House 401/403**: ensure `CH_API_KEY` is a valid API key and not an OAuth token; Transform Enrich uses Basic Auth with the key as username and a blank password (API source only). See `docs/troubleshooting.md`.

## Future Work

- CI/CD workflow to run quality gates automatically.

## Configuration

Set in `.env` or environment variables:

```bash
CH_SOURCE_TYPE=file          # file (snapshot) or api
SNAPSHOT_ROOT=data/cache/snapshots
SPONSOR_CLEAN_PATH=
CH_CLEAN_PATH=
CH_TOKEN_INDEX_DIR=
CH_FILE_MAX_CANDIDATES=500   # File-based candidate cap
CH_API_KEY=your_companies_house_api_key
CH_SLEEP_SECONDS=0.2          # Delay between API calls
CH_MAX_RPM=600                # Rate limit (requests per minute)
CH_TIMEOUT_SECONDS=30         # HTTP timeout in seconds
CH_MAX_RETRIES=3              # Retry attempts for transient errors
CH_BACKOFF_FACTOR=0.5         # Exponential backoff factor
CH_BACKOFF_MAX_SECONDS=60     # Max backoff delay
CH_BACKOFF_JITTER_SECONDS=0.1 # Random jitter added to backoff
CH_CIRCUIT_BREAKER_THRESHOLD=5  # Failures before opening breaker
CH_CIRCUIT_BREAKER_TIMEOUT_SECONDS=60  # Seconds before half-open probe
CH_BATCH_SIZE=250             # Organisations per batch (incremental output)
CH_MIN_MATCH_SCORE=0.72       # Minimum score to accept a match
CH_SEARCH_LIMIT=10            # Candidates per search (API)
TECH_SCORE_THRESHOLD=0.55     # Minimum score for shortlist (usage)
GEO_FILTER_REGIONS=           # Single region filter (one value only)
GEO_FILTER_POSTCODES=         # Comma-separated postcode prefix filter
```

## Data Sources

- **Sponsor Register**: [GOV.UK Register of Licensed Sponsors](https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers)
- **Companies House**: [Public Data API](https://developer.company-information.service.gov.uk/) (optional) and Free Data Product bulk CSV snapshots

## Security

- Never commit `.env` (it's in `.gitignore`)
- Rotate your Companies House API key if shared
- Cache contains API response data—treat as sensitive
