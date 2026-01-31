# Action Plan: Quality, Tests, and Resilient Networking

## Goals
- Raise overall code quality to production-grade: clear interfaces, consistent data contracts, reliable I/O, and minimal duplication.
- Achieve comprehensive test coverage across pipeline stages, utilities, error paths, and CLI behavior.
- Implement disciplined error handling, idiomatic rate limiting, and robust circuit breaker behavior for external API calls.

## Scope
- Affects: `src/uk_sponsor_pipeline/**`, `tests/**`, and supporting docs.
- Non-goals: new product features beyond reliability/quality unless required for correctness.

## Phase 1 — Baseline & Architecture Cleanup
1. **Audit and consolidate HTTP utilities**
   - Remove duplication between `infrastructure.py` and `utils/http.py`.
   - Establish a single, well-tested HTTP client with cache, rate limiter, and circuit breaker.
2. **Strengthen data contracts**
   - Validate stage outputs against `schemas.py` contracts.
   - Standardize column types (e.g., numeric scores) to avoid lexicographic sorting bugs.
3. **Improve configurability and DI**
   - Ensure all stages accept injectable filesystem/HTTP clients for testability.
   - Remove unused DI parameters or fully wire them in.

## Phase 2 — Disciplined Error Handling & Rate Limiting
1. **HTTP error taxonomy**
   - Normalize errors into domain exceptions with actionable messages.
   - Ensure consistent behavior on 401/403/429/5xx (retry/backoff vs fail-fast).
2. **Rate limiter implementation**
   - Enforce min-delay + RPM consistently across all requests.
   - Add jittered exponential backoff for retryable errors (429/5xx).
3. **Circuit breaker semantics**
   - Track consecutive failures per host or per operation.
   - Ensure breaker trips on repeat failures and blocks subsequent calls until reset.
   - Add explicit reset policy or manual reset behavior.

## Phase 3 — Test Coverage Expansion
1. **Stage 1 tests**
   - Aggregation, deduplication, multi-location flags, and stats JSON.
2. **Stage 2 tests**
   - Candidate ranking stability, resume logic, and edge cases.
   - Error handling for 401/403/429/5xx, backoff behavior, and breaker opening.
3. **Stage 3 tests**
   - Threshold/bucket logic, geographic filtering, and sorting correctness.
4. **CLI tests**
   - Command wiring, overrides, and end-to-end flow with fakes.

## Phase 4 — Quality & DX Improvements
1. **Documentation**
   - Update README and configuration docs for new behaviors.
2. **Linting and typing**
   - Close mypy gaps in core modules; add type-safe helpers.
3. **Test tooling**
   - Add coverage enforcement thresholds and CI-ready test targets.

## Deliverables
- Refactored, unified HTTP client + rate limiting + circuit breaker modules.
- Strengthened stage contracts and deterministic sorting behavior.
- Comprehensive test suite with coverage report and clear fixtures.
- Updated documentation reflecting reliability and error-handling guarantees.

## Risks / Dependencies
- The GOV.UK sponsor CSV schema may change; ensure schema validation is resilient.
- Companies House API behavior can vary; tests will be mocked/stubbed accordingly.

## Success Criteria
- All tests pass with high coverage (target: >90% lines in core pipeline modules).
- No duplicate HTTP logic paths; consistent error handling.
- Rate limiting and circuit breaker behavior verified via tests.
