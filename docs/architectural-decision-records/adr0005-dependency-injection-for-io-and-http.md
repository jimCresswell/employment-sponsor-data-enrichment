# ADR 0005: Dependency Injection for I/O and HTTP

Date: 2026-02-01

## Status

Accepted

## Context

Pipeline steps depend on file I/O and HTTP calls. Direct dependencies would make testing brittle and require real network access.

## Decision

Use protocol-style interfaces (`protocols.py`) and concrete implementations (`infrastructure/`). Steps accept injected dependencies (file system, HTTP client, cache, rate limiter, circuit breaker) to keep I/O replaceable.
Concrete wiring is owned by the composition root (`composition.py`) and called by the CLI. Application entry points require injected dependencies with no concrete defaults.

## Consequences

- Tests can use in-memory files and fake HTTP clients from `tests/fakes/`.
- Production uses concrete implementations without changing step logic.
- Integration boundaries are explicit and easier to refactor.
