# Archived Runtime API Mode (Reference Only)

Date archived: 2026-02-06
Status: Archived implementation notes (not active runtime behaviour)

## Purpose

This document preserves the removed CLI runtime API branching so it can be restored
quickly if needed. Runtime pipeline execution is file-only (`CH_SOURCE_TYPE=file`) in
the active code path.

## What Changed

Runtime commands now fail fast for non-file source mode:

- `uk-sponsor transform-enrich`
- `uk-sponsor run-all`

The CLI now raises:

```text
<command> supports CH_SOURCE_TYPE=file only (got '<value>').
```

## Archived CLI Branches

The following branch shape was removed from runtime command wiring in
`src/uk_sponsor_pipeline/cli.py`:

```python
if config.ch_source_type == "file":
    ch_clean_path, ch_token_index_dir = _resolve_companies_house_paths(
        config=config,
        fs=deps.fs,
    )
    config = _with_snapshot_paths(
        config=config,
        sponsor_clean_path=register_value,
        ch_clean_path=ch_clean_path,
        ch_token_index_dir=ch_token_index_dir,
    )
else:
    config = replace(config, sponsor_clean_path=str(register_value))
```

Runtime dependency building for these commands also changed from:

```python
deps = state.build_dependencies(
    cache_dir=DEFAULT_CACHE_DIR,
    build_http_client=True,
    config=config,
)
```

to file-only mode with `build_http_client=False`.

## Still Present in Codebase

API support code is still present in non-runtime wiring and can be reused:

- `ApiCompaniesHouseSource` in `src/uk_sponsor_pipeline/application/companies_house_source.py`
- HTTP client composition in `src/uk_sponsor_pipeline/composition.py`
- API-related exceptions and infrastructure HTTP client code

## Restore Checklist (If Re-enabling Runtime API Mode)

1. Remove `_require_file_runtime_source(...)` guards in `src/uk_sponsor_pipeline/cli.py`.
1. Restore `build_http_client=True` for runtime commands.
1. Restore runtime `if config.ch_source_type == "file": ... else: ...` branches in
   `transform-enrich` and `run-all`.
1. Re-validate docs (`README.md`, `docs/troubleshooting.md`, `docs/validation-protocol.md`).
1. Re-run full quality gates: `uv run check`.
