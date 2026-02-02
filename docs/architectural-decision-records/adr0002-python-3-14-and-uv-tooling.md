# ADR 0002: Python 3.14+ and uv Tooling

Date: 2026-02-01

## Status

Accepted

## Context

The project needs fast, reproducible environment management with consistent formatting, linting, and type checking. The tooling should be simple to run and easy to standardise across contributors.

## Decision

Standardise on Python 3.14+ and use `uv` for environment and command execution. Use:

- `ruff` for linting and formatting
- `pyright` for type checking
- `pytest` for tests

All workflow commands are executed via `uv run`.

## Consequences

- Developers get consistent tooling and commands across machines.
- The project avoids mixed package managers or ad-hoc scripts.
- Tooling choices are opinionated and centralised in `pyproject.toml`.
