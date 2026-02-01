# ADR 0001: Record Architecture Decisions

Date: 2026-02-01

## Status

Accepted

## Context

The pipeline has several non-trivial decisions around tooling, staging, external integrations, and quality gates. These decisions need a durable record so contributors can understand the "why" behind the current architecture.

## Decision

Use Architectural Decision Records (ADRs) in `docs/architectural-decision-records` to capture major architectural and workflow decisions. Each ADR uses a consistent template (Context, Decision, Consequences) and a sequential ID.

## Consequences

- Architectural intent is documented and discoverable.
- Future changes can reference or supersede existing decisions.
- Onboarding is improved without relying on tribal knowledge.
