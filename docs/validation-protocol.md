# Validation Protocol (File-First)

This protocol validates the pipeline in isolated steps, using file-backed Companies
House data only. It provides objective acceptance checks for each action and includes
an end-to-end fixture run labelled as an e2e test.

## Scope and Assumptions

- `CH_SOURCE_TYPE=file` only. API validation is out of scope.
- Tests remain network-isolated; any network access occurs only during refresh.
- All checks must be reproducible and auditable.
- Fail fast on missing artefacts or schema mismatches.

## Pre-Flight

1. Confirm environment and tooling.
   Use Python 3.14+ and `uv`. Ensure `unzip` is available.
1. Set environment variables for file-first runs.
   Prefer `.env` with `CH_SOURCE_TYPE=file` and snapshot paths as needed.
1. Ensure adequate disk space for large downloads.

## Step 1: Source Discovery and Refresh (Pipeline-Owned)

1. Source pages are constant:
Sponsor register: `https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers`
Companies House bulk data: `https://download.companieshouse.gov.uk/en_output.html`
1. The pipeline refresh commands own link discovery, download, and unzip. Do not
   manually download or unzip sources outside the pipeline.
1. Refresh commands support grouped execution via `--only`:

- `discovery`: resolve the current source URL only
- `acquire`: download raw payload (and extract ZIP for Companies House)
- `clean`: finalise latest pending acquire into the dated snapshot
- `all` (default): run acquire and clean in one command

1. If discovery fails, record the exception and provide `--url` with the direct
   CSV (sponsor) or ZIP (Companies House) URL.

## Step 2: Refresh Sponsor Snapshot

1. Run grouped sponsor refresh validation:

```bash
uv run uk-sponsor refresh-sponsor --only discovery
uv run uk-sponsor refresh-sponsor --only acquire
uv run uk-sponsor refresh-sponsor --only clean
# Optional explicit URL for acquire/all:
uv run uk-sponsor refresh-sponsor --url <SPONSOR_CSV_URL>
```

2. Acceptance checks.

- Discovery prints one resolved CSV URL.
- Acquire creates a pending staging directory under `data/cache/snapshots/sponsor/.tmp-<uuid>/`
  containing `raw.csv` and `pending.json`.
- Clean consumes the latest pending staging directory and commits
  `data/cache/snapshots/sponsor/<YYYY-MM-DD>/`.
- Snapshot directory exists under `data/cache/snapshots/sponsor/<YYYY-MM-DD>/`.
- Artefacts present: `raw.csv`, `clean.csv`, `register_stats.json`, `manifest.json`.
- `manifest.json` includes required fields and `schema_version` is `sponsor_clean_v1`.
- `clean.csv` has required columns from `TRANSFORM_REGISTER_OUTPUT_COLUMNS`.

## Step 3: Refresh Companies House Snapshot

1. Run grouped Companies House refresh validation:

```bash
uv run uk-sponsor refresh-companies-house --only discovery
uv run uk-sponsor refresh-companies-house --only acquire
uv run uk-sponsor refresh-companies-house --only clean
# Optional explicit URL for acquire/all (ZIP):
uv run uk-sponsor refresh-companies-house --url <CH_ZIP_URL>
```

2. Acceptance checks.

- Discovery prints one resolved ZIP URL.
- Acquire creates a pending staging directory under
  `data/cache/snapshots/companies_house/.tmp-<uuid>/` containing `pending.json`
  and raw artefacts (`raw.zip` plus extracted `raw.csv` for ZIP sources).
- Clean consumes the latest pending staging directory and commits
  `data/cache/snapshots/companies_house/<YYYY-MM-DD>/`.
- Snapshot directory exists under `data/cache/snapshots/companies_house/<YYYY-MM-DD>/`.
- Artefacts present: `raw.csv`, `clean.csv`, `manifest.json`, `index_tokens_<bucket>.csv`,
  and `profiles_<bucket>.csv`.
- `manifest.json` includes required fields and `schema_version` is `ch_clean_v1`.
- `clean.csv` headers match `ch_clean_v1` in `docs/data-contracts.md`.
- Index files include headers `token,company_number`.

## Step 4: Transform Enrich (File Source)

1. Ensure `CH_SOURCE_TYPE=file` and snapshot paths are set or resolvable from
   `SNAPSHOT_ROOT`.
1. Run the transform with file source.

```bash
uv run uk-sponsor transform-enrich
```

2. Acceptance checks.

- Outputs created in `data/processed/`:
  `companies_house_enriched.csv`, `companies_house_unmatched.csv`,
  `companies_house_candidates_top3.csv`, `companies_house_checkpoint.csv`,
  `companies_house_resume_report.json`.
- Enriched and unmatched outputs contain all columns from
  `TRANSFORM_ENRICH_OUTPUT_COLUMNS` and `TRANSFORM_ENRICH_UNMATCHED_COLUMNS`.
- Resume report has a `status` of `complete` and non-empty timing fields.

## Step 5: Transform Score

1. Run the scoring step.

```bash
uv run uk-sponsor transform-score
```

2. Acceptance checks.

- Output `data/processed/companies_scored.csv` exists.
- Columns include all `TRANSFORM_SCORE_OUTPUT_COLUMNS`.

## Step 6: Usage Shortlist

1. Run the usage step with default thresholds.

```bash
uv run uk-sponsor usage-shortlist
```

2. Acceptance checks.

- Outputs `data/processed/companies_shortlist.csv` and
  `data/processed/companies_explain.csv` exist.
- Explain output columns match `TRANSFORM_SCORE_EXPLAIN_COLUMNS`.

## Step 7: Full Cache-Only Run (Optional Sanity Pass)

1. Run the cache-only orchestration.

```bash
uv run uk-sponsor run-all
```

2. Acceptance checks.

- Output paths reported by the CLI exist.
- No network calls occur during the run.

## e2e Test: Fixture Run

This run validates correctness on tiny fixtures and must be labelled as e2e.

1. Create minimal fixture CSVs for sponsor and Companies House.
1. Use a local HTTP stub or in-repo fixtures to supply the URLs.
1. Run `refresh-sponsor` and `refresh-companies-house` against the fixture URLs.
1. Run `transform-enrich`, `transform-score`, and `usage-shortlist`.
1. Assert that all outputs exist and contain the expected row counts and column sets.

## Post-Run Quality Gates

After a validation run that changes code or docs, run the full gate sequence:

```bash
uv run check
```

## Run Log Template

Use a short run log for auditability:

```text
Validation Run
Date:
Operator:
Sponsor ZIP URL:
Sponsor CSV URL:
Companies House ZIP/CSV URL:
Snapshot dates:
Artefact locations:
Notes:
```
