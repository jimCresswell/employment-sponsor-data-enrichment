# Project Definition: UK Sponsor → Tech Hiring Pipeline

## Purpose

Build a reproducible, auditable data pipeline that turns the UK Home Office sponsor register into a high-signal shortlist of companies likely to hire a senior engineer (React Native/Front-end heavy, some iOS, Node, some back-end) who requires UK visa sponsorship.

The pipeline must:

- Be mechanically reproducible end-to-end
- Produce intermediate artefacts for auditability
- Be robust to dataset changes (new CSV filenames, schema drift)
- Be pragmatic and “data science standard”: staged outputs, caching, thresholds, basic evaluation

## Primary User Journey

1. Run `uk-sponsor download` → pulls latest sponsor CSV from GOV.UK
2. Run `uk-sponsor stage1` → yields sponsor-eligible companies for Skilled Worker route
3. Run `uk-sponsor stage2` → enriches sponsors via Companies House (SIC, status, basic address)
4. Run `uk-sponsor stage3` → computes tech-likelihood score + outputs a shortlist CSV
5. Human uses shortlist for sourcing: targeted outreach, job board filtering, and recruiter briefings

## What We Have (Delivered Bundle)

Repo (zipped) with a working skeleton and these stages:

### Repo Structure

- `pyproject.toml` (modern package config)
- `src/uk_sponsor_pipeline/`
  - `cli.py` (Typer CLI): `download`, `stage1`, `stage2`, `stage3`
  - `stages/download.py` (scrapes GOV.UK guidance page; downloads latest CSV asset)
  - `stages/stage1.py` (filters Skilled Worker + A-rated; aggregates by org name)
  - `stages/stage2_companies_house.py` (Companies House enrichment via search→score→profile; caching)
  - `stages/stage3_scoring.py` (heuristic tech scoring from SIC codes; shortlist export)
  - `utils/http.py` (disk cache + JSON GET helper with 429 backoff)
- `.env.example` (CH_API_KEY + thresholds)
- `tests/` (minimal tests for Stage 3 SIC parsing/scoring)
- `CITATIONS.md` (source URLs)
- `data/` scaffolding: raw / interim / processed / cache

### Stage Contracts (Current)

- **download**
  - Input: none
  - Output: `data/raw/<downloaded csv>`
  - Manifest: `reports/download_manifest.json`
- **stage1**
  - Input: latest CSV in `data/raw/*.csv`
  - Output: `data/interim/stage1_skilled_worker_A_rated_aggregated_by_org.csv`
- **stage2**
  - Input: stage1 output
  - Output:
    - `data/processed/stage2_enriched_companies_house.csv`
    - `data/processed/stage2_unmatched.csv`
    - `data/processed/stage2_candidates_top3.csv`
    - cache: `data/cache/companies_house/*.json`
- **stage3**
  - Input: stage2 enriched output
  - Output:
    - `data/processed/stage3_scored.csv`
    - `data/processed/stage3_shortlist_tech.csv`

## What We Still Need to Build (Required Enhancements)

The current pipeline is functional but will produce a shortlist that is still too broad/noisy. The goal is to make it “high-signal for hiring senior RN/FE/iOS/Node”.

### 1) Improve Robustness of Download Stage

Problem: GOV.UK page structure can change, multiple CSVs may exist, and “first link” may not always be latest.

Build:

- More reliable attachment selection:
  - Prefer link text containing “Worker and Temporary Worker” or similar
  - Or parse GOV.UK attachment metadata if available
- Verify CSV schema after download (columns present)
- Include file hash (sha256) in manifest
- Add `uk-sponsor download --url <csv>` override for pinned runs
- Add retry + streaming download (large files)

Acceptance:

- Download stage consistently finds and fetches the correct CSV, or fails with actionable error.

### 2) Stage 1: Better Canonicalisation + Output Shape

Problem: Organisation names may have trading names, punctuation, differing suffixes. Aggregation by raw name can under/over merge.

Build:

- Add columns:
  - `org_name_raw`
  - `org_name_normalized` (for later matching + dedupe)
- Option to aggregate by normalized name (but keep raw list)
- Preserve route/rating columns as structured values (still as strings is ok, but deterministic)
- Add a Stage 1 stats report (JSON) in `reports/`:
  - counts, duplicates, top towns, etc.

Acceptance:

- Stage 1 output supports deterministic matching and later diagnostics.

### 3) Stage 2: Matching Quality + Resume + Safety

Problem: Companies House matching is hard (trading names, trusts, universities, branches, “T/A”, punctuation). Also the run may take a long time; must be resumable and rate-limit safe.

Build:

- Better name preprocessing:
  - Remove “T/A”, “trading as”, bracketed suffixes
  - Split on “ - ”, “ / ”, “,” for candidates
- Multi-query strategy:
  - Try original name → if low score, try stripped/alternate name(s)
- Add “match_reason” signals:
  - name similarity component
  - locality match
  - status bonus
- Implement robust resume:
  - write outputs incrementally (append mode) or store a checkpoint state
  - skip orgs already enriched in output (idempotent)
- Rate limit controls:
  - configurable RPM budget
  - exponential backoff on 429
- Improve caching keying (avoid collisions from minor whitespace differences)
- Expand stored enrichment fields:
  - company type, status, incorporation date already
  - optionally: `accounts` summary (if present), `has_insolvency_history` etc (if needed)
- Add confidence bands:
  - `match_confidence = high|medium|low` based on score thresholds
- Ensure failures are explicit and non-fatal:
  - keep going; output error reason per org

Acceptance:

- Stage 2 can run overnight, can resume after interruption, and produces high-quality matches with audit trail.

### 4) Stage 3: Tech-Likelihood Model Upgrade

Problem: SIC heuristics are crude. We need to narrow to “likely to hire the candidate profile”.

Build:

- Replace single heuristic with a small scoring model composed of interpretable features:
  - `sic_tech_score` (based on SIC codes, but richer mapping)
  - `is_active` (already)
  - `company_age` (years since creation)
  - `company_type_weight` (e.g., ltd vs plc vs charity)
  - `name_keywords` (e.g., “software”, “digital”, “tech”, “consulting”)
  - optionally `postcode_region` mapping (London/hubs may be higher likelihood)
- Provide top-level “role-fit score” (0–1) and bucket labels:
  - `role_fit_bucket = strong|possible|unlikely`
- Provide a default shortlist threshold but make it tunable:
  - `--threshold` CLI option overrides env
- Add “exclusion lists”:
  - configurable denylist for sectors (care homes, construction, hospitality) via SIC prefixes
  - allowlist for known tech SICs and keywords
- Output additional artefacts:
  - `stage3_explain.csv` with per-feature contributions for transparency

Acceptance:

- Stage 3 output is much narrower and explainable (not a black box).

### 5) Stage 4 (New): “Likely Engineering Employer” Enrichment

We need at least one more enrichment layer beyond Companies House to distinguish “sponsors” from “tech employers”.

Two options; build at least one:

Option A (API-light / cheap):

- Use Companies House SIC + name keywords + age + location only
- Result: okay, but still noisy

Option B (recommended; still lightweight):

- For the Stage 3 shortlist only (reduce scale), attempt to enrich:
  - official website domain (Companies House may not provide; fallback via search)
  - presence signals: LinkedIn company page exists? GitHub org exists?
  - careers page exists?
  - (Keep this minimal and cached; avoid full scraping where possible)

Implementation guidance:

- If external search is needed, do it only on the narrowed shortlist to avoid cost/volume.
- Persist “source URL” fields and timestamps for audit.

Acceptance:

- Stage 4 produces a “sourcing-ready” shortlist (hundreds or less, not tens of thousands).

### 6) UX Outputs: Recruiter-Friendly Views

Build:

- Generate a “final shortlist” CSV with columns most useful to a recruiter:
  - org name, town/county, Companies House number, status, SICs, tech score, match confidence
- Optional: produce a simple HTML report or notebook:
  - distributions, top SICs, score histogram, coverage of matched vs unmatched

Acceptance:

- Non-technical stakeholder can use outputs without reading code.

### 7) Testing & Quality

Build:

- Add unit tests for:
  - name normalization and candidate generation
  - match scoring behavior on known examples
  - stage 1 schema validation
- Add a small “golden” test dataset (tiny CSV) checked into `tests/fixtures/`
- Add ruff formatting + lint task instructions in README
- Add CI-ready command list (but do not include GitHub workflows unless asked)

Acceptance:

- Tests run fast; core transformations are verified.

## Non-Goals (Explicit)

- Not building an ATS or CRM.
- Not producing “guaranteed tech stack inference” from public data.
- Not automating outreach; output is for human use.
- Not attempting to predict salary or sponsorship willingness beyond license eligibility.

## Deliverables (What the Coding Agent Should Produce)

1. A clean, runnable Python repo with the enhanced pipeline:
   - robust download
   - better stage 1 canonicalisation
   - stage 2 resumable enrichment + improved matching
   - stage 3 improved role-fit scoring + explainability
   - (optional but preferred) stage 4 lightweight web presence enrichment for final shortlist
2. Clear CLI:
   - `uk-sponsor download`
   - `uk-sponsor stage1`
   - `uk-sponsor stage2`
   - `uk-sponsor stage3`
   - `uk-sponsor stage4` (if implemented)
   - `uk-sponsor run-all` (nice-to-have)
3. Artefacts written to `data/` with stable filenames
4. Reports/metadata in `reports/` with counts + config snapshot
5. Updated README with:
   - setup instructions (uv + pip)
   - stage-by-stage runbook
   - tuning knobs (thresholds, sleep seconds, etc.)
   - interpretation guidance for tech shortlist
6. No secrets committed; `.env` remains ignored.

## Definition of Done

- A new user can:
  1) clone/unzip
  2) install dependencies
  3) set CH_API_KEY
  4) run stages sequentially
  5) get a final shortlist CSV with a clear explanation of why each org is included
- Pipeline is resumable and robust to intermittent API failures
- Outputs are auditable: can trace each shortlist row back to:
  - sponsor register inclusion
  - Companies House match candidates + match score
  - scoring features contributing to selection
