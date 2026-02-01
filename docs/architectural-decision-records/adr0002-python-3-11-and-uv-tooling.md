# ADR 0002: Python 3.11+ and uv Tooling

Date: 2026-02-01

## Status

Accepted

## Context

The project needs fast, reproducible environment management with consistent formatting, linting, and type checking. The tooling should be simple to run and easy to standardize across contributors.

## Decision

Standardize on Python 3.11+ and use `uv` for environment and command execution. Use:
- `ruff` for linting and formatting
- `mypy` for type checking
- `pytest` for tests

All workflow commands are executed via `uv run`.

## Consequences

- Developers get consistent tooling and commands across machines.
- The project avoids mixed package managers or ad-hoc scripts.
- Tooling choices are opinionated and centralized in `pyproject.toml`.
