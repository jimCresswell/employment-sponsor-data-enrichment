# UK Sponsor → Tech Hiring Pipeline (Python 3)

A practical, auditable pipeline to:

1. **Download** the latest UK Home Office *Register of licensed sponsors: workers* (CSV)
2. **Stage 1**: filter to **Skilled Worker** + **A-rated** and aggregate to unique organisations
3. **Stage 2**: **enrich** organisations using **Companies House** search + company profile
4. **Stage 3**: derive a **tech-likelihood score** using SIC codes + a simple heuristic model
5. Output **shortlists** suitable for recruiting a senior engineer who needs sponsorship

## Why this repo exists

The sponsor register is the best “eligibility filter” available, but it’s noisy for tech hiring.
This pipeline turns it into a structured dataset you can search, slice, and shortlist.

## Quick start (uv recommended)

Install uv (once): https://docs.astral.sh/uv/

```bash
cd uk-sponsor-tech-hiring-pipeline
uv sync
```

Alternatively, with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run the full pipeline

### 1) Download latest sponsor register

```bash
uk-sponsor download
```

This writes to `data/raw/` and also records a manifest in `reports/`.

### 2) Stage 1: Skilled Worker + A-rated + aggregate

```bash
uk-sponsor stage1
```

Output: `data/interim/stage1_skilled_worker_A_rated_aggregated_by_org.csv`

### 3) Stage 2: Companies House enrichment

Set your Companies House API key:

```bash
cp .env.example .env
# edit .env and set CH_API_KEY=...
```

Run enrichment:

```bash
uk-sponsor stage2
```

Outputs:
- `data/processed/stage2_enriched_companies_house.csv`
- `data/processed/stage2_unmatched.csv`
- `data/processed/stage2_candidates_top3.csv`
- cached API responses in `data/cache/companies_house/`

### 4) Stage 3: Tech-likelihood scoring + shortlist

```bash
uk-sponsor stage3
```

Outputs:
- `data/processed/stage3_scored.csv`
- `data/processed/stage3_shortlist_tech.csv` (default threshold + exclusions)

## Notes / design choices

- **Auditable matching**: Stage 2 saves the top 3 search candidates per org with scores.
- **Caching**: Stage 2 caches all responses, so reruns are cheap + rate-limit friendly.
- **Deterministic stages**: Each stage reads explicit inputs and writes explicit outputs.
- **Heuristic model** (Stage 3): intentionally simple; you can swap in a classifier later.

## Data sources

- GOV.UK guidance page for the sponsor register is scraped to find the latest CSV asset.
- Companies House Public Data API is used for enrichment.

## Security

Do not commit `.env`. Rotate API keys if shared.
