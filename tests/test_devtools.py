"""Tests for devtools entrypoints."""

from types import SimpleNamespace

import pytest

from uk_sponsor_pipeline import devtools


def _capture_run(monkeypatch):
    calls = []

    def fake_run(args, check=False):
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(devtools.subprocess, "run", fake_run)
    return calls


def _assert_exit_ok(exc_info):
    assert exc_info.value.code == 0


def test_lint_calls_ruff(monkeypatch):
    calls = _capture_run(monkeypatch)
    monkeypatch.setattr(devtools.sys, "argv", ["devtools", "--select", "E"])
    with pytest.raises(SystemExit) as exc_info:
        devtools.lint()
    _assert_exit_ok(exc_info)
    assert calls[0][:4] == ["ruff", "check", "src", "tests"]


def test_format_calls_ruff(monkeypatch):
    calls = _capture_run(monkeypatch)
    monkeypatch.setattr(devtools.sys, "argv", ["devtools", "--line-length", "100"])
    with pytest.raises(SystemExit) as exc_info:
        devtools.format_code()
    _assert_exit_ok(exc_info)
    assert calls[0][:3] == ["ruff", "format", "src"]


def test_format_check_calls_ruff(monkeypatch):
    calls = _capture_run(monkeypatch)
    monkeypatch.setattr(devtools.sys, "argv", ["devtools"])
    with pytest.raises(SystemExit) as exc_info:
        devtools.format_check()
    _assert_exit_ok(exc_info)
    assert calls[0][:4] == ["ruff", "format", "--check", "src"]


def test_typecheck_calls_mypy(monkeypatch):
    calls = _capture_run(monkeypatch)
    monkeypatch.setattr(devtools.sys, "argv", ["devtools"])
    with pytest.raises(SystemExit) as exc_info:
        devtools.typecheck()
    _assert_exit_ok(exc_info)
    assert calls[0][:2] == ["mypy", "src"]


def test_test_calls_pytest(monkeypatch):
    calls = _capture_run(monkeypatch)
    monkeypatch.setattr(devtools.sys, "argv", ["devtools", "-q"])
    with pytest.raises(SystemExit) as exc_info:
        devtools.test()
    _assert_exit_ok(exc_info)
    assert calls[0][0] == "pytest"


def test_coverage_calls_pytest(monkeypatch):
    calls = _capture_run(monkeypatch)
    monkeypatch.setattr(devtools.sys, "argv", ["devtools"])
    with pytest.raises(SystemExit) as exc_info:
        devtools.coverage()
    _assert_exit_ok(exc_info)
    assert calls[0][:2] == ["pytest", "--cov=uk_sponsor_pipeline"]
    assert "--cov-fail-under=85" in calls[0]


def test_check_runs_quality_gates_in_order(monkeypatch):
    calls = _capture_run(monkeypatch)
    emitted = []
    monkeypatch.setattr(devtools, "_emit", lambda msg: emitted.append(msg))
    with pytest.raises(SystemExit) as exc_info:
        devtools.check()
    _assert_exit_ok(exc_info)
    assert calls == [
        ["ruff", "format", "src", "tests"],
        ["mypy", "src"],
        ["ruff", "check", "src", "tests"],
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


def test_check_stops_on_first_error(monkeypatch):
    calls = []
    returncodes = [0, 3]
    emitted = []

    def fake_run(args, check=False):
        calls.append(args)
        code = returncodes.pop(0) if returncodes else 0
        return SimpleNamespace(returncode=code)

    monkeypatch.setattr(devtools.subprocess, "run", fake_run)
    monkeypatch.setattr(devtools, "_emit", lambda msg: emitted.append(msg))

    with pytest.raises(SystemExit) as exc_info:
        devtools.check()

    assert exc_info.value.code == 3
    assert calls == [
        ["ruff", "format", "src", "tests"],
        ["mypy", "src"],
    ]
    assert any("✗ typecheck failed" in msg for msg in emitted)
