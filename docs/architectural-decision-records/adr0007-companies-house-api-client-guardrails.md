# ADR 0007: Companies House API Client Guardrails

Date: 2026-02-01

## Status

Accepted

## Context

Companies House API usage must respect rate limits, handle transient failures, and avoid repeated requests for the same resources. The pipeline needs predictable behavior and safe failure modes.

## Decision

Wrap Companies House calls with:
- Disk caching for search and profile responses
- Rate limiting and minimum delay between requests
- Retry with exponential backoff and jitter
- Circuit breaker to stop repeated failures
- Fail-fast authentication errors

These behaviors are centralized in the HTTP client implementation.

## Consequences

- API usage is controlled and respectful of limits.
- Transient errors are retried with bounded backoff.
- Failure states are explicit and protect the API from hammering.
- Cached responses speed up re-runs and reduce cost.
