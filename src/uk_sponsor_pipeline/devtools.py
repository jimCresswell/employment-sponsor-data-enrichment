"""Developer tooling entrypoints for uv run.

These commands wrap common checks without requiring repo scripts in PATH.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence


def _run(args: Sequence[str]) -> None:
    result = subprocess.run(args, check=False)
    raise SystemExit(result.returncode)


def lint() -> None:
    _run(["ruff", "check", "src", "tests", *sys.argv[1:]])


def format_code() -> None:
    _run(["ruff", "format", "src", "tests", *sys.argv[1:]])


def format_check() -> None:
    _run(["ruff", "format", "--check", "src", "tests", *sys.argv[1:]])


def typecheck() -> None:
    _run(["mypy", "src", *sys.argv[1:]])


def test() -> None:
    _run(["pytest", *sys.argv[1:]])


def coverage() -> None:
    _run(
        [
            "pytest",
            "--cov=uk_sponsor_pipeline",
            "--cov-report=term-missing",
            "--cov-fail-under=85",
            *sys.argv[1:],
        ]
    )
