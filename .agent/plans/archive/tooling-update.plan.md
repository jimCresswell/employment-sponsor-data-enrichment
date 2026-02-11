> Archived Plan Notice (2026-02-11): this file is historical reference only.
> Do not execute this plan directly.
> Active execution queue: `.agent/plans/linear-delivery-plan.md`.
> Durable contracts and operational guidance live in `README.md`, `docs/`, and `docs/architectural-decision-records/`.

# Tooling Update Plan (Python 3.14+) — `uv` + Hatchling (Entry Point)

This is the **entry-point plan** for updating tooling in this repository.
It is authoritative for a new session and should be read first, then followed in order.

This repo is a **Python CLI tool** targeting **Python 3.14+**, distributed via `pip install`.
Tooling requirements:

- **`uv`** for dependency management, virtual environments, running commands, building distributions
- **`hatchling`** as the **PEP 517 build backend** (modern replacement for “setuptools as the thing you configure”)
- **`pyproject.toml`** (PEP 621) as the single source of truth

The aim is a clean, reproducible, contributor-friendly setup with sensible “modern touches” while staying lightweight.

---

## Decisions (locked)

- **Python:** `>=3.14`
- **Workflow tool:** `uv`
- **Build backend:** `hatchling` (migration required)
- **Layout:** `src/` layout
- **CLI exposure:** `[project.scripts]`
- **Quality tooling:** Ruff + Pytest + Pyright (required; staged alongside mypy during transition)
- **Reproducibility:** commit `uv.lock`
- **CI:** minimal GitHub Actions workflow (lint, test, build) — **deferred**

No `setup.py`. No `setup.cfg`.

---

## Entry-point checklist (new session)

1. Confirm Python is **3.14+** and `uv` is installed.
2. Read this plan end-to-end.
3. Read `.agent/plans/archive/tooling-update-mypy-to-pyright.plan.md` (type checker migration details).
4. Run current quality gates (expect failures during migration):
   - `uv sync --group dev`
   - `uv run check`
5. Start Phase 1 below; do not skip phases.

---

## Repo layout

Analyse and adapt as appropriate to the specific needs of your project.

```text
yourtool/
  pyproject.toml
  README.md
  LICENSE
  .gitignore
  uv.lock
  .python-version              # optional, recommended (e.g. "3.14")
  src/
    yourtool/
      __init__.py
      cli.py
  tests/
    test_cli.py
  .github/
    workflows/
      ci.yml
```

Conventions:

- Package/import name: `yourtool`
- Command name: `yourtool`
- CLI module: `src/yourtool/cli.py`

---

## `pyproject.toml` (copy/paste baseline)

> Replace `yourtool` with your actual package + command name.

```toml
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[project]
name = "yourtool"
version = "0.1.0"
description = "Short description of what the CLI does"
readme = "README.md"
requires-python = ">=3.14"
license = { text = "MIT" }
authors = [{ name = "Jim", email = "cv@jimcresswell.net" }]
keywords = ["cli"]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Environment :: Console",
  "License :: OSI Approved :: MIT License",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.14",
]
dependencies = [
  # CLI framework (recommended)
  "typer>=0.12",
  # Optional UX polish (recommended for CLIs)
  "rich>=13.7",
  # Optional: config dirs if you plan to read/write config
  # "platformdirs>=4.2",
]

[project.scripts]
yourtool = "yourtool.cli:app"

[dependency-groups]
dev = [
  "pytest>=8",
  "ruff>=0.6",
  # Required during transition; eventually replace mypy.
  "pyright>=1.1.380",
  "mypy>=1.11",
]

[tool.hatch.build.targets.wheel]
packages = ["src/yourtool"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
# E/F: pycodestyle/pyflakes
# I: import sorting
# B: bugbear
# UP: pyupgrade

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Notes:

- `[dependency-groups]` is used for dev dependencies; `uv` consumes these cleanly.
- Keep runtime dependencies minimal for a CLI; put everything else in `dev`.

---

## CLI implementation (Typer baseline + modern UX touches)

Create `src/yourtool/cli.py`:

```python
from __future__ import annotations

import importlib.metadata
from typing import Annotated

import typer
from rich import print

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="yourtool — short tagline here",
)

def _version() -> str:
    # Works when installed (wheel/sdist) and in editable mode
    try:
        return importlib.metadata.version("yourtool")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0+local"

@app.callback()
def main(
    version: Annotated[bool, typer.Option("--version", help="Show version and exit.")] = False,
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Enable verbose output.")] = False,
) -> None:
    if version:
        print(_version())
        raise typer.Exit(code=0)

    # You can wire verbosity into logging later; keep it simple for now.
    if verbose:
        print("[dim]verbose mode enabled[/]")

@app.command()
def hello(name: str = "world") -> None:
    """Example command."""
    print(f"[bold green]hello[/] {name}")
```

Key “modern touches” included:

- `--version` wired to installed distribution metadata
- `--verbose` placeholder (easy to extend into logging)
- Clean help/UX defaults

Entry point stays:

```toml
[project.scripts]
yourtool = "yourtool.cli:app"
```

---

## Testing baseline

Create `tests/test_cli.py`:

```python
from typer.testing import CliRunner

from yourtool.cli import app

runner = CliRunner()

def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip()  # non-empty

def test_hello_default() -> None:
    result = runner.invoke(app, ["hello"])
    assert result.exit_code == 0
    assert "hello" in result.stdout

def test_hello_name() -> None:
    result = runner.invoke(app, ["hello", "--name", "Jim"])
    assert result.exit_code == 0
    assert "Jim" in result.stdout
```

---

## `uv` workflow (authoritative)

### One-time: install uv

- Prefer: `pipx install uv`
- Alternative: your standard global install method

### Create/sync environment

From repo root:

- Install runtime deps:
  - `uv sync`

- Install dev deps too:
- `uv sync --group dev`

This creates/updates:

- `.venv/` (or uv-managed env)
- `uv.lock` (commit this)

### Run commands

- CLI:
  - `uv run yourtool --help`
  - `uv run yourtool --version`
  - `uv run yourtool hello --name Jim`

- Quality:
  - `uv run ruff check .`
  - `uv run ruff format .`
  - `uv run pytest -q`
- `uv run pyright`  *(required; staged alongside mypy until migration completes)*

### Build distributions

- `uv build`

Sanity test the artefact:

- `pip install dist/yourtool-*.whl`
- `yourtool --version`
- `yourtool hello --name Jim`

### Editable install (optional)

If you want `yourtool` available without `uv run`:

- `uv pip install -e .`
- `yourtool --help`

---

## Reproducibility policy (modern, contributor-friendly)

- Commit:
  - `pyproject.toml`
  - `uv.lock`

- CI should run with `uv sync --group dev` to ensure consistent deps across contributors and CI.

For end users: `pip install yourtool` ignores your lockfile, as expected.

---

## CI (GitHub Actions) — minimal but complete (deferred)

Create `.github/workflows/ci.yml`:

```yaml
name: ci

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Set up Python
        run: uv python install 3.14

      - name: Sync deps (incl dev)
        run: uv sync --group dev

      - name: Lint
        run: uv run ruff check .

      - name: Format check
        run: uv run ruff format --check .

      - name: Typecheck
        run: uv run pyright

      - name: Test
        run: uv run pytest -q

      - name: Build
        run: uv build
```

Notes:

- Pyright is required; keep the “Typecheck” step.
- CI work is deferred; treat this section as a blueprint, not current work.
- Ruff format check is separate so CI fails if formatting drifts.

---

## Publishing / versioning (choose one)

### Option A: manual version bumps (simplest)

- Keep `version = "0.1.0"` and bump manually.
- Good enough until you automate releases.

### Option B: tag-driven versions (recommended if publishing often)

Use `hatch-vcs` with Hatchling to derive versions from git tags.

Update:

```toml
[build-system]
requires = ["hatchling>=1.25", "hatch-vcs"]
build-backend = "hatchling.build"

[project]
dynamic = ["version"]
# remove the static `version = "..."`
```

And add:

```toml
[tool.hatch.version]
source = "vcs"
```

Then:

- `git tag v0.1.0`
- `uv build` produces `0.1.0`

(If you pick this, ensure the implementing agent updates the version function to read distribution metadata as already shown.)

---

## Optional “modern touches” (add only if needed)

### Pre-commit hooks

If the repo uses pre-commit, add `.pre-commit-config.yaml` for Ruff + basic hygiene.

### Structured logging

If you expect non-trivial verbosity and debugging needs, add:

- `logging` config + `--verbose/--quiet`
- optionally `rich.logging.RichHandler`

### Config locations

If you read/write config, add `platformdirs` and store config in the correct OS location.

### Self-update / completions

Only if genuinely needed; avoid unnecessary complexity early.

---

## What NOT to do

- Don’t add `setup.py` / `setup.cfg`
- Don’t use legacy `console_scripts` config
- Don’t run `python setup.py ...`
- Don’t pin runtime dependencies too tightly unless you have a reason (libraries/CLIs benefit from sensible ranges + CI)

---

## Migration phases

### Phase 0 — Baseline audit (no behaviour changes)

- Ensure `uv` is required for all contributor workflows (no alternative paths).
- Record current tooling state (build backend, dependency groups, checks).
- Confirm Python target is `>=3.14` everywhere.
- Identify any legacy configuration to remove (e.g., setuptools configs, mypy-only wiring after Pyright gate).

### Phase 1 — Hatchling migration (clean break)

- Update `[build-system]` to Hatchling.
- Add `[tool.hatch.build.targets.wheel]` with `src/` package discovery.
- Remove any setuptools-specific configuration once Hatchling is in place.
- Validate `uv build` works and produces a wheel.

### Phase 2 — Dependency group migration (clean break)

- Move dev dependencies to `[dependency-groups].dev`.
- Replace all `uv sync --extra dev` usage with `uv sync --group dev`.
- Ensure `uv.lock` is regenerated and committed.

### Phase 3 — Pyright staged gate

- Keep mypy + pyright in `uv run typecheck` and `uv run check`.
- Work down Pyright errors until green.
- Switch to Pyright-only gate; remove mypy from deps and tooling.

### Phase 4 — Documentation + polish

- Update README and docs to require `uv` and the new commands.
- Ensure any references to legacy tooling or setuptools are removed.

---

## Definition of done

- Hatchling is the build backend; setuptools config removed.
- Dev deps live under `[dependency-groups].dev`.
- `uv` is the only supported workflow for contributors.
- `uv.lock` updated and committed.
- `uv run check` passes (Pyright included; mypy removed at the end of migration).
- Docs reflect Python 3.14+, uv-only workflow, and staged Pyright plan.

---

## Deliverables for the implementing agent (definition of done)

1. Migrate tooling to Hatchling and update the repo structure/config as required:
   - `pyproject.toml`, `README.md`, `LICENSE`
   - `src/yourtool/cli.py`
   - `tests/test_cli.py`
   - `.github/workflows/ci.yml` (deferred)
2. Ensure `uv.lock` is generated and committed:
   - `uv sync --group dev`
3. Confirm these commands succeed:
   - `uv sync --group dev`
   - `uv run ruff check .`
   - `uv run ruff format --check .`
   - `uv run pyright` *(required)*
   - `uv run pytest -q`
   - `uv build`
4. Confirm installable CLI:
   - `pip install dist/*.whl`
   - `yourtool --version`
   - `yourtool --help`
