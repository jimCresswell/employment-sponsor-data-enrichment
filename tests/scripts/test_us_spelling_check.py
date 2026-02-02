"""Tests for American spelling scan utility."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pytest

from scripts.check_us_spelling import US_UK_MAPPING, SpellingConfig, run, scan_repo


@dataclass(frozen=True)
class _Sample:
    path: Path
    content: str


def _write_sample(tmp_path: Path, name: str, content: str) -> _Sample:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return _Sample(path=path, content=content)


def _config(root: Path) -> SpellingConfig:
    return SpellingConfig(
        root=root,
        include_extensions=(".md", ".txt"),
        exclude_dirs=(),
        exclude_files=(),
        include_list=True,
    )


def _pair_for_uk(uk_word: str) -> tuple[str, str]:
    for us_word, mapped_uk in US_UK_MAPPING.items():
        if mapped_uk == uk_word:
            return us_word, mapped_uk
    pytest.fail(f"Missing mapping for {uk_word}")


def test_scan_detects_american_spellings(tmp_path: Path) -> None:
    us_centre, _ = _pair_for_uk("centre")
    us_colourize, _ = _pair_for_uk("colourize")
    _write_sample(tmp_path, "sample.md", f"{us_centre.title()} {us_colourize}.\n")
    config = _config(tmp_path)

    result = scan_repo(config, US_UK_MAPPING)

    assert result.files_scanned == 1
    words = {(finding.word, finding.suggestion) for finding in result.findings}
    assert (us_centre.title(), "Centre") in words
    assert (us_colourize, "colourize") in words


def test_run_returns_non_zero_with_findings(tmp_path: Path) -> None:
    us_colour, _ = _pair_for_uk("colour")
    us_centre, _ = _pair_for_uk("centre")
    _write_sample(tmp_path, "sample.txt", f"{us_colour.title()} {us_centre}.\n")
    config = _config(tmp_path)
    buffer = StringIO()

    exit_code = run(config, US_UK_MAPPING, buffer)

    assert exit_code == 1
    output = buffer.getvalue()
    assert us_colour.title() in output
    assert "centre" in output.lower()


def test_report_includes_reference_list(tmp_path: Path) -> None:
    _write_sample(tmp_path, "sample.txt", "No changes here.\n")
    config = _config(tmp_path)
    buffer = StringIO()

    exit_code = run(config, US_UK_MAPPING, buffer)

    assert exit_code == 0
    output = buffer.getvalue()
    assert "US -> UK list" in output
    us_word, _ = _pair_for_uk("accessorise")
    assert f"{us_word} -> accessorise" in output


def test_python_scan_checks_string_literals_except_comparisons(tmp_path: Path) -> None:
    us_organisation, _ = _pair_for_uk("organisation")
    us_colourize, _ = _pair_for_uk("colourize")
    us_authorised, _ = _pair_for_uk("authorised")
    source = (
        "import re\n\n"
        f"def {us_organisation}_data() -> None:\n"
        f'    note = "{us_colourize.title()}"\n'
        f'    if status == "{us_authorised}":\n'
        "        pass\n"
        f'    if status in ["{us_authorised}"]:\n'
        "        pass\n"
        f'    if status.startswith("{us_authorised}"):\n'
        "        pass\n"
        f'    if re.search("{us_authorised}", status):\n'
        "        pass\n"
        "    match status:\n"
        f'        case "{us_authorised}":\n'
        "            pass\n"
        "    return None\n"
    )
    _write_sample(tmp_path, "sample.py", source)
    config = SpellingConfig(
        root=tmp_path,
        include_extensions=(".py",),
        exclude_dirs=(),
        exclude_files=(),
        include_list=False,
    )

    result = scan_repo(config, US_UK_MAPPING)

    words = {finding.word for finding in result.findings}
    assert us_organisation in words
    assert us_colourize.title() in words
    assert us_authorised not in words
