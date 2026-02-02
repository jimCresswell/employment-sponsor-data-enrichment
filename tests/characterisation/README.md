# Characterisation Tests

These tests lock down current behaviour during refactors. They are intentionally conservative and may duplicate core behaviour tests.

## Purpose

- Prevent accidental behavioural changes while refactoring.
- Provide concrete, deterministic expectations for transform outputs and error reporting.
- Act as temporary scaffolding; remove once the target module is stabilised and covered by the refactor tests.

## Removal Criteria

- The corresponding refactor phase is complete and stable.
- Core behaviour tests exist in the final module structure.
- ADRs/README references have been updated to the new boundaries.

## Files

- `test_transform_register_characterisation.py`
- `test_transform_enrich_characterisation.py`
- `test_transform_score_characterisation.py`
