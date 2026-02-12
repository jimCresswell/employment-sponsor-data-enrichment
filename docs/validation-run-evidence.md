# Validation Run Evidence

This document is the canonical, non-ephemeral log for live validation run evidence.

## Recording Rules

1. Append one `Validation Run` block per completed live validation run.
1. Keep entries chronological.
1. Include exact snapshot dates, source URLs, commands, and result.
1. Record remediation actions when issues are observed.

## Template

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

## Validation Run Log

```text
Validation Run
Date: 2026-02-08
Operator: Codex
Environment: Local macOS; uv 0.9.28; Python 3.14.2
CH_SOURCE_TYPE: file (shell export fallback used because .env lacked explicit value)
Sponsor CSV URL: https://assets.publishing.service.gov.uk/media/6985be6985bc7d6ba0fbc725/2026-02-06_-_Worker_and_Temporary_Worker.csv
Companies House ZIP URL: https://download.companieshouse.gov.uk/BasicCompanyDataAsOneFile-2026-02-01.zip
Sponsor snapshot date: 2026-02-06
Companies House snapshot date: 2026-02-01
Runtime commands executed:
  CH_SOURCE_TYPE=file uv run uk-sponsor transform-enrich
  CH_SOURCE_TYPE=file uv run uk-sponsor transform-score
  CH_SOURCE_TYPE=file uv run uk-sponsor usage-shortlist
  CH_SOURCE_TYPE=file uv run uk-sponsor run-all
Output artefact locations:
  data/processed/sponsor_enriched.csv (100,850 lines incl header)
  data/processed/sponsor_unmatched.csv (18,261 lines incl header)
  data/processed/sponsor_match_candidates_top3.csv (254,716 lines incl header)
  data/processed/sponsor_enrich_checkpoint.csv (119,110 lines incl header)
  data/processed/companies_scored.csv (100,850 lines incl header)
  data/processed/companies_shortlist.csv (11,062 lines incl header)
  data/processed/companies_explain.csv (11,062 lines incl header)
Observed issues:
  Snapshot validation initially failed: Companies House live manifest did not include `artefacts.manifest`.
Recovery actions:
  Added characterisation test and aligned `validation_snapshots` required artefact keys to live Companies House manifest contract.
  Updated docs to include explicit shell export fallback for `CH_SOURCE_TYPE`.
Result: pass
```
