"""Tests for CLI wiring and overrides."""

from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from uk_sponsor_pipeline import cli
from uk_sponsor_pipeline.config import PipelineConfig

runner = CliRunner()


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
        scored_path: str, out_dir: str, config: PipelineConfig
    ) -> dict[str, str]:
        captured["config"] = config
        return {"shortlist": "short.csv", "explain": "explain.csv"}

    monkeypatch.setattr(cli, "run_usage_shortlist", fake_run_usage_shortlist)

    result = runner.invoke(
        cli.app,
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

    result = runner.invoke(
        cli.app,
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
        raise AssertionError("extract_register should not be called")

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )
    monkeypatch.setattr(cli, "extract_register", fail_download)
    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)

    result = runner.invoke(cli.app, ["run-all", "--skip-download"])

    assert result.exit_code == 0
    assert calls["skip_download"] is True
