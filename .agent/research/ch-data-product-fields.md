# Free Data Product - Data Fields

The bulk download CSV uses a fixed, flat schema. The data in the files will conform to the following specification. Max size values are reproduced from the source.

## Company

| Field | Max size | Notes |
| --- | --- | --- |
| CompanyName | 160 | Current registered name. |
| CompanyNumber | 8 | Primary identifier. Preserve exactly as supplied (including prefix and zero padding). |
| CompanyCategory | 100 | Legal form (`corporate_body_type_desc`). |
| CompanyStatus | 70 | Lifecycle status (`action_code_desc`). |
| CountryofOrigin | 50 | Original registration country. |
| DissolutionDate | 10 | Only populated if dissolved. |
| IncorporationDate | 10 | Incorporation date. |
| URI | 47 | Canonical Companies House URI; must match the deterministic mapping rule. |

## Registered Office Address

| Field | Max size | Notes |
| --- | --- | --- |
| Careof | 100 | Optional. |
| POBox | 10 | Optional. |
| AddressLine1 | 300 | House number and street. |
| AddressLine2 | 300 | Area. |
| PostTown | 50 | |
| County | 50 | Region. |
| Country | 50 | |
| PostCode | 20 | |

Blank values are valid and common.

## Accounts

| Field | Max size | Notes |
| --- | --- | --- |
| AccountingRefDay | 2 | Day of accounting period. |
| AccountingRefMonth | 2 | Month of accounting period. |
| NextDueDate | 10 | Next filing deadline. |
| LastMadeUpDate | 10 | Last accounts date. |
| AccountsCategory | 30 | `accounts_type_desc`. |

If no accounts filed, dates may be blank.

## Confirmation Statement (Returns)

| Field | Max size | Notes |
| --- | --- | --- |
| ConfStmtNextDueDate | 10 | Next confirmation due. |
| ConfStmtLastMadeUpDate | 10 | Last made up to date. |

## Mortgages / Charges

| Field | Max size | Notes |
| --- | --- | --- |
| NumMortCharges | 6 | Total charges. |
| NumMortOutstanding | 6 | Outstanding. |
| NumMortPartSatisfied | 6 | Part satisfied. |
| NumMortSatisfied | 6 | Fully satisfied. |

If all values are blank or zero, no charges exist.

## SIC Codes (occurs max 4)

| Field | Max size | Notes |
| --- | --- | --- |
| SICCode1 | 170 | Condensed Companies House SIC code. |
| SICCode2 | 170 | Condensed Companies House SIC code. |
| SICCode3 | 170 | Condensed Companies House SIC code. |
| SICCode4 | 170 | Condensed Companies House SIC code. |

- Max 4 per company.
- Order is not semantically meaningful.
- Blank values are valid.
- These are condensed Companies House SIC codes (not full ONS SIC hierarchies).

## Limited Partnerships (conditional)

| Field | Max size | Notes |
| --- | --- | --- |
| NumGenPartners | 6 | Only present for LP-type entities. |
| NumLimPartners | 6 | Only present for LP-type entities. |

## Previous Names (occurs max 10)

| Field | Max size | Notes |
| --- | --- | --- |
| Change of Name Date | 10 | Only supplied if name changes occurred. |
| Company name (previous) | 160 | Only supplied if name changes occurred. |
