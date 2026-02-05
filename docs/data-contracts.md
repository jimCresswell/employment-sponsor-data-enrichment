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
- `sic_codes`: extract code prefixes from `SICCode.SicText_1..4` by splitting on `" - "`,
  then join with `;`.
- Address fields are trimmed only (no additional normalisation).
- `uri`: must match `http://data.companieshouse.gov.uk/doc/company/{CompanyNumber}`.

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
| `uri` | `URI` | Validate against canonical mapping. |

## Versioning Policy

- `schema_version` is recorded in snapshot manifests.
- Bump `ch_clean_v1` only when canonical columns or normalisation rules change.
- Raw CSV headers are treated as a strict contract; missing columns are errors.
