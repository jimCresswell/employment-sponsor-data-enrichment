"""Fail if inline ignore comments are present in the codebase."""

from __future__ import annotations

import re
import sys
import tokenize
from collections.abc import Iterable
from pathlib import Path

IGNORE_PATTERNS: dict[str, re.Pattern[str]] = {
    "noqa": re.compile(r"\bnoqa\b", re.IGNORECASE),
    "type-ignore": re.compile(r"type\s*:\s*ignore", re.IGNORECASE),
    "pyright-ignore": re.compile(r"pyright\s*:\s*ignore", re.IGNORECASE),
    "pylint-disable": re.compile(r"pylint\s*:\s*disable", re.IGNORECASE),
}


def _iter_python_files(paths: Iterable[Path]) -> Iterable[Path]:
    for base in paths:
        if base.is_file() and base.suffix == ".py":
            yield base
            continue
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path


def _find_inline_ignores(path: Path) -> list[tuple[int, str]]:
    matches: list[tuple[int, str]] = []
    with path.open("rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type != tokenize.COMMENT:
                continue
            comment = token.string
            for pattern in IGNORE_PATTERNS.values():
                if pattern.search(comment):
                    matches.append((token.start[0], comment.strip()))
                    break
    return matches


def main(argv: list[str]) -> int:
    roots = [Path(arg) for arg in argv] if argv else [Path("src"), Path("tests"), Path("scripts")]
    violations: list[tuple[Path, int, str]] = []

    for path in _iter_python_files(roots):
        for lineno, comment in _find_inline_ignores(path):
            violations.append((path, lineno, comment))

    if not violations:
        return 0

    print(
        "Inline ignore comments are not allowed; configure exceptions in tool config files.",
        file=sys.stderr,
    )
    for path, lineno, comment in violations:
        print(f"{path}:{lineno}: {comment}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
