# UK Sponsor → Tech Hiring Pipeline

A data pipeline that transforms the UK Home Office sponsor register into a shortlist of tech companies likely to hire senior engineers who need visa sponsorship.

## Pipeline Overview

```text
GOV.UK Sponsor Register → Transform Register → Transform Enrich → Transform Score → Shortlist
       (CSV)                    (CSV)               (CSV)              (CSV)
```

| Step               | Input       | Output                                      | What it does                                        |
| ------------------ | ----------- | ------------------------------------------- | --------------------------------------------------- |
| extract            | GOV.UK page | `data/raw/*.csv`                            | Scrapes page, downloads CSV, validates schema       |
| transform-register | Raw CSV     | `data/interim/sponsor_register_filtered.csv` | Filters Skilled Worker + A-rated, aggregates by org |
| transform-enrich   | Register CSV | `data/processed/companies_house_*.csv`     | Enriches via Companies House API                    |
| transform-score    | Enriched CSV | `data/processed/companies_*.csv`           | Scores for tech-likelihood, outputs shortlist       |

Steps describe artefact boundaries for audit and resume. They are not architectural boundaries; orchestration and shared standards live in the application pipeline (see `docs/architectural-decision-records/adr0012-artefact-boundaries-and-orchestration.md`).

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (fast Python package manager)
- Companies House API key ([register free](https://developer.company-information.service.gov.uk/))

### Installation

```bash
# Clone and enter directory
cd uk-sponsor-tech-hiring-pipeline

# Install uv (if needed)
./scripts/install-uv

# Create and sync a uv environment
uv venv
uv sync --group dev

# Copy env template and add your API key
cp .env.example .env
# Edit .env: set CH_API_KEY=your_key_here
```

### Run the Full Pipeline

```bash
# All steps in sequence
uv run uk-sponsor run-all

# Or run each step individually:
uv run uk-sponsor extract
uv run uk-sponsor transform-register
uv run uk-sponsor transform-enrich
uv run uk-sponsor transform-score
```

`uv run <command>` executes tools inside the project environment.

### Transform Enrich Batching and Resume

Transform Enrich runs in batches by default using `CH_BATCH_SIZE`. You can control which batches run:

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

### Companies House Source (API or File)

By default Transform Enrich uses the Companies House API. To use a file source instead, set:

```bash
export CH_SOURCE_TYPE=file
export CH_SOURCE_PATH=data/reference/companies_house.json
```

The file format is JSON:

```json
{
  "searches": [
    {
      "query": "Acme Ltd",
      "items": [
        {
          "title": "ACME LTD",
          "company_number": "12345678",
          "company_status": "active",
          "address": {
            "locality": "London",
            "region": "Greater London",
            "postal_code": "EC1A 1BB"
          }
        }
      ]
    }
  ],
  "profiles": [
    {
      "company_number": "12345678",
      "profile": {
        "company_name": "ACME LTD",
        "company_status": "active",
        "type": "ltd",
        "date_of_creation": "2015-01-01",
        "sic_codes": ["62020"],
        "registered_office_address": {
          "locality": "London",
          "region": "Greater London",
          "postal_code": "EC1A 1BB"
        }
      }
    }
  ]
}
```

### Geographic Filtering

Filter the final shortlist by region or postcode (single region only):

```bash
# Filter to London companies only
uv run uk-sponsor transform-score --region London

# Single region only
uv run uk-sponsor transform-score --region London

# Postcode prefix filtering
uv run uk-sponsor transform-score --postcode-prefix EC --postcode-prefix SW

# Adjust score threshold (default: 0.55)
uv run uk-sponsor transform-score --threshold 0.40

# Full pipeline with filters
uv run uk-sponsor run-all --region London --threshold 0.50
```

Location aliases live in `data/reference/location_aliases.json` and expand region/locality/postcode matching
(for example, `--region Manchester` matches Salford and M* postcodes). Override the file location with
`LOCATION_ALIASES_PATH` if needed.

## Architecture

### Architecture Direction

The long‑term direction is an application‑owned pipeline: orchestration and step ownership live in an application layer, domain logic is pure and infrastructure is shared and injected. CSV artefacts remain as audit and resume boundaries.

Observability is standardised via a shared logger factory with UTC timestamps so pipeline logs remain consistent across steps.

### Project Structure

```text
src/uk_sponsor_pipeline/
├── cli.py              # Typer CLI entry point
├── config.py           # Pipeline configuration
├── io_contracts.py     # IO boundary contracts for infrastructure
├── protocols.py        # Interface-style contracts
├── application/        # Use-case orchestration
│   ├── companies_house_source.py
│   ├── extract.py
│   ├── transform_register.py
│   ├── transform_enrich.py
│   └── transform_score.py
├── infrastructure/     # Concrete implementations (DI pattern)
│   ├── io/
│   │   ├── filesystem.py
│   │   ├── http.py
│   │   └── validation.py
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

Application modules implement pipeline steps; the CLI invokes them directly. Track the refactor in `/.agent/plans/refactor-plan.md`.

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

Application entry points require a `PipelineConfig` instance; environment variables are read once at the CLI entry point and passed through. For programmatic use:

```python
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.application.transform_enrich import run_transform_enrich
from uk_sponsor_pipeline.application.transform_score import run_transform_score

config = PipelineConfig.from_env()
run_transform_enrich(
    register_path="data/interim/sponsor_register_filtered.csv",
    out_dir="data/processed",
    config=config,
)
run_transform_score(
    enriched_path="data/processed/companies_house_enriched.csv",
    out_dir="data/processed",
    config=config,
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

# Full quality gate run (format → typecheck → lint → test → coverage)
uv run check
```

`uv run lint` is the single lint entry point. It currently runs ruff; import‑linter will be added here as part of the refactor plan.

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

## Output Files

When running Transform Enrich with `--no-resume`, outputs are written under a timestamped
subdirectory of `data/processed/` (paths below reflect the default `--resume` behaviour).

| File                                                 | Description                                   |
| ---------------------------------------------------- | --------------------------------------------- |
| `reports/extract_manifest.json`                       | Download metadata with SHA256 hash            |
| `reports/register_stats.json`                         | Filtering statistics                          |
| `data/raw/*.csv`                                      | Extracted sponsor register CSV                |
| `data/interim/sponsor_register_filtered.csv`          | Filtered and aggregated sponsor register      |
| `data/processed/companies_house_enriched.csv`         | Matched companies with CH data                |
| `data/processed/companies_house_unmatched.csv`        | Orgs that couldn't be matched                 |
| `data/processed/companies_house_candidates_top3.csv`  | Audit trail: top 3 match candidates per org   |
| `data/processed/companies_house_checkpoint.csv`       | Resume checkpoint of processed orgs           |
| `data/processed/companies_house_resume_report.json`   | Resume report for interrupted or partial runs |
| `data/processed/companies_scored.csv`                 | All companies with scores                     |
| `data/processed/companies_shortlist.csv`              | Filtered shortlist                            |
| `data/processed/companies_explain.csv`                | Score breakdown for shortlist                 |

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

- **Companies House 401/403**: ensure `CH_API_KEY` is a valid API key and not an OAuth token; Transform Enrich uses Basic Auth with the key as username and a blank password. See `docs/troubleshooting.md`.

## Future Work

- CI/CD workflow to run quality gates automatically.

## Configuration

Set in `.env` or environment variables:

```bash
CH_API_KEY=your_companies_house_api_key
CH_SLEEP_SECONDS=0.5          # Delay between API calls
CH_MAX_RPM=500                # Rate limit (requests per minute)
CH_TIMEOUT_SECONDS=30         # HTTP timeout in seconds
CH_MAX_RETRIES=3              # Retry attempts for transient errors
CH_BACKOFF_FACTOR=0.5         # Exponential backoff factor
CH_BACKOFF_MAX_SECONDS=60     # Max backoff delay
CH_BACKOFF_JITTER_SECONDS=0.1 # Random jitter added to backoff
CH_CIRCUIT_BREAKER_THRESHOLD=5  # Failures before opening breaker
CH_CIRCUIT_BREAKER_TIMEOUT_SECONDS=60  # Seconds before half-open probe
CH_BATCH_SIZE=250             # Organisations per batch (incremental output)
CH_MIN_MATCH_SCORE=0.72       # Minimum score to accept a match
CH_SEARCH_LIMIT=5             # Candidates per search
TECH_SCORE_THRESHOLD=0.55     # Minimum score for shortlist
GEO_FILTER_REGIONS=           # Single region filter (one value only)
GEO_FILTER_POSTCODES=         # Comma-separated postcode prefix filter
```

## Data Sources

- **Sponsor Register**: [GOV.UK Register of Licensed Sponsors](https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers)
- **Companies House**: [Public Data API](https://developer.company-information.service.gov.uk/)

## Security

- Never commit `.env` (it's in `.gitignore`)
- Rotate your Companies House API key if shared
- Cache contains API response data—treat as sensitive
