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
    _run_or_exit(["ruff", "check", "src", "tests", *sys.argv[1:]])


def format_code() -> None:
    _run_or_exit(["ruff", "format", "src", "tests", *sys.argv[1:]])


def format_check() -> None:
    _run_or_exit(["ruff", "format", "--check", "src", "tests", *sys.argv[1:]])


def typecheck() -> None:
    _run_or_exit(["mypy", "src", *sys.argv[1:]])


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
        ("typecheck", ["mypy", "src"]),
        ("lint", ["ruff", "check", "src", "tests"]),
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
