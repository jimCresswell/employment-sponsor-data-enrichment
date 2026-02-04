"""Tests for devtools entrypoints."""

from types import SimpleNamespace

import pytest

from uk_sponsor_pipeline import devtools


def _capture_run(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(args: list[str], check: bool = False) -> SimpleNamespace:
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(devtools.subprocess, "run", fake_run)
    return calls


def _assert_exit_ok(exc_info: pytest.ExceptionInfo[SystemExit]) -> None:
    assert exc_info.value.code == 0


def test_lint_calls_ruff(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_run(monkeypatch)
    monkeypatch.setattr(devtools.sys, "argv", ["devtools", "--select", "E"])
    with pytest.raises(SystemExit) as exc_info:
        devtools.lint()
    _assert_exit_ok(exc_info)
    assert calls[0][:5] == ["ruff", "check", "src", "tests", "--ignore-noqa"]
    assert calls[1] == [devtools.sys.executable, "scripts/check_inline_ignores.py"]
    assert calls[2] == [
        devtools.sys.executable,
        "-m",
        "uk_sponsor_pipeline.devtools.uwotm8_linter",
        "--no-list",
    ]
    assert calls[3] == ["lint-imports"]


def test_format_calls_ruff(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_run(monkeypatch)
    monkeypatch.setattr(devtools.sys, "argv", ["devtools", "--line-length", "100"])
    with pytest.raises(SystemExit) as exc_info:
        devtools.format_code()
    _assert_exit_ok(exc_info)
    assert calls[0][:3] == ["ruff", "format", "src"]


def test_format_check_calls_ruff(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_run(monkeypatch)
    monkeypatch.setattr(devtools.sys, "argv", ["devtools"])
    with pytest.raises(SystemExit) as exc_info:
        devtools.format_check()
    _assert_exit_ok(exc_info)
    assert calls[0][:4] == ["ruff", "format", "--check", "src"]


def test_typecheck_calls_pyright(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_run(monkeypatch)
    monkeypatch.setattr(devtools.sys, "argv", ["devtools"])
    with pytest.raises(SystemExit) as exc_info:
        devtools.typecheck()
    _assert_exit_ok(exc_info)
    assert calls[0][0] == "pyright"


def test_test_calls_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_run(monkeypatch)
    monkeypatch.setattr(devtools.sys, "argv", ["devtools", "-q"])
    with pytest.raises(SystemExit) as exc_info:
        devtools.test()
    _assert_exit_ok(exc_info)
    assert calls[0][0] == "pytest"


def test_coverage_calls_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_run(monkeypatch)
    monkeypatch.setattr(devtools.sys, "argv", ["devtools"])
    with pytest.raises(SystemExit) as exc_info:
        devtools.coverage()
    _assert_exit_ok(exc_info)
    assert calls[0][:2] == ["pytest", "--cov=uk_sponsor_pipeline"]
    assert "--cov-fail-under=85" in calls[0]


def test_spelling_check_calls_script(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_run(monkeypatch)
    monkeypatch.setattr(devtools.sys, "argv", ["devtools"])
    with pytest.raises(SystemExit) as exc_info:
        devtools.spelling_check()
    _assert_exit_ok(exc_info)
    assert calls[0] == [
        devtools.sys.executable,
        "-m",
        "uk_sponsor_pipeline.devtools.uwotm8_linter",
    ]


def test_check_runs_quality_gates_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_run(monkeypatch)
    emitted: list[str] = []

    def emit(msg: str) -> None:
        emitted.append(msg)

    monkeypatch.setattr(devtools, "_emit", emit)
    with pytest.raises(SystemExit) as exc_info:
        devtools.check()
    _assert_exit_ok(exc_info)
    assert calls == [
        ["ruff", "format", "src", "tests"],
        ["pyright"],
        ["ruff", "check", "src", "tests", "--ignore-noqa"],
        [devtools.sys.executable, "scripts/check_inline_ignores.py"],
        [
            devtools.sys.executable,
            "-m",
            "uk_sponsor_pipeline.devtools.uwotm8_linter",
            "--no-list",
        ],
        ["lint-imports"],
        ["pytest"],
        [
            "pytest",
            "--cov=uk_sponsor_pipeline",
            "--cov-report=term-missing",
            "--cov-fail-under=85",
        ],
    ]
    assert any("→ format" in msg for msg in emitted)
    assert any("✓ format" in msg for msg in emitted)
    assert "All checks passed" in emitted[-1]


def test_check_stops_on_first_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    returncodes = [0, 3]
    emitted: list[str] = []

    def fake_run(args: list[str], check: bool = False) -> SimpleNamespace:
        calls.append(args)
        code = returncodes.pop(0) if returncodes else 0
        return SimpleNamespace(returncode=code)

    def emit(msg: str) -> None:
        emitted.append(msg)

    monkeypatch.setattr(devtools.subprocess, "run", fake_run)
    monkeypatch.setattr(devtools, "_emit", emit)

    with pytest.raises(SystemExit) as exc_info:
        devtools.check()

    assert exc_info.value.code == 3
    assert calls == [
        ["ruff", "format", "src", "tests"],
        ["pyright"],
    ]
    assert any("✗ typecheck failed" in msg for msg in emitted)
