# Companies House Free Data Product - Raw CSV Headers

This document records the **raw CSV headers as supplied** in the Companies House
Free Data Product (Basic Company Data). These are the *real-world* column names
observed in `BasicCompanyDataAsOneFile-2026-02-01.csv`.

Important: the raw header line contains **leading spaces** on some columns.
**Always trim header names** (`.strip()`) before validation, mapping, or comparison.

This file documents raw headers only. **Canonical/internal headers are a separate
concept** and must be defined explicitly by the pipeline (see the ingest plan).

## Raw CSV Header List (trimmed, in order)

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

## Field Groups (raw header names)

### Company

| Field | Notes |
| --- | --- |
| CompanyName | Current registered name. |
| CompanyNumber | Primary identifier. Preserve exactly as supplied (including prefix and zero padding). |
| CompanyCategory | Legal form (`corporate_body_type_desc`). |
| CompanyStatus | Lifecycle status (`action_code_desc`). |
| CountryOfOrigin | Original registration country. |
| DissolutionDate | Only populated if dissolved. |
| IncorporationDate | Incorporation date. |
| URI | Canonical Companies House URI; must match the deterministic mapping rule. |

### Registered Office Address

| Field | Notes |
| --- | --- |
| RegAddress.CareOf | Optional. |
| RegAddress.POBox | Optional. |
| RegAddress.AddressLine1 | House number and street. |
| RegAddress.AddressLine2 | Area. |
| RegAddress.PostTown | |
| RegAddress.County | Region. |
| RegAddress.Country | |
| RegAddress.PostCode | |

Blank values are valid and common.

### Accounts

| Field | Notes |
| --- | --- |
| Accounts.AccountRefDay | Day of accounting period. |
| Accounts.AccountRefMonth | Month of accounting period. |
| Accounts.NextDueDate | Next filing deadline. |
| Accounts.LastMadeUpDate | Last accounts date. |
| Accounts.AccountCategory | `accounts_type_desc`. |

If no accounts filed, dates may be blank.

### Returns

| Field | Notes |
| --- | --- |
| Returns.NextDueDate | Next return due date (legacy). |
| Returns.LastMadeUpDate | Last made up to date (legacy). |

### Confirmation Statement

| Field | Notes |
| --- | --- |
| ConfStmtNextDueDate | Next confirmation due. |
| ConfStmtLastMadeUpDate | Last made up to date. |

Both Returns and Confirmation Statement fields exist in the raw CSV.

### Mortgages / Charges

| Field | Notes |
| --- | --- |
| Mortgages.NumMortCharges | Total charges. |
| Mortgages.NumMortOutstanding | Outstanding. |
| Mortgages.NumMortPartSatisfied | Part satisfied. |
| Mortgages.NumMortSatisfied | Fully satisfied. |

### SIC Codes (occurs max 4)

| Field | Notes |
| --- | --- |
| SICCode.SicText_1 | Condensed SIC code **plus description** (e.g., `99999 - Dormant Company`). |
| SICCode.SicText_2 | Same as above. |
| SICCode.SicText_3 | Same as above. |
| SICCode.SicText_4 | Same as above. |

Do not assume the value is code-only. If a canonical code list is required,
define explicit parsing rules during cleaning.

### Limited Partnerships (conditional)

| Field | Notes |
| --- | --- |
| LimitedPartnerships.NumGenPartners | Only present for LP-type entities. |
| LimitedPartnerships.NumLimPartners | Only present for LP-type entities. |

### Previous Names (occurs max 10)

The raw CSV includes 10 repeated pairs:

| Field | Notes |
| --- | --- |
| PreviousName_n.CONDATE | Change of name date (n = 1..10). |
| PreviousName_n.CompanyName | Previous company name (n = 1..10). |

If no name changes occurred, these fields are blank.
