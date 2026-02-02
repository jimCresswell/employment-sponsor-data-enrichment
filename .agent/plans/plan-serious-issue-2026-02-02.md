# Plan: Serious Issue (2026-02-02)

## Entry Instructions (Read First)

This plan is a standalone entry point. Before any work:

1) Read directives in this order:
   - `.agent/directives/AGENT.md`
   - `.agent/directives/rules.md`
   - `.agent/directives/project.md`
   - `.agent/directives/python3.practice.md`
2) Follow all requirements therein (TDD, clean breaks, full quality gates, British spelling, etc.).
3) Use this plan as the only scope for the session.

## Scope
Address the high-severity architectural issue from `.agent/reports/standalone_review_2026_02_02.md`:
- Systemic Application → Infrastructure coupling via `LocalFileSystem` defaults.

## Decisions & Constraints (Confirmed)

- Fail fast with clear errors if required dependencies are missing.
- Optimise for architectural soundness, long-term quality, developer experience, and user experience.
- Tests must be fully isolated from IO, repeatable, idempotent, and parallel-safe.
- Add the import-linter rule **before** refactoring to enforce direction during the change.
- No external users; breaking API changes are acceptable.
- Consider whether centralised wiring improves architecture; choose the best long-term option.

## Plan (Linear)

### 1) Add import-linter guard (before refactor)
- Add an import-linter rule that forbids `uk_sponsor_pipeline.application` from importing `uk_sponsor_pipeline.infrastructure`.
- Run `uv run check` to ensure the rule is active (expected to fail until refactor is complete).

**Acceptance criteria**
- Import-linter contract is present and fails when application code imports infrastructure.

---

### 2) Choose and implement the composition root
- Prefer a **centralised wiring module** (e.g., `composition.py`) that builds concrete dependencies and is called by `cli.py`.
- This keeps wiring in one place while keeping `application` clean and testable.

**Acceptance criteria**
- A single composition entry point owns all concrete infrastructure construction.
- `cli.py` delegates wiring to the composition module.

---

### 3) Make filesystem dependencies explicit in application layer
- Remove imports of `LocalFileSystem` from application modules.
- Require `fs: FileSystem` to be passed in; raise a clear error if missing.
- Ensure no application module instantiates `LocalFileSystem` directly.

**Acceptance criteria**
- No `application` modules import `uk_sponsor_pipeline.infrastructure`.
- All application entry points require an injected `FileSystem` or fail fast with a clear error.

---

### 4) Update CLI + tests to use injected dependencies
- Update CLI commands to pass the injected filesystem from composition root.
- Ensure tests continue to use in-memory fakes and remain parallel-safe.

**Acceptance criteria**
- CLI commands work as before but now pass `fs` explicitly.
- `run_pipeline` receives its filesystem from the CLI (or caller) rather than defaulting internally.
- Tests remain IO-isolated, idempotent, and parallel-safe.

---

## Quality Gates
- Run the full sequence via `uv run check` after changes.
