> Archived Plan Notice (2026-02-11): this file is historical reference only.
> Do not execute this plan directly.
> Active execution queue: `.agent/plans/linear-delivery-plan.md`.
> Durable contracts and operational guidance live in `README.md`, `docs/`, and `docs/architectural-decision-records/`.

# Strict mypy → strict Pyright migration (uv repo)

This doc complements the general `uv + hatchling` blueprint and focuses only on migrating from **strict mypy** to **strict Pyright**, with the project rule:

> **Unknown is permitted only at incoming IO boundaries. Any propagation of Unknown is a bug. Any is forbidden.**

The goal is **strict-by-default**, with explicit, audited IO boundary parsing that converts `object/unknown` into typed domain structures immediately.

---

## 0) Target end state

### CI gates

- `ruff check .`
- `ruff format --check .`
- `pytest`
- `pyright`

### Type policy

- **No `Any`** (explicit or implicit): forbidden.
- **No `Unknown` beyond IO boundaries**: forbidden.
- All boundary inputs typed as `object` or `Unknown` *only in boundary modules*, then validated/parsed into strict types.

### Architectural rule

Every IO boundary gets a dedicated “adapter/parser” layer that:

1. accepts `object` / `dict[str, object]` / `Sequence[object]`
2. validates shape and invariants
3. returns strongly typed domain objects (`dataclass`, `TypedDict`, `Protocol`, etc.)

---

## 1) Add Pyright in parallel (do not remove mypy yet)

### 1.1 Confirm `pyrightconfig.json`

`pyrightconfig.json` already exists at repo root and is intentionally strict:

- all `Any` diagnostics are errors
- all `Unknown` diagnostics are errors
- missing stubs/imports are errors (forces proper typing dependencies)

### 1.2 Update dev tooling versions and add Pyright

Update the dev dependency group (PEP 735 `dependency-groups`) to latest versions and add Pyright:

```toml
[dependency-groups]
dev = [
  "pytest>=9.0.2",
  "pytest-cov>=7.0.0",
  "mypy>=1.19.1",
  "pyright>=1.1.408",
  "ruff>=0.14.14",
  "import-linter>=2.9",
  "pre-commit>=4.5.1",
  "pandas-stubs>=2.3.3.251219",
  "types-requests>=2.32.4.20260107",
  "types-beautifulsoup4>=4.12.0.20250516",
  "types-tqdm>=4.67.0.20250809"
]
```

Then:

- `uv sync --group dev`
- `uv run pyright`

### 1.3 CI/local: run both checkers temporarily

For 1–3 PRs, run both:

- `uv run mypy`
- `uv run pyright`

During this phase, mypy remains the “ship gate”, and Pyright is your “worklist generator” until it’s green.
Update `uv run typecheck` to run both in sequence, and keep `uv run check` aligned with the quality gate order.

Note: current repo uses `[project.optional-dependencies]` + `uv sync --extra dev`; this migration requires moving dev deps into `[dependency-groups]` and switching commands to `uv sync --group dev`.

---

## 2) Handling “Unknown only at IO boundaries” in practice

Pyright’s strictness means any untyped data source will immediately trigger Unknown-related errors.
That’s desirable given your policy — but you need a repeatable pattern to eliminate Unknown at the boundary.

### 2.1 Boundary typing pattern (recommended)

At the IO boundary:

- treat inputs as `object`
- validate + narrow with `isinstance`, `TypeGuard`, or explicit parsing functions
- convert into strongly typed objects

#### **Example (JSON response boundary)**

```python
from __future__ import annotations
from typing import TypeGuard

def is_str_dict(x: object) -> TypeGuard[dict[str, object]]:
    return isinstance(x, dict) and all(isinstance(k, str) for k in x)

def require_str(x: object, *, field: str) -> str:
    if not isinstance(x, str):
        raise ValueError(f"{field} must be str")
    return x

def parse_payload(raw: object) -> dict[str, object]:
    if not is_str_dict(raw):
        raise ValueError("payload must be a dict[str, object]")
    return raw
```

Then immediately convert into:

- dataclasses, or
- `TypedDict` with required keys, or
- a small domain model.

### 2.2 Pandas boundary rule

Treat Pandas as a **transport** and enforce schema/typing at the edges.

Recommended approach:

- validate required columns explicitly
- when extracting values from a row/cell, treat as `object` and parse
- convert into typed domain records as soon as feasible

Avoid trying to make DataFrame internals “fully typed” — enforce typing **before** and **after** pandas transforms.

---

## 3) What will change relative to strict mypy

### 3.1 Any vs Unknown philosophy

- mypy: `Any` often becomes “silently accepted”
- pyright: `Unknown` is sticky unless narrowed, and strict mode will force you to deal with it

Given your policy, Pyright is a better match — it makes “unknown propagation” visible.

### 3.2 `cast(...)` usage

Mypy users often rely on `cast` to silence errors.
In Pyright strict, excessive `cast` is a smell because it can hide boundary typing issues.

Rule of thumb:

- Prefer **parsing/narrowing** over `cast`
- Allow `cast` only when:
  - the value is proven by invariant elsewhere, and
  - you can document why the invariant holds

### 3.3 Type ignores

Mypy supports fine-grained ignores like:

```python
# type: ignore[arg-type]
```

Pyright supports:

- `# type: ignore` (generic)
- `# pyright: ignore[reportXyz]` (specific diagnostic)

Policy recommendation:

- keep ignores rare
- if used, require a comment explaining why and ideally a follow-up issue to remove it

---

## 4) Concrete migration checklist (PR-by-PR)

### PR1 — introduce Pyright + config (no behavioural change)

- Add `pyrightconfig.json`
- Add `pyright` dependency
- Add CI step for `pyright` (non-blocking if you need a brief ramp, but ideally blocking)

### PR2 — eliminate Unknown propagation from IO

- Identify sources:
  - `requests` JSON
  - env vars / CLI args / file IO
  - pandas row/cell values
- Introduce adapter/parsing layer functions to convert `object → typed`
- Replace `cast` usage at boundaries with parsing + narrowing

### PR3 — make Pyright the gate

- CI: Pyright required
- Remove mypy from CI

### PR4 — remove mypy

- Remove mypy dependency
- Remove `mypy.ini` / `[tool.mypy]`
- Remove mypy-specific ignores and any related scripts/docs

---

## 5) uv commands / scripts (recommended)

### Local

- `uv sync --group dev`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run pytest -q`
- `uv run pyright`

### CI

Use the same commands to keep parity.

---

## 6) Third-party typing hard line (because `reportMissingTypeStubs` is error)

Your Pyright config treats missing stubs/imports as errors.
That means you must do one of:

- install a stub package (e.g. `types-requests`, `pandas-stubs`, etc.)
- choose a different dependency that ships types
- isolate the dependency behind a typed wrapper that returns typed domain objects

This is aligned with your “Unknown is only allowed at IO boundaries” rule.

---

## 7) Common friction points and solutions

### 7.1 `requests` and `.json()`

`requests.Response.json()` effectively returns untyped data.

Solution:

- immediately parse return value (`object`) into typed structures
- do not let `dict[str, Any]` escape boundary modules

### 7.2 Optional values and narrowing

Prefer explicit narrowing:

- `if x is None: raise ...`
- `assert x is not None`
- `isinstance` checks

### 7.3 Dict-heavy code

Replace `dict[str, object]` with:

- `TypedDict` (best for structured JSON-like objects)
- dataclasses (best for domain models)
- Protocol (best for structural typing across implementations)

---

## 8) Definition of done

Pyright is the single source of truth when:

- `uv run pyright` is clean on main
- no `Any` in the codebase (explicit or implicit)
- no `Unknown` escapes boundary modules
- mypy removed from dependencies and CI

---

## 9) Optional tightening knobs (after green)

Once stable, consider:

- treating `reportPrivateUsage` as error (if you want stricter encapsulation)
- switching `reportUnnecessaryTypeIgnoreComment` from warning → error
- adding a rule in CI that disallows `typing.Any` imports (belt-and-braces)

---
