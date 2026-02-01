# ADR 0004: Config Loaded at CLI and Passed Through

Date: 2026-02-01

## Status

Accepted

## Context

The pipeline is executed through a CLI and needs predictable configuration that works for both production runs and tests. Global configuration can cause hidden coupling and make tests harder to control.

## Decision

Load configuration once at the CLI entry point and pass it through function calls. Configuration values are sourced from `.env` or environment variables and encapsulated in `PipelineConfig`.

## Consequences

- Configuration is explicit and testable.
- Functions remain pure and dependency-injected where possible.
- Environment lookups are centralized and easier to audit.
