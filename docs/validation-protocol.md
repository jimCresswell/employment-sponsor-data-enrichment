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

Durable schema/output and validation contracts are defined in `docs/data-contracts.md`.
This runbook focuses on operational command execution and acceptance checks.

Historical note:
- Older evidence entries may use `uk-sponsor` command examples from sessions before `M8-B1`.

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

If `.env` does not define `CH_SOURCE_TYPE`, set it in your shell before running protocol commands:

```bash
export CH_SOURCE_TYPE=file
```

3. Sync dependencies if needed:

```bash
uv sync --group dev
```

4. Confirm enough disk space for refresh payloads.

## Step 1: Source Discovery

Run:

```bash
uv run uship admin refresh sponsor --only discovery
uv run uship admin refresh companies-house --only discovery
```

Acceptance checks:

- Sponsor command prints one resolved CSV URL.
- Companies House command prints one resolved ZIP URL.
- No snapshot files are created in this step.

If discovery fails, capture the error and continue using explicit `--url` values.

## Step 2: Acquire Raw Payloads

Run:

```bash
uv run uship admin refresh sponsor --only acquire
uv run uship admin refresh companies-house --only acquire
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
uv run uship admin refresh sponsor --only clean
uv run uship admin refresh companies-house --only clean
```

Acceptance checks:

- Dated snapshot directories exist:
  - `data/cache/snapshots/sponsor/<YYYY-MM-DD>/`
  - `data/cache/snapshots/companies_house/<YYYY-MM-DD>/`
  - `data/cache/snapshots/employee_count/<YYYY-MM-DD>/`
- Sponsor artefacts present: `raw.csv`, `clean.csv`, `register_stats.json`, `manifest.json`.
- Companies House artefacts present: `raw.csv`, `clean.csv`, `manifest.json`,
  `index_tokens_<bucket>.csv`, `profiles_<bucket>.csv`.
- Employee-count artefacts present: `raw.csv`, `clean.csv`, `manifest.json`.
- Manifest schema versions:
  - sponsor: `sponsor_clean_v1`
  - companies_house: `ch_clean_v1`
  - employee_count: `employee_count_v1`

## Step 4: Cache-Only Runtime Steps

Run:

```bash
uv run uship admin build enrich
uv run uship admin build score
uv run uship admin build shortlist
```

Acceptance checks:

- Latest `employee_count` snapshot is present and valid before running `admin build score`.
- `admin build enrich` creates:
  - `data/processed/sponsor_enriched.csv`
  - `data/processed/sponsor_unmatched.csv`
  - `data/processed/sponsor_match_candidates_top3.csv`
  - `data/processed/sponsor_enrich_checkpoint.csv`
  - `data/processed/sponsor_enrich_resume_report.json`
- `admin build score` creates:
  - `data/processed/companies_scored.csv`
- `admin build shortlist` creates:
  - `data/processed/companies_shortlist.csv`
  - `data/processed/companies_explain.csv`

## Step 5: Cache-Only Orchestration Sanity Check

Run:

```bash
uv run uship admin build all
```

Acceptance checks:

- CLI reports final shortlist and explain outputs.
- Reported output paths exist.
- No runtime source-mode errors occur.
- If enrich outputs are already complete, `admin build all` may reuse resume state and report
  zero additional processed organisations; this is expected.

## Step 6: Run Validation Scripts

Validate snapshot and processed artefact contracts with dedicated scripts:

```bash
uv run python scripts/validation_check_snapshots.py --snapshot-root data/cache/snapshots
uv run python scripts/validation_check_outputs.py --out-dir data/processed
uv run python scripts/validation_audit_enrichment.py --out-dir data/processed
```

Expected behaviour:

- Exit code `0` with `PASS ...` output when validation succeeds.
- Non-zero exit with `FAIL ...` output when any required artefact, field, or column check fails.
- Snapshot validation covers `sponsor`, `companies_house`, and `employee_count`.
- Enrichment audit prints key matching quality metrics and exits `0` by default.
- Enrichment audit exit codes are:
  - `1` for structural/data-contract failures.
  - `2` for warning-threshold breaches in `--strict` mode.
- Use `--strict` on enrichment audit to fail non-zero when warning thresholds are exceeded.

Run fixture-driven e2e CLI validation (outside pytest):

```bash
uv run python scripts/validation_e2e_fixture.py
```

Expected behaviour:

- Script builds local fixtures, serves them on a local HTTP server, executes grouped refresh once,
  then runs `admin build enrich --no-resume` twice on unchanged snapshots.
- Script verifies deterministic enrich contracts by asserting byte-identical outputs for:
  - `sponsor_enriched.csv`
  - `sponsor_unmatched.csv`
  - `sponsor_match_candidates_top3.csv`
  - `sponsor_enrich_checkpoint.csv`
- Script reruns `admin build enrich --resume` against the second no-resume output and verifies
  resume completion invariants (`status=complete`, `processed_in_run=0`, `remaining=0`).
- Script then runs `admin build score` and `admin build shortlist` on the validated second-run outputs,
  validates required output contracts, and exits `0` on success.
- On failure, script exits non-zero with the failing command or contract violation in stderr.

## Optional: Filter Validation

Validate single-region and postcode filtering behaviour:

```bash
uv run uship admin build shortlist --region London
uv run uship admin build shortlist --postcode-prefix EC --postcode-prefix SW
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
Employee count source URL:
Sponsor snapshot date:
Companies House snapshot date:
Employee count snapshot date:
Runtime commands executed:
Output artefact locations:
Observed issues:
Recovery actions:
Result: pass | fail
```

## Recurring Evidence Cadence and Canonical Log Location

Canonical location:

- Append each live validation record as a `Validation Run` block in
  `docs/validation-run-evidence.md`.

Minimum cadence:

1. Weekly (every 7 days) while pipeline-affecting work is active.
1. Immediately after snapshot-date changes used for shared validation baselines.
1. Before merging changes that affect refresh, transform, usage, config precedence, or
   validation contracts/scripts.

Copy-paste weekly evidence command set:

```bash
uv run uship admin build all
uv run python scripts/validation_check_snapshots.py --snapshot-root data/cache/snapshots
uv run python scripts/validation_check_outputs.py --out-dir data/processed
uv run python scripts/validation_audit_enrichment.py --out-dir data/processed --strict
```

Periodic deterministic check (at least monthly, and before release candidates):

```bash
uv run python scripts/validation_e2e_fixture.py
```

## Notes for Contributors

- Keep this protocol aligned with actual CLI behaviour and artefact contracts.
- If you change command semantics, update this file in the same change.
- If you discover manual steps not documented here, treat that as documentation debt.
