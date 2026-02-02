"""Developer tooling entrypoints for uv run.

These commands wrap common checks without requiring repo scripts in PATH.
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Sequence

from rich import print as rprint


def _run(args: Sequence[str]) -> int:
    result = subprocess.run(args, check=False)
    return result.returncode


def _run_or_exit(args: Sequence[str]) -> None:
    raise SystemExit(_run(args))


def _emit(message: str) -> None:
    rprint(message)


def lint() -> None:
    steps: list[list[str]] = [
        ["ruff", "check", "src", "tests", "--ignore-noqa", *sys.argv[1:]],
        [sys.executable, "scripts/check_inline_ignores.py"],
        [sys.executable, "scripts/check_us_spelling.py"],
        ["lint-imports"],
    ]
    for args in steps:
        code = _run(args)
        if code != 0:
            raise SystemExit(code)
    raise SystemExit(0)


def format_code() -> None:
    _run_or_exit(["ruff", "format", "src", "tests", *sys.argv[1:]])


def format_check() -> None:
    _run_or_exit(["ruff", "format", "--check", "src", "tests", *sys.argv[1:]])


def typecheck() -> None:
    raise SystemExit(_run(["pyright", *sys.argv[1:]]))


def spelling_check() -> None:
    _run_or_exit([sys.executable, "scripts/check_us_spelling.py", *sys.argv[1:]])


def test() -> None:
    _run_or_exit(["pytest", *sys.argv[1:]])


def coverage() -> None:
    _run_or_exit(
        [
            "pytest",
            "--cov=uk_sponsor_pipeline",
            "--cov-report=term-missing",
            "--cov-fail-under=85",
            *sys.argv[1:],
        ]
    )


def check() -> None:
    steps: list[tuple[str, list[str]]] = [
        ("format", ["ruff", "format", "src", "tests"]),
        ("typecheck", ["pyright"]),
        ("lint", ["ruff", "check", "src", "tests", "--ignore-noqa"]),
        ("lint-inline-ignores", [sys.executable, "scripts/check_inline_ignores.py"]),
        ("lint-us-spelling", [sys.executable, "scripts/check_us_spelling.py"]),
        ("import-linter", ["lint-imports"]),
        ("test", ["pytest"]),
        (
            "coverage",
            [
                "pytest",
                "--cov=uk_sponsor_pipeline",
                "--cov-report=term-missing",
                "--cov-fail-under=85",
            ],
        ),
    ]

    for name, args in steps:
        _emit(f"[bold cyan]→ {name}[/bold cyan] [dim]{' '.join(args)}[/dim]")
        start = time.perf_counter()
        code = _run(args)
        duration = time.perf_counter() - start
        if code != 0:
            _emit(f"[bold red]✗ {name} failed[/bold red] [dim]({duration:.2f}s, exit {code})[/dim]")
            raise SystemExit(code)
        _emit(f"[green]✓ {name}[/green] [dim]({duration:.2f}s)[/dim]")

    _emit("[bold green]✓ All checks passed[/bold green]")
    raise SystemExit(0)
