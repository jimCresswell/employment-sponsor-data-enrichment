# Validation Protocol (File-First Runtime)

This runbook validates the pipeline end to end in the supported runtime mode:
`CH_SOURCE_TYPE=file`.

It is intended for:

- maintainers validating a release candidate,
- contributors verifying behaviour after significant changes,
- operators needing an auditable, repeatable process.

## Scope

In scope:

- refresh discovery/acquire/clean behaviour,
- snapshot artefact and schema checks,
- cache-only pipeline execution and output checks.

Out of scope:

- runtime API mode validation (archived reference only),
- non-reproducible/manual transformations outside pipeline commands.

## Pre-Flight Checklist

1. Confirm tooling:

```bash
uv --version
uv run python --version
```

2. Confirm configuration is file-first:

```bash
grep '^CH_SOURCE_TYPE=' .env
```

Expected value: `CH_SOURCE_TYPE=file`.

3. Sync dependencies if needed:

```bash
uv sync --group dev
```

4. Confirm enough disk space for refresh payloads.

## Step 1: Source Discovery

Run:

```bash
uv run uk-sponsor refresh-sponsor --only discovery
uv run uk-sponsor refresh-companies-house --only discovery
```

Acceptance checks:

- Sponsor command prints one resolved CSV URL.
- Companies House command prints one resolved ZIP URL.
- No snapshot files are created in this step.

If discovery fails, capture the error and continue using explicit `--url` values.

## Step 2: Acquire Raw Payloads

Run:

```bash
uv run uk-sponsor refresh-sponsor --only acquire
uv run uk-sponsor refresh-companies-house --only acquire
```

Acceptance checks:

- Sponsor pending staging directory exists under:
  `data/cache/snapshots/sponsor/.tmp-<uuid>/`
- Companies House pending staging directory exists under:
  `data/cache/snapshots/companies_house/.tmp-<uuid>/`
- Sponsor staging includes `raw.csv` and `pending.json`.
- Companies House staging includes `pending.json` and raw artefacts
  (`raw.zip` plus extracted `raw.csv` for ZIP sources).

## Step 3: Clean and Commit Snapshots

Run:

```bash
uv run uk-sponsor refresh-sponsor --only clean
uv run uk-sponsor refresh-companies-house --only clean
```

Acceptance checks:

- Dated snapshot directories exist:
  - `data/cache/snapshots/sponsor/<YYYY-MM-DD>/`
  - `data/cache/snapshots/companies_house/<YYYY-MM-DD>/`
- Sponsor artefacts present: `raw.csv`, `clean.csv`, `register_stats.json`, `manifest.json`.
- Companies House artefacts present: `raw.csv`, `clean.csv`, `manifest.json`,
  `index_tokens_<bucket>.csv`, `profiles_<bucket>.csv`.
- Manifest schema versions:
  - sponsor: `sponsor_clean_v1`
  - companies_house: `ch_clean_v1`

## Step 4: Cache-Only Runtime Steps

Run:

```bash
uv run uk-sponsor transform-enrich
uv run uk-sponsor transform-score
uv run uk-sponsor usage-shortlist
```

Acceptance checks:

- `transform-enrich` creates:
  - `data/processed/companies_house_enriched.csv`
  - `data/processed/companies_house_unmatched.csv`
  - `data/processed/companies_house_candidates_top3.csv`
  - `data/processed/companies_house_checkpoint.csv`
  - `data/processed/companies_house_resume_report.json`
- `transform-score` creates:
  - `data/processed/companies_scored.csv`
- `usage-shortlist` creates:
  - `data/processed/companies_shortlist.csv`
  - `data/processed/companies_explain.csv`

## Step 5: Cache-Only Orchestration Sanity Check

Run:

```bash
uv run uk-sponsor run-all
```

Acceptance checks:

- CLI reports final shortlist and explain outputs.
- Reported output paths exist.
- No runtime source-mode errors occur.

## Step 6: Run Validation Scripts

Validate snapshot and processed artefact contracts with dedicated scripts:

```bash
uv run python scripts/validation_check_snapshots.py --snapshot-root data/cache/snapshots
uv run python scripts/validation_check_outputs.py --out-dir data/processed
```

Expected behaviour:

- Exit code `0` with `PASS ...` output when validation succeeds.
- Non-zero exit with `FAIL ...` output when any required artefact, field, or column check fails.

Run fixture-driven e2e CLI validation (outside pytest):

```bash
uv run python scripts/validation_e2e_fixture.py
```

Expected behaviour:

- Script builds local fixtures, serves them on a local HTTP server, executes grouped refresh and
  runtime steps, validates required output contracts, and exits `0` on success.
- On failure, script exits non-zero with the failing command or contract violation in stderr.

## Optional: Filter Validation

Validate single-region and postcode filtering behaviour:

```bash
uv run uk-sponsor usage-shortlist --region London
uv run uk-sponsor usage-shortlist --postcode-prefix EC --postcode-prefix SW
```

Expected:

- Region command accepts a single region value.
- Postcode filtering accepts repeated prefixes.

## Failure Handling Rules

- Do not patch files manually to “fix” outputs.
- If refresh staging is incomplete, rerun acquire and clean.
- If runtime fails on missing artefacts, repair snapshots first.
- Record errors and remediation in run logs for audit continuity.
- If a validation script fails, fix the underlying artefact/contract issue and rerun the script.

See `docs/troubleshooting.md` for concrete error-to-recovery mappings.

## Post-Run Quality Gates

If code or docs changed during validation:

```bash
uv run check
```

## Auditable Run Log Template

Use this template for every validation run:

```text
Validation Run
Date:
Operator:
Environment:
CH_SOURCE_TYPE:
Sponsor CSV URL:
Companies House ZIP URL:
Sponsor snapshot date:
Companies House snapshot date:
Runtime commands executed:
Output artefact locations:
Observed issues:
Recovery actions:
Result: pass | fail
```

## Notes for Contributors

- Keep this protocol aligned with actual CLI behaviour and artefact contracts.
- If you change command semantics, update this file in the same change.
- If you discover manual steps not documented here, treat that as documentation debt.
