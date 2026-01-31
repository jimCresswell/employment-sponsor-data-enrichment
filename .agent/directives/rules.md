# Rules

These rules are mandatory for all work in this repository.

## Core

- Ask first: **could it be simpler without compromising quality?**
- No compatibility layers. Replace and delete old paths.
- DRY + YAGNI + KISS.
- Keep boundaries explicit: protocols for interfaces, infrastructure for implementations.
- Delete unused code, unused files, and dead branches.

## Error Handling

- Fail fast with clear error messages.
- Do not ignore exceptions.
- Preserve error context when re‑raising.

## Configuration

- Read environment variables once at entry points.
- Pass configuration through function calls; avoid global config lookups.

## Testing

- All tests are network‑isolated; no real HTTP calls.
- Prefer small, injected fakes over complex mocks.
- Tests must prove behaviour, not implementation details.
- No skipped tests.

## Quality Gates

- Do not disable linting, formatting, type checking, or tests.
- Run gates in order: `format` → `typecheck` → `lint` → `test` → `coverage`.

## Tooling

- Use `uv` for environments and commands.
- Use `ruff` for linting/formatting, `mypy` for types, `pytest` for tests.
