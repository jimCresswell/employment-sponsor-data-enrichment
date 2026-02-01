"""Tests for shared observability logging."""

import logging
import time

import pytest

from uk_sponsor_pipeline.observability.logging import get_logger


def test_get_logger_formats_utc_timestamps(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fixed = time.struct_time((2020, 1, 2, 3, 4, 5, 3, 2, 0))

    def fake_gmtime(_: float | None = None) -> time.struct_time:
        return fixed

    monkeypatch.setattr(time, "gmtime", fake_gmtime)

    name = "uk_sponsor_pipeline.test.logging"
    logger = get_logger(name)
    logger.info("Hello")

    captured = capsys.readouterr()
    assert "2020-01-02T03:04:05+0000 INFO uk_sponsor_pipeline.test.logging: Hello" in captured.err


def test_get_logger_is_singleton_per_name() -> None:
    name = "uk_sponsor_pipeline.test.logging.singleton"
    logger = get_logger(name)
    logger_again = get_logger(name)

    assert logger is logger_again
    assert len(logger.handlers) == 1
    assert logger.level == logging.INFO
