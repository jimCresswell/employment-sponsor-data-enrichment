# Future Enhancement Plan

> Remaining work and potential improvements for the UK Sponsor Pipeline.

## Priority 1: Immediate Value

### 1.1 Integration Tests

- [ ] Test download with mock HTTP responses
- [ ] Test Stage 1→2→3 with fixture data in `conftest.py`
- [ ] Add pytest markers for slow/integration tests

### 1.2 Error Handling Hardening

- [ ] Graceful handling of GOV.UK page structure changes
- [ ] Better error messages for API rate limits
- [ ] Retry logic for transient network failures

### 1.3 CI/CD Setup

- [ ] GitHub Actions workflow for tests on PR
- [ ] Pre-commit hooks (ruff, mypy)
- [ ] Coverage reporting

---

## Priority 2: Feature Enhancements

### 2.1 Stage 4: Web Presence Scoring

Add signals from web presence to improve tech-likelihood:

```
web_presence_score = f(
    has_linkedin: bool,
    linkedin_employee_count: int,
    has_career_page: bool,
    career_page_tech_keywords: int,
    github_presence: bool,
)
```

**Implementation:**

- [ ] Add `WebPresenceClient` protocol
- [ ] Implement LinkedIn public page check
- [ ] Implement career page scraping with keyword detection
- [ ] Add GitHub org detection
- [ ] Integrate into Stage 3 scoring

### 2.2 Data Validation Pipeline

- [ ] Pydantic models for each stage's input/output
- [ ] Schema versioning for cache invalidation
- [ ] Data quality metrics per stage

### 2.3 Reporting Dashboard

- [ ] HTML report generation with charts
- [ ] Stage funnel visualization
- [ ] Geographic distribution map

---

## Priority 3: Architecture Improvements

### 3.1 Async HTTP Client

Replace synchronous requests with `httpx` async for parallel API calls:

- [ ] Add `AsyncHttpClient` protocol
- [ ] Implement with connection pooling
- [ ] Add concurrent request limit

### 3.2 Persistent State Store

Replace CSV-based resumability with SQLite:

- [ ] Schema for orgs, matches, scores
- [ ] Query interface for filtered exports
- [ ] Migration from existing CSVs

### 3.3 Plugin Architecture

Enable custom scoring plugins:

- [ ] `ScoringPlugin` protocol
- [ ] Plugin discovery and loading
- [ ] User-defined weighting

---

## Implementation Notes

### Key Patterns (for TypeScript devs)

| Python | TypeScript Equivalent |
|--------|----------------------|
| `Protocol` | `interface` |
| `@dataclass` | `class` with properties |
| `Optional[T]` | `T \| undefined` |
| `dict[str, Any]` | `Record<string, unknown>` |
| `pytest fixtures` | Jest `beforeEach` + factory functions |
| `uv sync --extra dev` | `npm install --dev` |

### Running Specific Tests

```bash
# All tests
uv run test

# Specific file
uv run test tests/test_normalization.py -v

# Specific test class
uv run test tests/test_stage3.py::TestScoreFromSic -v

# With coverage
uv run coverage
```
