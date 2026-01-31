# UK Sponsor → Tech Hiring Pipeline

A data pipeline that transforms the UK Home Office sponsor register into a shortlist of tech companies likely to hire senior engineers who need visa sponsorship.

## Pipeline Overview

```
GOV.UK Sponsor Register → Filter → Enrich → Score → Shortlist
       (CSV)             Stage1   Stage2  Stage3   (CSV)
```

| Stage | Input | Output | What it does |
|-------|-------|--------|--------------|
| download | GOV.UK page | `data/raw/*.csv` | Scrapes page, downloads CSV, validates schema |
| stage1 | Raw CSV | `data/interim/stage1_*.csv` | Filters Skilled Worker + A-rated, aggregates by org |
| stage2 | Stage1 CSV | `data/processed/stage2_*.csv` | Enriches via Companies House API |
| stage3 | Stage2 CSV | `data/processed/stage3_*.csv` | Scores for tech-likelihood, outputs shortlist |

## Quick Start

### Prerequisites

- Python 3.11+
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
uv sync --extra dev

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

### Geographic Filtering

Filter the final shortlist by region or postcode:

```bash
# Filter to London companies only
uv run uk-sponsor stage3 --region London

# Multiple regions
uv run uk-sponsor stage3 --region London --region Manchester --region Bristol

# Postcode prefix filtering
uv run uk-sponsor stage3 --postcode-prefix EC --postcode-prefix SW

# Adjust score threshold (default: 0.55)
uv run uk-sponsor stage3 --threshold 0.40

# Full pipeline with filters
uv run uk-sponsor run-all --region London --threshold 0.50
```

## Architecture (for TypeScript developers)

### Project Structure

```
src/uk_sponsor_pipeline/
├── cli.py              # Typer CLI (like Commander.js)
├── config.py           # PipelineConfig dataclass (like a typed config object)
├── protocols.py        # Protocol definitions (like TypeScript interfaces)
├── infrastructure.py   # Concrete implementations (DI pattern)
├── normalization.py    # Org name processing utilities
├── schemas.py          # Column contracts per stage
└── stages/
    ├── download.py
    ├── stage1.py
    ├── stage2_companies_house.py
    └── stage3_scoring.py

tests/
├── conftest.py         # Pytest fixtures (like beforeEach + factories)
├── test_normalization.py
└── test_stage3.py
```

### Key Patterns

| Python Pattern | TypeScript Equivalent |
|----------------|----------------------|
| `Protocol` class | `interface` |
| `@dataclass` | `class` with typed properties |
| `Optional[T]` | `T \| undefined` |
| `dict[str, Any]` | `Record<string, unknown>` |
| `list[str]` | `string[]` |
| Type hints | Same purpose as TS types |

### Dependency Injection

We use Python's `Protocol` (similar to TS interfaces) for testability:

```python
# protocols.py - defines the interface
class HttpClient(Protocol):
    def get_json(self, url: str, cache_key: str) -> dict[str, Any]: ...

# infrastructure.py - production implementation
class CachedHttpClient:
    def get_json(self, url: str, cache_key: str) -> dict[str, Any]:
        # Real HTTP + caching logic

# conftest.py - test implementation
class FakeHttpClient:
    def get_json(self, url: str, cache_key: str) -> dict[str, Any]:
        return self.responses.get(cache_key, {})
```

### Running Tests

```bash
# All tests
uv run test

# Verbose output
uv run test -v

# Specific test file
uv run test tests/test_normalization.py

# Specific test class
uv run test tests/test_stage3.py::TestScoreFromSic

# With coverage
uv run coverage
```

### Developer Scripts (uv-backed)

```bash
# Lint
uv run lint

# Format
uv run format

# Format check (CI style)
uv run format-check

# Type check
uv run typecheck
```

## Scoring Model (Stage 3)

Companies are scored on multiple features:

| Feature | Weight Range | Source |
|---------|-------------|--------|
| SIC tech codes | 0.0–0.50 | Companies House profile |
| Active status | 0.0 or 0.10 | Companies House profile |
| Company age | 0.0–0.15 | Date of creation |
| Company type | 0.0–0.10 | Ltd, PLC, LLP, etc. |
| Name keywords | -0.10 to 0.15 | "software", "digital" vs "care", "recruitment" |

**Role-fit buckets:**

- **strong** (≥0.55): High probability tech company
- **possible** (≥0.35): Worth investigating
- **unlikely** (<0.35): Probably not tech

## Output Files

| File | Description |
|------|-------------|
| `reports/download_manifest.json` | Download metadata with SHA256 hash |
| `reports/stage1_stats.json` | Filtering statistics |
| `data/processed/stage2_enriched_companies_house.csv` | Matched companies with CH data |
| `data/processed/stage2_unmatched.csv` | Orgs that couldn't be matched |
| `data/processed/stage2_candidates_top3.csv` | Audit trail: top 3 match candidates per org |
| `data/processed/stage3_scored.csv` | All companies with scores |
| `data/processed/stage3_shortlist_tech.csv` | Filtered shortlist |
| `data/processed/stage3_explain.csv` | Score breakdown for shortlist |

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
CH_MIN_MATCH_SCORE=0.72       # Minimum score to accept a match
CH_SEARCH_LIMIT=5             # Candidates per search
TECH_SCORE_THRESHOLD=0.55     # Minimum score for shortlist
GEO_FILTER_REGIONS=           # Comma-separated region filter
GEO_FILTER_POSTCODES=         # Comma-separated postcode prefix filter
```

## Data Sources

- **Sponsor Register**: [GOV.UK Register of Licensed Sponsors](https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers)
- **Companies House**: [Public Data API](https://developer.company-information.service.gov.uk/)

## Security

- Never commit `.env` (it's in `.gitignore`)
- Rotate your Companies House API key if shared
- Cache contains API response data—treat as sensitive
