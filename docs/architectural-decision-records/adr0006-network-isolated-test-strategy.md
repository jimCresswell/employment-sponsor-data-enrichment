# ADR 0006: Network-Isolated Test Strategy

Date: 2026-02-01

## Status

Accepted

## Context

The pipeline relies on external APIs. Tests must be deterministic, fast, and safe to run without network access.

## Decision

Block real network calls in tests and use injected fakes or mocks for HTTP. Tests validate behaviour through small, focused units and in-memory filesystem fixtures.

## Consequences

- Tests run reliably without external dependencies.
- Failures are attributable to code, not network conditions.
- HTTP behaviour is validated through controlled fakes.
