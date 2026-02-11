> Archived Plan Notice (2026-02-11): this file is historical reference only.
> Do not execute this plan directly.
> Active execution queue: `.agent/plans/linear-delivery-plan.md`.
> Durable contracts and operational guidance live in `README.md`, `docs/`, and `docs/architectural-decision-records/`.

# UK Sponsor Pipeline Plan (Consolidated)

## Principles
- No backwards compatibility; remove legacy/unused code paths.
- DRY + YAGNI; prefer small, testable components over premature features.
- Tests are fully network-isolated.

## Completed (Current Baseline)
- Unified HTTP client with caching, rate limiting, retry/backoff, and circuit breaker.
- Schema validation at stage boundaries.
- Stage 1/2/3 behaviour hardened with deterministic scoring and explainability output.
- CLI overrides for thresholds and geographic filters.
- uv-first developer tooling with lint/format/typecheck/test commands.
- Network-blocking test harness for isolation.
- In-memory end-to-end pipeline test (no real I/O or network).
- Stage 2 batching, incremental output, and resume checkpoints.

## Remaining Work (Critical)
1. **Confirm automatic batching support (top priority)**
   - Verify Stage 2 runs in batches by default via `CH_BATCH_SIZE`.
   - Ensure batching behaviour is observable and reliable without manual intervention.
2. **Config + docs alignment**
   - Ensure docs list only supported features and flags; remove any references to legacy or dropped items.

## Future Work
- CI/CD pipeline (GitHub Actions for lint/format/typecheck/test).

## Explicitly Dropped
- Dashboard/reporting UI
- Plugin architecture
- SQLite persistence layer
