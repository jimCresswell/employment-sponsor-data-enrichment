# Rules

These rules are mandatory for all work in this repository. For goals and outputs, see `project.md`.

## Core

- Always reflect on the question: **could it be simpler without compromising quality or functionality?**
- Strict typing:what  no `Any` allowed, use `object` only at incoming IO boundaries, no `cast` or `type: ignore`.
- No compatibility layers, no backward compatibility. Clean breaks only. Replace and delete old paths.
- No trivial aliases, refactor instead.
- DRY + YAGNI + KISS.
- Keep boundaries explicit: protocols for interfaces, infrastructure for implementations.
- Each module has a single responsibility and a narrow public API; keep helpers private.
- Dependency direction is one-way: domain/application code must not import infrastructure.
- Delete unused code, unused files, and dead branches.
- Never disable linting, formatting, type checking, or tests.
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

- Python 3.13+ with type hints.
- Use snake_case for modules and functions.
- Keep Ruff and Pyright clean; fix root causes instead of suppressing.
- Avoid `Any` outside IO boundaries; validate external data into strict `TypedDict` or dataclass shapes immediately after ingestion.
- Ruff `ANN401` must be enabled; allow per-file ignores only for explicit IO boundary modules.
- Use British spelling in all documentation, comments, and user-facing text.
- Protocol implementations must mark overridden methods with `@override`.
- Private names (prefixed with `_`) must not be imported or used outside their module; make them public or provide a public wrapper.
- Tests must be fully type-annotated, including fixtures and test parameters; no `Unknown` leakage in tests.
- `Any` is forbidden (explicit or implicit). Enforce with Ruff `ANN401`; Pyright strict mode must not allow `Any` to escape IO boundaries.
- Complexity limits are enforced via Ruff (C90/PLR): max complexity 45, max branches 45, max returns 8, max statements 220, max arguments 20.
- File/function size guidance is documented in `AGENT.md` (no automated gate yet).
- Incoming IO payloads must be accepted as `object`/`Mapping[str, object]`, validated immediately with Pydantic, and converted to strict dataclasses/`TypedDict` shapes using helpers in `infrastructure/io/validation.py`.

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
- Use `ruff` for linting/formatting, `pyright` for types, `pytest` for tests.

## Architecture Records

- Add/adjust ADRs when introducing new boundaries, dependency direction changes, or cross-cutting infrastructure.
