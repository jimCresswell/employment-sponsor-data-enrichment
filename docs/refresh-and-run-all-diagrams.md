# Refresh and Cache-Only Run Diagrams

This document provides the flow diagrams for refresh commands and cache-only `run-all`.

## Refresh Flow (Snapshot Generation)

```mermaid
flowchart TD
    Start[Operator runs refresh command] --> Url[CLI validates URL + config]
    Url --> StartProgress[CLI starts progress reporting]
    StartProgress --> Download[Stream download to raw artefact]
    Download --> Extract{ZIP source?}
    Extract -- Yes --> ExtractCsv[Extract CSV to raw.csv]
    Extract -- No --> RawCsv[Use raw.csv as-is]
    ExtractCsv --> ValidateHeaders[Trim + validate headers]
    RawCsv --> ValidateHeaders
    ValidateHeaders --> Clean[Clean rows into canonical schema]
    Clean --> Index[Index tokens + bucketed profiles]
    Index --> Manifest[Write manifest + stats]
    Manifest --> Commit[Atomic move to snapshot date dir]
    Commit --> Done[Snapshot ready]
```

## Cache-Only `run-all` Flow

```mermaid
flowchart TD
    Start[Operator runs run-all] --> Resolve[Resolve snapshot paths]
    Resolve --> Validate[Fail fast if artefacts missing]
    Validate --> Enrich[transform-enrich from clean snapshots]
    Enrich --> Score[transform-score]
    Score --> Usage[usage-shortlist]
    Usage --> Done[Outputs written]
```

Notes:
- Refresh commands may use network IO; `run-all` does not.
- Cache-only runs consume clean snapshots only and never read raw artefacts.
