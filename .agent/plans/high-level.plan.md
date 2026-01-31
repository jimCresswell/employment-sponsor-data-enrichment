# UK Sponsor Pipeline Plan (Consolidated)

## Principles
- No backwards compatibility; remove legacy/unused code paths.
- DRY + YAGNI; prefer small, testable components over premature features.
- Tests are fully network-isolated.

## Completed (Current Baseline)
- Unified HTTP client with caching, rate limiting, retry/backoff, and circuit breaker.
- Schema validation at stage boundaries.
- Stage 1/2/3 behavior hardened with deterministic scoring and explainability output.
- CLI overrides for thresholds and geographic filters.
- uv-first developer tooling with lint/format/typecheck/test/coverage commands.
- Coverage gate enforced at 85% minimum.
- Network-blocking test harness for isolation.
- In-memory end-to-end pipeline test (no real I/O or network).

## Remaining Work (Critical)
1. **CI pipeline**
   - Add GitHub Actions workflow to run `uv sync --extra dev`, `uv run lint`, `uv run format-check`, `uv run typecheck`, `uv run test`, and `uv run coverage`.
2. **Integration test expansion**
   - Add additional fixture-driven pipeline tests (still fully isolated) to cover edge cases and data contract changes.
3. **Config + docs alignment**
   - Ensure docs list only supported features and flags; remove any references to legacy or dropped items.

## Explicitly Dropped
- Dashboard/reporting UI
- Plugin architecture
- SQLite persistence layer
