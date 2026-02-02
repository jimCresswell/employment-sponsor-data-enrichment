"""Tests for CLI wiring and overrides."""

from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from uk_sponsor_pipeline import cli
from uk_sponsor_pipeline.config import PipelineConfig

runner = CliRunner()


def test_cli_transform_score_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, PipelineConfig] = {}

    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    def fake_run_transform_score(
        enriched_path: str, out_dir: str, config: PipelineConfig
    ) -> dict[str, str]:
        captured["config"] = config
        return {"scored": "scored.csv", "shortlist": "short.csv", "explain": "explain.csv"}

    monkeypatch.setattr(cli, "run_transform_score", fake_run_transform_score)

    result = runner.invoke(
        cli.app,
        [
            "transform-score",
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


def test_cli_transform_score_rejects_multiple_regions(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    result = runner.invoke(cli.app, ["transform-score", "--region", "London", "--region", "Leeds"])

    assert result.exit_code != 0
    assert "Only one --region" in result.output


def test_cli_run_all_skip_download(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"transform_register": 0, "transform_enrich": 0, "transform_score": 0}

    def fake_transform_register(*args: object, **kwargs: object) -> SimpleNamespace:
        calls["transform_register"] += 1
        return SimpleNamespace(unique_orgs=1)

    def fake_transform_enrich(*args: object, **kwargs: object) -> dict[str, str]:
        calls["transform_enrich"] += 1
        return {"enriched": "enriched.csv"}

    def fake_transform_score(*args: object, **kwargs: object) -> dict[str, str]:
        calls["transform_score"] += 1
        return {"shortlist": "short.csv", "explain": "explain.csv"}

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
    monkeypatch.setattr(cli, "run_transform_register", fake_transform_register)
    monkeypatch.setattr(cli, "run_transform_enrich", fake_transform_enrich)
    monkeypatch.setattr(cli, "run_transform_score", fake_transform_score)

    result = runner.invoke(cli.app, ["run-all", "--skip-download"])

    assert result.exit_code == 0
    assert calls == {"transform_register": 1, "transform_enrich": 1, "transform_score": 1}
