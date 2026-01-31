"""Tests for CLI wiring and overrides."""

from types import SimpleNamespace

from typer.testing import CliRunner

from uk_sponsor_pipeline import cli
from uk_sponsor_pipeline.config import PipelineConfig

runner = CliRunner()


def test_cli_stage3_overrides(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(lambda cls, dotenv_path=None: PipelineConfig()),
    )

    def fake_run_stage3(stage2_path, out_dir, config):
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
    assert captured["config"].geo_filter_regions == ("London",)
    assert captured["config"].geo_filter_postcodes == ("EC",)


def test_cli_run_all_skip_download(monkeypatch):
    calls = {"stage1": 0, "stage2": 0, "stage3": 0}

    def fake_stage1(*args, **kwargs):
        calls["stage1"] += 1
        return SimpleNamespace(unique_orgs=1)

    def fake_stage2(*args, **kwargs):
        calls["stage2"] += 1
        return {"enriched": "enriched.csv"}

    def fake_stage3(*args, **kwargs):
        calls["stage3"] += 1
        return {"shortlist": "short.csv", "explain": "explain.csv"}

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(lambda cls, dotenv_path=None: PipelineConfig()),
    )
    monkeypatch.setattr(
        cli,
        "download_latest",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("download_latest should not be called")
        ),
    )
    monkeypatch.setattr(cli, "run_stage1", fake_stage1)
    monkeypatch.setattr(cli, "run_stage2", fake_stage2)
    monkeypatch.setattr(cli, "run_stage3", fake_stage3)

    result = runner.invoke(cli.app, ["run-all", "--skip-download"])

    assert result.exit_code == 0
    assert calls == {"stage1": 1, "stage2": 1, "stage3": 1}
