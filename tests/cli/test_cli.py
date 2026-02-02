"""Tests for CLI wiring and overrides."""

from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from uk_sponsor_pipeline import cli
from uk_sponsor_pipeline.config import PipelineConfig

runner = CliRunner()


def test_cli_stage3_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, PipelineConfig] = {}

    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    def fake_run_stage3(stage2_path: str, out_dir: str, config: PipelineConfig) -> dict[str, str]:
        captured["config"] = config
        return {"scored": "scored.csv", "shortlist": "short.csv", "explain": "explain.csv"}

    monkeypatch.setattr(cli, "run_stage3", fake_run_stage3)

    result = runner.invoke(
        cli.app,
        [
            "stage3",
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


def test_cli_stage3_rejects_multiple_regions(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    result = runner.invoke(cli.app, ["stage3", "--region", "London", "--region", "Leeds"])

    assert result.exit_code != 0
    assert "Only one --region" in result.output


def test_cli_run_all_skip_download(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"stage1": 0, "stage2": 0, "stage3": 0}

    def fake_stage1(*args: object, **kwargs: object) -> SimpleNamespace:
        calls["stage1"] += 1
        return SimpleNamespace(unique_orgs=1)

    def fake_stage2(*args: object, **kwargs: object) -> dict[str, str]:
        calls["stage2"] += 1
        return {"enriched": "enriched.csv"}

    def fake_stage3(*args: object, **kwargs: object) -> dict[str, str]:
        calls["stage3"] += 1
        return {"shortlist": "short.csv", "explain": "explain.csv"}

    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    def fail_download(*args: object, **kwargs: object) -> None:
        raise AssertionError("download_latest should not be called")

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )
    monkeypatch.setattr(cli, "download_latest", fail_download)
    monkeypatch.setattr(cli, "run_stage1", fake_stage1)
    monkeypatch.setattr(cli, "run_stage2", fake_stage2)
    monkeypatch.setattr(cli, "run_stage3", fake_stage3)

    result = runner.invoke(cli.app, ["run-all", "--skip-download"])

    assert result.exit_code == 0
    assert calls == {"stage1": 1, "stage2": 1, "stage3": 1}
