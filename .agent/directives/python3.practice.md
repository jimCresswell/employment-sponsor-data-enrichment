# Python 3.14+ Practices (Repository Directive)

This file complements `.agent/directives/AGENT.md`, `.agent/directives/rules.md`, and
`.agent/directives/project.md`. If anything conflicts, those directives take precedence.

## Language and Tooling

- Python 3.14+ only.
- Use `uv` for environment and command execution; prefer `uv run check` for full gates.
- Tooling is fixed: `ruff` (format + lint), `pyright` (types), `pytest` (tests), `import-linter` (architecture).

## Architecture and Boundaries

- Layered structure: CLI → application → domain → infrastructure.
- Domain code must not import application, CLI, or infrastructure.
- Use `typing.Protocol` for DI contracts; use `@override` on protocol implementations.
- Use ABCs only when shared implementation inheritance is required.
- No compatibility layers; clean breaks only.

## Typing and Data Modelling

- No `Any`, no `cast`, no inline ignores.
- Accept untrusted inputs as `object`/`Mapping[str, object]` at IO boundaries only.
- Validate at IO boundaries with Pydantic helpers in `infrastructure/io/validation.py`.
- Convert validated data into strict `TypedDict` or dataclasses immediately after ingestion.
- Prefer `dataclasses(frozen=True)` for immutable value objects.
- Use built-in generics (e.g., `list[str]`, `dict[str, int]`).

## Configuration

- Read environment variables once at the CLI entry point.
- Configuration is immutable and passed through function calls (no global lookups).
- Use `PipelineConfig` for configuration; do not re-read env elsewhere.

## IO and Infrastructure

- Application and domain code must not import `requests` or use filesystem APIs directly.
- All IO goes through protocol-backed infrastructure implementations.
- Cache reads are filesystem IO; treat them as boundary operations.

## Logging and Observability

- Use the shared logger factory in `observability/logging.py`.
- Prefer structured, key-value context; never log secrets or PII.
- Do not print from application/infrastructure modules; CLI owns user-facing output.

## Testing

- TDD is mandatory.
- Tests must be network-isolated; no real HTTP calls.
- Use fakes in `tests/fakes/`; prefer small injected fakes over complex mocks.
- Tests must be fully type-annotated (fixtures and test parameters included).
- Add contract tests for new protocols and unit tests for pure logic.

## Data Pipeline Principles

- ETL transforms produce immutable artefacts.
- Usage steps read artefacts and produce usage outputs; they do not mutate upstream artefacts.
- Keep artefact boundaries explicit and documented.

## Documentation

- Use British spelling in documentation, comments, and user-facing strings.
- Keep README(s) and ADRs aligned with actual behaviour and CLI flags.
- Document public APIs in module docstrings with short examples.

## Python Idioms (Aligned with Repo)

- Prefer `pathlib.Path` over string paths.
- Use timezone-aware `datetime` values (UTC where applicable).
- Prefer f-strings for formatting.
- Keep functions and modules small; split by responsibility.
