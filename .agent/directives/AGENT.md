# AGENT.md

Core directives for this repository. Read this file first, then `rules.md` and `project.md`.

## First Question

Always ask: **could it be simpler without compromising quality?**

## Non‑negotiables

- No backwards compatibility. Replace old approaches; delete legacy paths.
- DRY + YAGNI: avoid duplicate logic and speculative features.
- Respect the intent of SOLID principles always, apply them where appropriate.
- Fail fast with clear errors. Never silence or swallow errors.
- Keep tests fully network‑isolated. No real HTTP calls in tests.
- All development MUST be carried out via TDD.

## Repo Context

- Language: Python 3.14+
- Tooling: `uv`, `pytest`, `ruff`, `pyright`, `import-linter`
- Commands:
  - `uv sync --group dev`
  - `uv run lint`
  - `uv run format`
  - `uv run format-check`
  - `uv run typecheck`
  - `uv run test`
  - `uv run coverage` (gated)

## Where to Look

- `project.md` covers goals, pipeline stages, outputs, and configuration.
- `rules.md` covers quality gates, testing constraints, and working conventions.

## Engineering Expectations

- TDD is mandatory.
- All code MUST be type-hinted.
- Prefer dependency injection and pure functions.
- Read environment variables once at the entry point (CLI), pass config through.
- Remove dead code and unused files.
- Keep documentation current with behaviour and CLI flags.
- Incoming IO boundaries accept `object`/`Mapping[str, object]` only, then validate with Pydantic and emit strict dataclasses/`TypedDict` shapes via `infrastructure/io/validation.py`.

## Size and Complexity Guidance

- Functions should be ≤ 50 lines and classes ≤ 200 lines; split earlier if behaviour is mixed.
- Modules should be ≤ 400 lines; split by responsibility when exceeded.
- Complexity is enforced by Ruff: max complexity 45, max branches 45, max returns 8, max statements 220, max arguments 20.
