# Companies House Company Data  

## AI Agent Guidance (URI + Bulk CSV)

---

## Purpose

This document defines a **canonical, mechanically reproducible approach** for AI agents
to:

1. Resolve UK companies via **Companies House URIs**
2. Ingest and interpret **bulk CSV (Free Data Product) downloads**
3. Reliably link entities across datasets
4. Apply **exact SIC classification semantics** as used by Companies House

This document is intended for:

- ETL / ELT pipelines
- Entity resolution agents
- Knowledge graph construction
- Data enrichment workflows

It is **not** a guide to the Companies House REST API.

---

## 1. Canonical Company Identifier (URI)

### 1.1 Base URI Pattern

Each UK company has a **permanent canonical URI**:

```
http://data.companieshouse.gov.uk/doc/company/{COMPANY_NUMBER}
```

This URI:

- Represents the company as an entity
- Is stable over time
- Is safe to store and exchange as a foreign key

---

### 1.2 Explicit Mapping Example (Required)

**Mapping rule (deterministic):**

```
CompanyNumber → CompanyURI
```

**Example A (numeric only):**

```
CompanyNumber: 02050399
↓
CompanyURI: http://data.companieshouse.gov.uk/doc/company/02050399
```

**Example B (prefixed company number):**

```
CompanyNumber: SC002180
↓
CompanyURI: http://data.companieshouse.gov.uk/doc/company/SC002180
```

### Rules

- Prefixes (`SC`, `NI`, `FC`, etc.) **must be uppercase**
- Company numbers must be **zero-padded exactly as supplied**
- No URL encoding or transformation is permitted

Agents must treat the URI as the **primary, canonical identifier**.

---

## 2. Supported Retrieval Formats (URI Service)

The URI service supports **content negotiation**:

- JSON (preferred)
- RDF (graph construction)
- XML
- CSV
- YAML
- HTML (browser default)

### Agent Guidance

- Explicitly request **JSON** or **RDF**
- Never scrape HTML
- Treat missing sections as valid, not errors

---

## 3. Scope and Intent of the URI Service

### This service IS

- Company identity resolution
- Lightweight metadata enrichment
- Cross-dataset linking

### This service IS NOT

- A search service
- A filings or documents API
- A substitute for the Companies House REST API

---

## 4. Bulk CSV (Free Data Product) – Field Model

The bulk download CSV uses a fixed, flat schema.

Reference documents:

- `ch-data-product-fields.md` for the authoritative field list, sizes, and field notes.
- `ch-sic-codes.md` for the condensed SIC code list.

The `URI` field must match the canonical mapping rule in Section 1.

## 5. Company Number Prefix Semantics

Prefixes encode jurisdiction and legal form.

Examples:

- `SC` – Scottish company
- `NI` – Northern Ireland company
- `OC` / `SO` – LLPs
- `LP`, `SL`, `NL` – Limited Partnerships
- `FC`, `NF`, `SF` – Overseas companies

Agents must:

- Preserve prefix verbatim
- Never infer jurisdiction without prefix

---

## 6. Error Handling and Absence Semantics

### URI Resolution

- `404 Not Found` → company does not exist
- Do not retry without a different identifier

### Bulk CSV

- Missing columns ≠ errors
- Blank values ≠ false
- Section absence is meaningful

---

## 7. Recommended Agent Strategy

1. Use **CompanyNumber + URI** as primary keys
2. Ingest bulk CSV as authoritative snapshots
3. Use URI service for:
   - Validation
   - Linking
   - Format negotiation
4. Preserve raw categorical values
5. Apply interpretation only downstream

---

## Appendix A – SIC Codes (Authoritative Source)

Companies House uses a **condensed SIC code list**, which **must be treated as authoritative**.

### Rules

- Do NOT substitute ONS SIC descriptions
- Do NOT expand or re-map codes automatically
- Store codes exactly as supplied

### Official Reference (Required)

```
https://resources.companieshouse.gov.uk/sic/
```

Agents should:

- Link SIC codes to this list at query time
- Cache mappings externally if required
- Treat unknown codes as valid future extensions

---

## Appendix B – Versioning and Authority

- URI Customer Guide version: 1.1 (Dec 2011)
- Bulk CSV schema: Companies House Free Data Product
- Publishing authority: Companies House (UK Government)

Despite document age, **URI patterns and CSV fields remain stable**.

---
