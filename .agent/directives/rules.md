# Rules

These rules are mandatory for all work in this repository. For goals and outputs, see `project.md`.

## Core

- Ask first: **could it be simpler without compromising quality?**
- No compatibility layers. Replace and delete old paths.
- DRY + YAGNI + KISS.
- Keep boundaries explicit: protocols for interfaces, infrastructure for implementations.
- Each module has a single responsibility and a narrow public API; keep helpers private.
- Dependency direction is one-way: domain/application code must not import infrastructure.
- Delete unused code, unused files, and dead branches.
- Use conventional commit messages (e.g. `feat: ...`, `fix: ...`).

## Error Handling

- Fail fast with clear error messages.
- Do not ignore exceptions.
- Preserve error context when re‑raising.
- Prefer typed, domain-specific exceptions over generic ones.

## Configuration

- Read environment variables once at entry points.
- Pass configuration through function calls; avoid global config lookups.

## Testing

- All tests are network‑isolated; no real HTTP calls.
- Prefer small, injected fakes over complex mocks.
- Tests must prove behaviour, not implementation details.
- No skipped tests.
- For each new boundary: add unit tests for pure logic and contract tests for protocols.

## Style

- Python 3.11+ with type hints.
- Use snake_case for modules and functions.
- Keep Ruff and Mypy clean; fix root causes instead of suppressing.
- Avoid `Any` in core/domain code; use Protocols, dataclasses, and TypedDicts instead.
- Use British spelling in all documentation, comments, and user-facing text.

## Documentation

- Documentation is comprehensive, includes examples, and is created at the same time as functionality.
- All code has inline documentation (docstrings and only the minimum necessary comments).
- Key usage and comprehension guidance live in README(s).
- Decisions and architecture are accurately captured in ADRs.
- Documentation is cross-referenced, DRY, and never deferred.
- We are building a system; humans and AI are part of it. Missing documentation is a critical engineering failure mode.

## Quality Gates

- Do not disable linting, formatting, type checking, or tests.
- Run the full gate sequence every time, in order: `format` → `typecheck` → `lint` → `test` → `coverage`.
- Do not run partial gates; use `uv run check` or the explicit full sequence.
- All linting runs via `uv run lint` (ruff + import-linter once wired).

## Tooling

- Use `uv` for environments and commands.
- Use `ruff` for linting/formatting, `mypy` for types, `pytest` for tests.

## Architecture Records

- Add/adjust ADRs when introducing new boundaries, dependency direction changes, or cross-cutting infrastructure.
