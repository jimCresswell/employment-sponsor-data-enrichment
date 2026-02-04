"""Scan the repository for American spellings and report suggested British forms.

This script was inspired by the `uwotm8` package (https://pypi.org/project/uwotm8/),
and uses the same underlying dictionary.
"""

from __future__ import annotations

import argparse
import ast
import io
import os
import re
import sys
import token
import tokenize
import tomllib
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, TypeGuard

from breame.data.spelling_constants import AMERICAN_ENGLISH_SPELLINGS

# Domain-standard terms where enforcing conversion is not desirable.
EXCLUDED_US_SPELLINGS: frozenset[str] = frozenset(
    {
        "analog",
        "catalog",
        "check",
        "connection",
        "disk",
        "draft",
        "filet",
        "filter",
        "gray",
        "install",
        "license",
        "mold",
        "pajama",
        "plow",
        "practice",
        "program",
        "tire",
    }
)

WORD_PATTERN = re.compile(r"[A-Za-z]+")
INLINE_CODE_PATTERN = re.compile(r"`[^`]*`")


@dataclass(frozen=True)
class Finding:
    path: Path
    line_number: int
    column_number: int
    word: str
    suggestion: str


@dataclass(frozen=True)
class ScanResult:
    findings: tuple[Finding, ...]
    files_scanned: int


@dataclass(frozen=True)
class SpellingConfig:
    root: Path
    include_extensions: tuple[str, ...]
    exclude_dirs: tuple[str, ...]
    exclude_files: tuple[str, ...]
    include_list: bool


def _root_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _normalise_path(value: str) -> str:
    return Path(value).as_posix().strip("/")


def _is_excluded_by_dirs(relative_path: Path, exclude_dirs: Sequence[str]) -> bool:
    parts = relative_path.parts
    for exclude in exclude_dirs:
        exclude_parts = Path(exclude).parts
        if parts[: len(exclude_parts)] == exclude_parts:
            return True
    return False


def _iter_files(config: SpellingConfig) -> Iterable[Path]:
    root = config.root
    exclude_dirs = [_normalise_path(entry) for entry in config.exclude_dirs]
    exclude_files = {_normalise_path(entry) for entry in config.exclude_files}

    for base, dirs, files in os.walk(root):
        base_path = Path(base)
        relative_dir = base_path.relative_to(root)
        if relative_dir.parts and _is_excluded_by_dirs(relative_dir, exclude_dirs):
            dirs[:] = []
            continue

        dirs[:] = [
            name for name in dirs if not _is_excluded_by_dirs(relative_dir / name, exclude_dirs)
        ]

        for filename in files:
            path = base_path / filename
            if config.include_extensions and path.suffix not in config.include_extensions:
                continue
            relative_file = path.relative_to(root)
            if _is_excluded_by_dirs(relative_file, exclude_dirs):
                continue
            relative_key = _normalise_path(str(relative_file))
            if relative_key in exclude_files or filename in exclude_files:
                continue
            yield path


def _match_case(word: str, replacement: str) -> str:
    if word.isupper():
        return replacement.upper()
    if word.istitle():
        return replacement.title()
    return replacement.lower()


def _mask_inline_code(text: str) -> str:
    if "`" not in text:
        return text
    return INLINE_CODE_PATTERN.sub(lambda match: " " * len(match.group(0)), text)


def _scan_text_line(
    path: Path,
    root: Path,
    mapping: Mapping[str, str],
    line_number: int,
    line: str,
    base_column: int = 1,
) -> list[Finding]:
    findings: list[Finding] = []
    masked_line = _mask_inline_code(line)
    for match in WORD_PATTERN.finditer(masked_line):
        word = match.group(0)
        word_lower = word.lower()
        if word_lower in mapping:
            suggestion = _match_case(word, mapping[word_lower])
            findings.append(
                Finding(
                    path=path.relative_to(root),
                    line_number=line_number,
                    column_number=base_column + match.start(),
                    word=word,
                    suggestion=suggestion,
                )
            )
    return findings


def _iter_identifier_words(identifier: str) -> Iterable[tuple[str, int]]:
    for match in WORD_PATTERN.finditer(identifier):
        token_value = match.group(0)
        token_start = match.start()
        parts = list(re.finditer(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", token_value))
        if len(parts) <= 1:
            yield token_value, token_start
        else:
            for part in parts:
                yield part.group(0), token_start + part.start()


def _scan_identifier(
    path: Path,
    root: Path,
    mapping: Mapping[str, str],
    name: str,
    line_number: int,
    column_number: int,
) -> list[Finding]:
    findings: list[Finding] = []
    for word, offset in _iter_identifier_words(name):
        word_lower = word.lower()
        if word_lower in mapping:
            suggestion = _match_case(word, mapping[word_lower])
            findings.append(
                Finding(
                    path=path.relative_to(root),
                    line_number=line_number,
                    column_number=column_number + offset,
                    word=word,
                    suggestion=suggestion,
                )
            )
    return findings


def _find_name_column(line: str, name: str, fallback: int) -> int:
    index = line.find(name, fallback)
    if index == -1:
        index = line.find(name)
    return (index + 1) if index >= 0 else fallback + 1


def _scan_python_identifiers(
    path: Path,
    root: Path,
    mapping: Mapping[str, str],
    source_lines: Sequence[str],
    tree: ast.AST,
) -> list[Finding]:
    findings: list[Finding] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            line = source_lines[node.lineno - 1] if node.lineno <= len(source_lines) else ""
            column = _find_name_column(line, node.name, node.col_offset)
            findings.extend(_scan_identifier(path, root, mapping, node.name, node.lineno, column))
        elif isinstance(node, ast.arg):
            if node.arg:
                column = node.col_offset + 1
                findings.extend(
                    _scan_identifier(path, root, mapping, node.arg, node.lineno, column)
                )
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            column = node.col_offset + 1
            findings.extend(_scan_identifier(path, root, mapping, node.id, node.lineno, column))
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            if isinstance(node.value, ast.Name) and node.value.id in {"self", "cls"}:
                line = source_lines[node.lineno - 1] if node.lineno <= len(source_lines) else ""
                index = line.find(f".{node.attr}", node.col_offset)
                if index == -1:
                    index = line.find(node.attr, node.col_offset)
                    column = (index + 1) if index >= 0 else node.col_offset + 1
                else:
                    column = index + 2
                findings.extend(
                    _scan_identifier(path, root, mapping, node.attr, node.lineno, column)
                )

    return findings


def _docstring_positions(tree: ast.AST) -> set[tuple[int, int]]:
    positions: set[tuple[int, int]] = set()

    def record_module(node: ast.Module) -> None:
        if not node.body:
            return
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                positions.add((first.lineno, first.col_offset))

    def record_def(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        if not node.body:
            return
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                positions.add((first.lineno, first.col_offset))

    if isinstance(tree, ast.Module):
        record_module(tree)
    for child in ast.walk(tree):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            record_def(child)

    return positions


def _docstring_line_column(
    content_line: str,
    source_line: str,
    fallback_column: int,
) -> int:
    index = source_line.find(content_line)
    if index == -1:
        stripped = source_line.lstrip()
        if stripped:
            index = len(source_line) - len(stripped)
        else:
            index = fallback_column - 1
    return index + 1


def _scan_python_comments_and_docstrings(
    path: Path,
    root: Path,
    mapping: Mapping[str, str],
    source: str,
    source_lines: Sequence[str],
    docstring_starts: set[tuple[int, int]],
) -> list[Finding]:
    findings: list[Finding] = []
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    for token_info in tokens:
        token_type = token_info.type
        if token_type == token.COMMENT:
            raw = token_info.string
            comment_text = raw[1:]
            if comment_text.startswith(" "):
                comment_text = comment_text[1:]
            comment_text = _mask_inline_code(comment_text)
            offset = raw.find(comment_text) if comment_text else len(raw)
            base_column = token_info.start[1] + offset + 1
            findings.extend(
                _scan_text_line(
                    path,
                    root,
                    mapping,
                    token_info.start[0],
                    comment_text,
                    base_column,
                )
            )
        elif token_type == token.STRING and token_info.start in docstring_starts:
            try:
                content = ast.literal_eval(token_info.string)
            except (SyntaxError, ValueError):
                continue
            if not isinstance(content, str):
                continue
            content_lines = content.splitlines()
            for offset, content_line in enumerate(content_lines):
                if not content_line:
                    continue
                content_line = _mask_inline_code(content_line)
                line_number = token_info.start[0] + offset
                source_line = (
                    source_lines[line_number - 1] if line_number <= len(source_lines) else ""
                )
                base_column = _docstring_line_column(
                    content_line,
                    source_line,
                    token_info.start[1] + 1,
                )
                findings.extend(
                    _scan_text_line(
                        path,
                        root,
                        mapping,
                        line_number,
                        content_line,
                        base_column,
                    )
                )

    return findings


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


MATCH_CALL_ATTRIBUTES = frozenset(
    {
        "contains",
        "count",
        "endswith",
        "find",
        "index",
        "match",
        "rfind",
        "rindex",
        "search",
        "startswith",
    }
)
REGEX_FUNCTIONS = frozenset(
    {
        "compile",
        "findall",
        "finditer",
        "fullmatch",
        "match",
        "search",
        "sub",
        "subn",
    }
)


def _is_matching_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute):
        if func.attr in MATCH_CALL_ATTRIBUTES:
            return True
        if (
            isinstance(func.value, ast.Name)
            and func.value.id == "re"
            and func.attr in REGEX_FUNCTIONS
        ):
            return True
    if isinstance(func, ast.Name) and func.id in REGEX_FUNCTIONS:
        return True
    return False


def _iter_ancestors(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> Iterable[ast.AST]:
    parent = parents.get(node)
    while parent is not None:
        yield parent
        parent = parents.get(parent)


MATCH_PATTERN_NODES: tuple[type[ast.AST], ...] = tuple(
    node
    for node in (
        getattr(ast, "MatchValue", None),
        getattr(ast, "MatchSingleton", None),
        getattr(ast, "MatchSequence", None),
        getattr(ast, "MatchMapping", None),
        getattr(ast, "MatchClass", None),
        getattr(ast, "MatchStar", None),
        getattr(ast, "MatchAs", None),
        getattr(ast, "MatchOr", None),
    )
    if node is not None
)


def _is_external_comparison_literal(
    node: ast.AST,
    parents: Mapping[ast.AST, ast.AST],
) -> bool:
    for ancestor in _iter_ancestors(node, parents):
        if isinstance(ancestor, ast.Compare):
            return True
        if isinstance(ancestor, ast.Call) and _is_matching_call(ancestor):
            return True
        if MATCH_PATTERN_NODES and isinstance(ancestor, MATCH_PATTERN_NODES):
            return True
    return False


def _scan_string_literal_node(
    path: Path,
    root: Path,
    mapping: Mapping[str, str],
    node: ast.Constant,
) -> list[Finding]:
    if not isinstance(node.value, str):
        return []
    base_line = node.lineno
    base_col = node.col_offset + 1
    findings: list[Finding] = []
    for offset, line in enumerate(node.value.splitlines() or [""]):
        if not line:
            continue
        line_number = base_line + offset
        column = base_col if offset == 0 else 1
        findings.extend(_scan_text_line(path, root, mapping, line_number, line, column))
    return findings


def _scan_python_file(path: Path, root: Path, mapping: Mapping[str, str]) -> list[Finding]:
    source = path.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    docstring_starts = _docstring_positions(tree)
    parents = _build_parent_map(tree)
    findings: list[Finding] = []
    findings.extend(_scan_python_identifiers(path, root, mapping, source_lines, tree))
    findings.extend(
        _scan_python_comments_and_docstrings(
            path,
            root,
            mapping,
            source,
            source_lines,
            docstring_starts,
        )
    )
    relative_path = path.relative_to(root)
    scan_string_literals = not (relative_path.parts and relative_path.parts[0] == "tests")
    if scan_string_literals:
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if (node.lineno, node.col_offset) in docstring_starts:
                    continue
                if _is_external_comparison_literal(node, parents):
                    continue
                findings.extend(_scan_string_literal_node(path, root, mapping, node))
    return findings


def _scan_text_file(path: Path, root: Path, mapping: Mapping[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    content = path.read_text(encoding="utf-8")
    in_code_block = False
    for line_number, line in enumerate(content.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        findings.extend(_scan_text_line(path, root, mapping, line_number, line))
    return findings


def _scan_file(path: Path, root: Path, mapping: Mapping[str, str]) -> list[Finding]:
    if path.suffix == ".py":
        return _scan_python_file(path, root, mapping)
    return _scan_text_file(path, root, mapping)


def scan_repo(config: SpellingConfig, mapping: Mapping[str, str]) -> ScanResult:
    all_findings: list[Finding] = []
    files_scanned = 0
    for path in _iter_files(config):
        files_scanned += 1
        all_findings.extend(_scan_file(path, config.root, mapping))
    return ScanResult(findings=tuple(all_findings), files_scanned=files_scanned)


def _render_findings(findings: Sequence[Finding]) -> list[str]:
    grouped: dict[Path, list[Finding]] = defaultdict(list)
    for finding in findings:
        grouped[finding.path].append(finding)

    lines: list[str] = []
    for path in sorted(grouped.keys(), key=lambda value: value.as_posix()):
        lines.append(path.as_posix())
        for finding in grouped[path]:
            loc = f"{finding.line_number}:{finding.column_number}"
            lines.append(f"  {loc} {finding.word} -> {finding.suggestion}")
    return lines


def _render_summary(findings: Sequence[Finding]) -> str:
    seen: set[tuple[str, str]] = set()
    parts: list[str] = []
    for finding in findings:
        key = (finding.word.lower(), finding.suggestion.lower())
        if key in seen:
            continue
        seen.add(key)
        parts.append(f"{finding.word} -> {finding.suggestion}")
    return ", ".join(parts)


def render_report(
    result: ScanResult,
    mapping: Mapping[str, str],
    include_list: bool,
) -> str:
    lines: list[str] = []
    if result.findings:
        count = len(result.findings)
        file_count = len({finding.path for finding in result.findings})
        msg = f"American spellings found: {count} occurrence(s) in {file_count} file(s)."
        lines.append(msg)
        summary = _render_summary(result.findings)
        if summary:
            lines.append(f"Detected US spellings: {summary}")
        lines.append("")
        lines.extend(_render_findings(result.findings))
    else:
        lines.append("No American spellings found.")

    if include_list:
        lines.append("")
        lines.append(f"US -> UK list ({len(mapping)} entries):")
        for us_word, uk_word in sorted(mapping.items(), key=lambda item: item[0]):
            lines.append(f"{us_word} -> {uk_word}")

    return "\n".join(lines).rstrip() + "\n"


def _is_list_of_objects(value: object) -> TypeGuard[list[object]]:
    """Type guard that narrows object to list[object]."""
    return isinstance(value, list)


def _is_dict_of_objects(value: object) -> TypeGuard[dict[object, object]]:
    """Type guard that narrows object to dict[object, object]."""
    return isinstance(value, dict)


def _ensure_str_list(value: object, name: str) -> list[str]:
    """Validate and convert an object to a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        msg = f"{name} must be a list"
        raise TypeError(msg)
    if not _is_list_of_objects(value):
        msg = f"{name} must be a list"
        raise TypeError(msg)
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            msg = f"{name} items must be strings"
            raise TypeError(msg)
        result.append(item)
    return result


def _as_str_object_dict(value: object) -> dict[str, object] | None:
    """Narrow a value to dict[str, object] if possible."""
    if value is None:
        return None
    if not _is_dict_of_objects(value):
        return None
    result: dict[str, object] = {}
    for key in value:
        if not isinstance(key, str):
            return None
        result[key] = value[key]
    return result


def _ensure_bool(value: object, name: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        msg = f"{name} must be boolean"
        raise TypeError(msg)
    return value


def _build_mapping(base_mapping: Mapping[str, str]) -> dict[str, str]:
    filtered: dict[str, str] = {}
    for us_word, uk_word in base_mapping.items():
        if any(us_word.startswith(prefix) for prefix in EXCLUDED_US_SPELLINGS):
            continue
        filtered[us_word] = uk_word
    return filtered


def load_config(root: Path) -> SpellingConfig:
    pyproject_path = root / "pyproject.toml"

    # Default configuration
    default_include_extensions: list[str] = [".py", ".md", ".txt"]
    default_exclude_dirs: list[str] = [
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    ]
    default_exclude_files: list[str] = []
    default_include_list: bool = False

    # Parse pyproject.toml if it exists
    raw_include_extensions: object = None
    raw_exclude_dirs: object = None
    raw_exclude_files: object = None
    raw_include_list: object = None

    if pyproject_path.exists():
        try:
            data: dict[str, object] = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            tool_table = _as_str_object_dict(data.get("tool"))
            if tool_table is not None:
                spelling_table = _as_str_object_dict(tool_table.get("us_spelling"))
                if spelling_table is not None:
                    raw_include_extensions = spelling_table.get("include_extensions")
                    raw_exclude_dirs = spelling_table.get("exclude_dirs")
                    raw_exclude_files = spelling_table.get("exclude_files")
                    raw_include_list = spelling_table.get("include_list")
        except (OSError, tomllib.TOMLDecodeError, KeyError):
            pass  # Fallback to defaults on any parse error

    if raw_include_extensions is None:
        include_extensions = default_include_extensions
    else:
        include_extensions = _ensure_str_list(raw_include_extensions, "include_extensions")

    if raw_exclude_dirs is None:
        exclude_dirs = default_exclude_dirs
    else:
        exclude_dirs = _ensure_str_list(raw_exclude_dirs, "exclude_dirs")

    if raw_exclude_files is None:
        exclude_files = default_exclude_files
    else:
        exclude_files = _ensure_str_list(raw_exclude_files, "exclude_files")

    if raw_include_list is None:
        include_list = default_include_list
    else:
        include_list = _ensure_bool(raw_include_list, "include_list", default_include_list)

    return SpellingConfig(
        root=root,
        include_extensions=tuple(include_extensions),
        exclude_dirs=tuple(exclude_dirs),
        exclude_files=tuple(exclude_files),
        include_list=include_list,
    )


def run(
    config: SpellingConfig,
    mapping: Mapping[str, str],
    output: TextIO,
) -> int:
    result = scan_repo(config, mapping)
    report = render_report(result, mapping, config.include_list)
    output.write(report)
    return 1 if result.findings else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan for American spellings and report British suggestions.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_root_dir(),
        help="Repository root to scan (default: repo root).",
    )
    parser.add_argument(
        "--no-list",
        action="store_true",
        help="Do not include the US -> UK reference list in the report.",
    )

    args = parser.parse_args(argv)
    config = load_config(args.root)
    mapping = _build_mapping(AMERICAN_ENGLISH_SPELLINGS)
    if args.no_list:
        config = SpellingConfig(
            root=config.root,
            include_extensions=config.include_extensions,
            exclude_dirs=config.exclude_dirs,
            exclude_files=config.exclude_files,
            include_list=False,
        )
    return run(config, mapping, sys.stdout)


US_UK_MAPPING = _build_mapping(AMERICAN_ENGLISH_SPELLINGS)


if __name__ == "__main__":
    raise SystemExit(main())
