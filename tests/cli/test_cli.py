"""Tests for CLI wiring and overrides."""

from pathlib import Path
from types import SimpleNamespace
from typing import override

import pytest
import typer
from typer.testing import CliRunner

from tests.fakes import InMemoryFileSystem
from uk_sponsor_pipeline import cli
from uk_sponsor_pipeline.cli import CliDependencies
from uk_sponsor_pipeline.config import PipelineConfig
from uk_sponsor_pipeline.protocols import FileSystem, HttpSession

runner = CliRunner()


class DummySession(HttpSession):
    """HTTP session stub for CLI tests."""

    @override
    def get_text(self, url: str, *, timeout_seconds: float) -> str:
        pytest.fail(f"Unexpected HTTP request to {url}")

    @override
    def get_bytes(self, url: str, *, timeout_seconds: float) -> bytes:
        pytest.fail(f"Unexpected HTTP request to {url}")


def _fake_cli_dependencies() -> CliDependencies:
    return CliDependencies(
        fs=InMemoryFileSystem(),
        http_session=DummySession(),
        http_client=None,
    )


def _build_cli_dependencies(
    *,
    config: PipelineConfig,
    cache_dir: str | Path,
    build_http_client: bool = False,
) -> CliDependencies:
    _ = (config, cache_dir, build_http_client)
    return _fake_cli_dependencies()


def _build_app() -> typer.Typer:
    return cli.create_app(_build_cli_dependencies)


def test_cli_usage_shortlist_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, PipelineConfig] = {}

    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    def fake_run_usage_shortlist(
        scored_path: str | Path,
        out_dir: str | Path,
        config: PipelineConfig,
        fs: FileSystem,
    ) -> dict[str, str]:
        captured["config"] = config
        return {"shortlist": "short.csv", "explain": "explain.csv"}

    monkeypatch.setattr(cli, "run_usage_shortlist", fake_run_usage_shortlist)

    app = _build_app()
    result = runner.invoke(
        app,
        [
            "usage-shortlist",
            "--threshold",
            "0.4",
            "--region",
            "London",
            "--postcode-prefix",
            "EC",
        ],
    )

    assert result.exit_code == 0
    assert captured["config"].tech_score_threshold == 0.4
    assert captured["config"].geo_filter_region == "London"
    assert captured["config"].geo_filter_postcodes == ("EC",)


def test_cli_usage_shortlist_rejects_multiple_regions(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    app = _build_app()
    result = runner.invoke(
        app,
        ["usage-shortlist", "--region", "London", "--region", "Leeds"],
    )

    assert result.exit_code != 0
    assert "Only one --region" in result.output


def test_cli_run_all_skip_download(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_run_pipeline(**kwargs: object) -> SimpleNamespace:
        calls.update(kwargs)
        return SimpleNamespace(
            extract=None,
            register=SimpleNamespace(unique_orgs=1),
            enrich={"enriched": "enriched.csv"},
            score={"scored": "scored.csv"},
            usage={"shortlist": "short.csv", "explain": "explain.csv"},
        )

    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    def fail_download(*args: object, **kwargs: object) -> None:
        pytest.fail("extract_register should not be called")

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )
    monkeypatch.setattr(cli, "extract_register", fail_download)
    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)

    app = _build_app()
    result = runner.invoke(app, ["run-all", "--skip-download"])

    assert result.exit_code == 0
    assert calls["skip_download"] is True
