# ADR 0011: No Dashboard, Plugins, or SQLite

Date: 2026-02-01

## Status

Accepted

## Context

The project’s scope is focused on an auditable data pipeline. UI layers, plugin systems, and embedded databases add complexity without improving the core outcome.

## Decision

Explicitly exclude dashboards, plugin architecture, and SQLite persistence. The pipeline remains CLI-driven with file-based outputs.

## Consequences

- Fewer moving parts and simpler operations.
- Reduced maintenance surface area.
- Future UI or storage work must be proposed as new ADRs.
