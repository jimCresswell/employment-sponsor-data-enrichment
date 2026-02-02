# Review Findings (2026-02-02)

## Findings (ordered by severity)

### Medium

- Extract schema validation logs a warning and continues after exceptions, which contradicts fail-fast and can let invalid CSVs flow downstream.
  - `src/uk_sponsor_pipeline/application/extract.py:92`
  - `src/uk_sponsor_pipeline/application/extract.py:104`

- Several Protocol implementations don’t subclass their Protocols or mark overrides with `@override`, weakening DI contract enforcement and breaking the stated rule.
  - `src/uk_sponsor_pipeline/infrastructure/io/http.py:130`
  - `src/uk_sponsor_pipeline/application/companies_house_source.py:59`
  - `src/uk_sponsor_pipeline/application/companies_house_source.py:83`
  - `tests/fakes/http.py:16`
  - `tests/fakes/filesystem.py:23`
  - `tests/fakes/cache.py:13`
  - `tests/fakes/resilience.py:10`

- Tests/fixtures are missing return type annotations in multiple places, violating strict typing for tests.
  - `tests/network/test_blocking.py:11`
  - `tests/domain/test_organisation_identity.py:16`
  - `tests/conftest.py:31`

- Observability directive is bypassed via direct printing in application/infrastructure, reducing consistent logging/structure.
  - `src/uk_sponsor_pipeline/application/extract.py:142`
  - `src/uk_sponsor_pipeline/infrastructure/io/http.py:222`

### Low

- British spelling rule is violated in documentation/comments/log strings.
  - `src/uk_sponsor_pipeline/config.py:1`
  - `docs/architectural-decision-records/adr0002-python-3-14-and-uv-tooling.md:11`
  - `tests/application/test_transform_register.py:1`
  - `src/uk_sponsor_pipeline/application/transform_enrich.py:194`

- Plan states Phase 9 complete and a terminology scan file exists, but legacy artefacts remain and the scan file is absent.
  - `.agent/plans/refactor-plan.md:24`
  - `.agent/plans/refactor-plan.md:32`
  - `.agent/plans/refactor-plan.md:38`
  - `.agent/plans/refactor-plan.md:113`
  - `src/uk_sponsor_pipeline/stages/`
  - `src/uk_sponsor_pipeline/__pycache__/`
  - `tests/__pycache__/`
  - `reports/download_manifest.json`
  - `reports/terminology-usage.txt`

## Open Questions / Assumptions

- Do you want all non-CLI messaging moved to the shared logger (and keep `rich` output strictly in `cli.py`)?
- Should British spelling be enforced in identifiers too (e.g., `normalise_org_name`, `org_name_normalised`) or only in docs/comments/log text?
- Are `.pyc`/`__pycache__` and `reports/download_manifest.json` intentionally tracked, or should they be removed and ignored?
- Should `reports/terminology-usage.txt` be generated now or should the plan be updated to mark it pending?
