# Troubleshooting

This page maps common failures to the fastest safe recovery path.

## 1) Missing Snapshots for Cache-Only Commands

Symptom:

- `run-all` or `transform-enrich` fails because snapshot artefacts are missing.

Recovery:

```bash
uv run uk-sponsor refresh-sponsor
uv run uk-sponsor refresh-companies-house
```

If running staged refresh:

```bash
uv run uk-sponsor refresh-sponsor --only acquire
uv run uk-sponsor refresh-sponsor --only clean
uv run uk-sponsor refresh-companies-house --only acquire
uv run uk-sponsor refresh-companies-house --only clean
```

If you manage paths explicitly, set:

- `SPONSOR_CLEAN_PATH`
- `CH_CLEAN_PATH`
- `CH_TOKEN_INDEX_DIR`

## 2) Unsupported Runtime Source Mode

Symptom:

```text
<command> supports CH_SOURCE_TYPE=file only (got '<value>').
```

Recovery:

1. Set `CH_SOURCE_TYPE=file` in `.env`.
2. Or export it for the current shell:

```bash
export CH_SOURCE_TYPE=file
```

3. Ensure required snapshots exist.
4. Rerun command.

Archived runtime API notes are in `docs/archived-api-runtime-mode.md`.

## 3) Multiple Region Values Rejected

Symptom (CLI):

```text
Only one --region value is supported.
```

Symptom (env parsing):

```text
GEO_FILTER_REGION must contain a single region value.
```

Cause:

- Geographic filtering is intentionally single-region for now.

Recovery:

- Use one `--region` value.
- Set one `GEO_FILTER_REGION` value (no comma-separated list).

## 4) `--only clean` Fails Without Pending Acquire

Symptom:

- Clean command reports no pending acquire snapshot for dataset.

Recovery:

Run acquire first for the same dataset:

```bash
uv run uk-sponsor refresh-sponsor --only acquire
uv run uk-sponsor refresh-sponsor --only clean
```

or

```bash
uv run uk-sponsor refresh-companies-house --only acquire
uv run uk-sponsor refresh-companies-house --only clean
```

## 5) URL Supplied with `--only clean`

Symptom:

```text
--url is not supported with --only clean.
```

Cause:

- `clean` finalises latest pending acquire state and does not use source URL input.

Recovery:

- Remove `--url` when running `--only clean`.
- If needed, run `--only acquire --url <...>` first, then `--only clean`.

## 6) Source Discovery Fails

Symptom:

- Discovery command cannot resolve source URL.

Recovery:

Use explicit URLs:

```bash
uv run uk-sponsor refresh-sponsor --url <sponsor-csv-url>
uv run uk-sponsor refresh-companies-house --url <companies-house-zip-url>
```

Record failure details in your run log so docs can be improved.

## 7) Location Aliases File Missing

Symptom:

- `usage-shortlist` fails when geo filtering is enabled.

Recovery:

1. Ensure `data/reference/location_aliases.json` exists, or
2. Set `LOCATION_ALIASES_PATH` to a valid file.

## 8) Lint and Type Failures During Contribution

Use the quality gates in order:

```bash
uv run format
uv run typecheck
uv run lint
uv run test
uv run coverage
```

Or run all gates:

```bash
uv run check
```

Notes:

- `uv run lint` includes ruff, inline-ignore checks, spelling checks, and import-linter.
- Tests block real network access; use fakes/mocks in tests.

## 9) Snapshot Validation Script Fails

Command:

```bash
uv run python scripts/validation_check_snapshots.py --snapshot-root <path>
```

Common causes:

- Missing required artefacts in latest dated snapshot directory.
- Missing/invalid manifest fields or wrong `schema_version`.
- `clean.csv` missing required contract columns.
- Companies House token/profile partition files missing.

Recovery:

1. Regenerate snapshots with grouped refresh (`--only acquire`, then `--only clean`).
2. Confirm artefacts in the latest dated snapshot directories.
3. Rerun the snapshot validation command.

## 10) Output Validation Script Fails

Command:

```bash
uv run python scripts/validation_check_outputs.py --out-dir <path>
```

Common causes:

- Missing required processed outputs.
- Output CSV headers drifted from contract columns.
- Resume report JSON is malformed or has invalid status values.

Recovery:

1. Rerun runtime steps:

```bash
uv run uk-sponsor transform-enrich
uv run uk-sponsor transform-score
uv run uk-sponsor usage-shortlist
```

2. Re-run the output validation command.

## 11) Fixture E2E Validation Script Fails

Command:

```bash
uv run python scripts/validation_e2e_fixture.py
```

Common causes:

- Local command failure during grouped refresh or runtime flow.
- Fixture contract mismatch with current pipeline rules.
- Port binding issues for the local fixture server.

Recovery:

1. Read the failing command and stderr details emitted by the script.
2. Resolve the underlying contract or command issue.
3. Rerun the script (optionally with `--work-dir` for inspection).

## 12) Still Blocked

Capture:

1. exact command run,
2. full error output,
3. current config values relevant to the failure,
4. any artefact paths involved.

Then open an issue or update the current plan with blocker details and proposed unblock action.

## 13) Enrichment Audit Reports Warnings or Fails in Strict Mode

Command:

```bash
uv run python scripts/validation_audit_enrichment.py --out-dir <path>
```

Strict mode:

```bash
uv run python scripts/validation_audit_enrichment.py --out-dir <path> --strict
```

Common causes:

- too many low-similarity matches,
- too many non-active matched companies,
- too many sponsors sharing one Companies House company number,
- too many unmatched rows with near-threshold candidate scores.

Recovery:

1. Review reported metrics against expected baseline.
2. Sample suspicious rows from `sponsor_enriched.csv` and `sponsor_unmatched.csv`.
3. Tune thresholds for this run or investigate matching logic before accepting outputs.
