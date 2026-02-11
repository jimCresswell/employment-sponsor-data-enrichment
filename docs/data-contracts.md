# Data Contracts

This document records durable data contracts for the pipeline. It is the canonical
reference for schema definitions that must remain stable across runs and between
refresh and usage steps.

## Companies House Raw CSV (Trimmed Headers)

The Companies House Free Data Product CSV includes leading spaces in the header row.
Always `strip()` header names before validation or comparison. Missing required columns
are errors.

Trimmed raw header list (in order):

```text
CompanyName
CompanyNumber
RegAddress.CareOf
RegAddress.POBox
RegAddress.AddressLine1
RegAddress.AddressLine2
RegAddress.PostTown
RegAddress.County
RegAddress.Country
RegAddress.PostCode
CompanyCategory
CompanyStatus
CountryOfOrigin
DissolutionDate
IncorporationDate
Accounts.AccountRefDay
Accounts.AccountRefMonth
Accounts.NextDueDate
Accounts.LastMadeUpDate
Accounts.AccountCategory
Returns.NextDueDate
Returns.LastMadeUpDate
Mortgages.NumMortCharges
Mortgages.NumMortOutstanding
Mortgages.NumMortPartSatisfied
Mortgages.NumMortSatisfied
SICCode.SicText_1
SICCode.SicText_2
SICCode.SicText_3
SICCode.SicText_4
LimitedPartnerships.NumGenPartners
LimitedPartnerships.NumLimPartners
URI
PreviousName_1.CONDATE
PreviousName_1.CompanyName
PreviousName_2.CONDATE
PreviousName_2.CompanyName
PreviousName_3.CONDATE
PreviousName_3.CompanyName
PreviousName_4.CONDATE
PreviousName_4.CompanyName
PreviousName_5.CONDATE
PreviousName_5.CompanyName
PreviousName_6.CONDATE
PreviousName_6.CompanyName
PreviousName_7.CONDATE
PreviousName_7.CompanyName
PreviousName_8.CONDATE
PreviousName_8.CompanyName
PreviousName_9.CONDATE
PreviousName_9.CompanyName
PreviousName_10.CONDATE
PreviousName_10.CompanyName
ConfStmtNextDueDate
ConfStmtLastMadeUpDate
```

## Companies House Canonical Clean Schema (ch_clean_v1)

Canonical columns (CSV, in order):

```text
company_number
company_name
company_status
company_type
date_of_creation
sic_codes
address_locality
address_region
address_postcode
uri
```

### Normalisation Rules

- `company_number`: preserve exactly as supplied, including prefixes and zero padding.
- `company_name`: trim only.
- `company_status`: lower-case.
- `company_type`: slugify `CompanyCategory`.
  - Lower-case, replace any non-alphanumeric with space, collapse whitespace to single
    hyphen, collapse repeated hyphens, trim leading/trailing hyphens.
- `date_of_creation`: parse `IncorporationDate` into ISO `YYYY-MM-DD`.
  - accepted incoming forms are ISO (`YYYY-MM-DD`) and slash format (`DD/MM/YYYY`).
- `sic_codes`: extract code prefixes from `SICCode.SicText_1..4` by splitting on `" - "`,
  then join with `;`.
- Address fields are trimmed only (no additional normalisation).
- `uri`: must be an absolute URL whose path ends with `/company/{CompanyNumber}`.
  - host/path variants are accepted as long as the company-number path match holds.

### Raw → Canonical Mapping

| Canonical field | Raw header | Rule |
| --- | --- | --- |
| `company_number` | `CompanyNumber` | Preserve exactly. |
| `company_name` | `CompanyName` | Trim only. |
| `company_status` | `CompanyStatus` | Lower-case. |
| `company_type` | `CompanyCategory` | Slugify. |
| `date_of_creation` | `IncorporationDate` | Parse to ISO date. |
| `sic_codes` | `SICCode.SicText_1..4` | Extract code prefixes; join with `;`. |
| `address_locality` | `RegAddress.PostTown` | Trim only. |
| `address_region` | `RegAddress.County` | Trim only. |
| `address_postcode` | `RegAddress.PostCode` | Trim only. |
| `uri` | `URI` | Validate absolute URL with `/company/{CompanyNumber}` suffix. |

## Versioning Policy

- `schema_version` is recorded in snapshot manifests.
- Bump `ch_clean_v1` only when canonical columns or normalisation rules change.
- Raw CSV headers are treated as a strict contract; missing columns are errors.

## Snapshot Validation Contract

`scripts/validation_check_snapshots.py` and `validation_snapshots` enforce these contracts:

- required snapshot datasets:
  - `sponsor`
  - `companies_house`
- required artefacts in latest dated snapshot:
  - sponsor: `raw.csv`, `clean.csv`, `register_stats.json`, `manifest.json`
  - companies_house: `raw.csv`, `clean.csv`, `manifest.json`, plus at least one
    `index_tokens_<bucket>.csv` and one `profiles_<bucket>.csv`
- required manifest fields:
  - `dataset`, `snapshot_date`, `source_url`, `downloaded_at_utc`, `last_updated_at_utc`,
    `schema_version`, `sha256_hash_raw`, `sha256_hash_clean`, `bytes_raw`, `row_counts`,
    `artefacts`, `git_sha`, `tool_version`, `command_line`
- required manifest `artefacts` keys:
  - sponsor: `raw`, `clean`, `register_stats`, `manifest`
  - companies_house: `raw`, `clean`
  - note: companies-house manifests do not require `artefacts.manifest`

## Transform Enrich Output Partition Contract

For a completed `transform-enrich` run:

- matched organisations are written to `sponsor_enriched.csv`,
- non-matched organisations are written to `sponsor_unmatched.csv`,
- each organisation name appears in at most one of those two files,
- output ordering is deterministic (`Organisation Name` sort in finalised outputs),
- checkpoint ordering is deterministic (`Organisation Name` sort).

Validation and enforcement:

- `scripts/validation_audit_enrichment.py` enforces structural partition checks.
- `scripts/validation_e2e_fixture.py` enforces deterministic rerun checks.

## Scoring Profile Catalogue Contract

`transform-score` is profile-driven and resolves one active profile per run using:

1. profile catalogue path:
   - CLI `--sector-profile` or env `SECTOR_PROFILE` when supplied,
   - otherwise default `data/reference/scoring_profiles.json`.
1. profile name:
   - CLI `--sector` or env `SECTOR_NAME` when supplied,
   - otherwise the catalogue `default_profile`.

Catalogue requirements:

- JSON schema version must be `1`.
- `default_profile` must reference an existing profile in `profiles`.
- Profile names must be unique.
- Starter profiles in `data/reference/scoring_profiles.json` are currently `tech` (default) and
  `care_support`.
- All scoring fields are strict and validated fail-fast (missing fields, unknown keys,
  wrong types, or invalid ranges are errors).

Runtime scoring requirements:

- The resolved profile drives feature values and bucket thresholds for all rows in the run.
- Scoring output column names and artefact paths remain unchanged.
- Given identical input rows and the same resolved profile, score outputs are deterministic.

Example selection:

```bash
uv run uk-sponsor transform-score --sector care_support
```

## Enrichment Audit CLI Contract

Command:

```bash
uv run python scripts/validation_audit_enrichment.py --out-dir <path>
```

Exit codes:

- `0`: pass (and warnings only when not using `--strict`),
- `1`: structural/data-contract failure,
- `2`: threshold breach in `--strict` mode.

Structural failures (exit `1`) include:

- duplicate organisations in enriched output,
- duplicate organisations in unmatched output,
- overlap between enriched and unmatched organisation sets,
- missing key enriched fields (`ch_company_number`, `ch_company_name`,
  `match_score`, `score_name_similarity`),
- invalid numeric fields in audit-required columns.

## Fixture E2E Deterministic Rerun Contract

Command:

```bash
uv run python scripts/validation_e2e_fixture.py
```

The script contract is:

1. Run grouped refresh once on local fixtures.
2. Run `transform-enrich --no-resume` twice on unchanged snapshots.
3. Assert byte-identical output for:
   - `sponsor_enriched.csv`
   - `sponsor_unmatched.csv`
   - `sponsor_match_candidates_top3.csv`
   - `sponsor_enrich_checkpoint.csv`
4. Run `transform-enrich --resume` against the second no-resume output.
5. Assert resume invariants:
   - `status=complete`
   - `processed_in_run=0`
   - `remaining=0`
6. Run `transform-score` and `usage-shortlist` on the validated second-run output.
