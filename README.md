# UK Sponsor → Tech Hiring Pipeline

A data pipeline that transforms the UK Home Office sponsor register into a shortlist of tech companies likely to hire senior engineers who need visa sponsorship.

## Pipeline Overview

```text
GOV.UK Sponsor Register → Filter → Enrich → Score → Shortlist
       (CSV)             Stage1   Stage2  Stage3   (CSV)
```

| Stage    | Input       | Output                        | What it does                                        |
| -------- | ----------- | ----------------------------- | --------------------------------------------------- |
| download | GOV.UK page | `data/raw/*.csv`              | Scrapes page, downloads CSV, validates schema       |
| stage1   | Raw CSV     | `data/interim/stage1_*.csv`   | Filters Skilled Worker + A-rated, aggregates by org |
| stage2   | Stage1 CSV  | `data/processed/stage2_*.csv` | Enriches via Companies House API                    |
| stage3   | Stage2 CSV  | `data/processed/stage3_*.csv` | Scores for tech-likelihood, outputs shortlist       |

Stages describe artefact boundaries for audit and resume. They are not architectural boundaries; orchestration and shared standards live in the application pipeline (see `docs/architectural-decision-records/adr0012-stages-as-artefact-boundaries.md`).

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
# All stages in sequence
uv run uk-sponsor run-all

# Or run each stage individually:
uv run uk-sponsor download
uv run uk-sponsor stage1
uv run uk-sponsor stage2
uv run uk-sponsor stage3
```

`uv run <command>` executes tools inside the project environment.

### Stage 2 Batching and Resume

Stage 2 runs in batches by default using `CH_BATCH_SIZE`. You can control which batches run:

```bash
# Run only the first 2 batches (after resume filtering)
uv run uk-sponsor stage2 --batch-count 2

# Start at batch 3 and run 2 batches
uv run uk-sponsor stage2 --batch-start 3 --batch-count 2

# Override batch size for this run
uv run uk-sponsor stage2 --batch-size 50
```

Resume data is written to `data/processed/stage2_checkpoint.csv` and
`data/processed/stage2_resume_report.json` (includes overall batch range and timing).

Stage 2 fails fast on authentication, rate limit, circuit breaker, or unexpected HTTP errors. Fix the issue and rerun with `--resume`; the resume report includes a ready‑made command.

When running with `--no-resume`, Stage 2 writes to a new timestamped subdirectory under the output directory to avoid stale data reuse.

### Geographic Filtering

Filter the final shortlist by region or postcode (single region only):

```bash
# Filter to London companies only
uv run uk-sponsor stage3 --region London

# Single region only
uv run uk-sponsor stage3 --region London

# Postcode prefix filtering
uv run uk-sponsor stage3 --postcode-prefix EC --postcode-prefix SW

# Adjust score threshold (default: 0.55)
uv run uk-sponsor stage3 --threshold 0.40

# Full pipeline with filters
uv run uk-sponsor run-all --region London --threshold 0.50
```

## Architecture

### Architecture Direction

The long‑term direction is an application‑owned pipeline: orchestration and step ownership live in an application layer, domain logic is pure and infrastructure is shared and injected. Staged CSVs remain as artefact boundaries for audit and resume, while `stages/` (if retained) becomes a thin delegate layer only.

Observability is standardised via a shared logger factory with UTC timestamps so pipeline logs remain consistent across stages.

### Project Structure

```text
src/uk_sponsor_pipeline/
├── cli.py              # Typer CLI entry point
├── config.py           # Pipeline configuration
├── io_contracts.py     # IO boundary contracts for infrastructure
├── protocols.py        # Interface-style contracts
├── application/        # Use-case orchestration
│   ├── download.py
│   ├── stage1.py
│   ├── stage2_companies_house.py
│   └── stage3_scoring.py
├── infrastructure/     # Concrete implementations (DI pattern)
│   ├── io/
│   │   ├── filesystem.py
│   │   ├── http.py
│   │   └── validation.py
│   └── resilience.py
├── domain/
│   ├── companies_house.py
│   ├── organisation_identity.py
│   ├── scoring.py
│   └── sponsor_register.py
├── observability/      # Shared logging helpers
├── schemas.py          # Column contracts per stage
└── stages/
    ├── download.py
    ├── stage1.py
    ├── stage2_companies_house.py
    └── stage3_scoring.py

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

The current `stages/` modules implement pipeline steps, but the architectural direction is to move orchestration into an application layer with shared infrastructure and keep `stages/` as thin delegates (or remove it entirely). Track this in `/.agent/plans/refactor-plan.md`.

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

Stage entry points require a `PipelineConfig` instance; environment variables are read once at the CLI entry point and passed through. For programmatic use:

```python
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.stages.stage2_companies_house import run_stage2
from uk_sponsor_pipeline.stages.stage3_scoring import run_stage3

config = PipelineConfig.from_env()
run_stage2(stage1_path="data/interim/stage1.csv", out_dir="data/processed", config=config)
run_stage3(stage2_path="data/processed/stage2_enriched_companies_house.csv", out_dir="data/processed", config=config)
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

## Scoring Model (Stage 3)

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

When running Stage 2 with `--no-resume`, outputs are written under a timestamped
subdirectory of `data/processed/` (paths below reflect the default `--resume` behaviour).

| File                                                 | Description                                   |
| ---------------------------------------------------- | --------------------------------------------- |
| `reports/download_manifest.json`                     | Download metadata with SHA256 hash            |
| `reports/stage1_stats.json`                          | Filtering statistics                          |
| `data/processed/stage2_enriched_companies_house.csv` | Matched companies with CH data                |
| `data/processed/stage2_unmatched.csv`                | Orgs that couldn't be matched                 |
| `data/processed/stage2_candidates_top3.csv`          | Audit trail: top 3 match candidates per org   |
| `data/processed/stage2_checkpoint.csv`               | Resume checkpoint of processed orgs           |
| `data/processed/stage2_resume_report.json`           | Resume report for interrupted or partial runs |
| `data/processed/stage3_scored.csv`                   | All companies with scores                     |
| `data/processed/stage3_shortlist_tech.csv`           | Filtered shortlist                            |
| `data/processed/stage3_explain.csv`                  | Score breakdown for shortlist                 |

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

- **Companies House 401/403**: ensure `CH_API_KEY` is a valid API key and not an OAuth token; Stage 2 uses Basic Auth with the key as username and a blank password. See `docs/troubleshooting.md`.

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
