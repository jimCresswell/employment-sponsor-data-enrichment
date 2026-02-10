"""Tests for CLI wiring and overrides."""

import re
from collections.abc import Iterable
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
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text)


class DummySession(HttpSession):
    """HTTP session stub for CLI tests."""

    @override
    def get_text(self, url: str, *, timeout_seconds: float) -> str:
        pytest.fail(f"Unexpected HTTP request to {url}")

    @override
    def get_bytes(self, url: str, *, timeout_seconds: float) -> bytes:
        pytest.fail(f"Unexpected HTTP request to {url}")

    @override
    def iter_bytes(
        self,
        url: str,
        *,
        timeout_seconds: float,
        chunk_size: int,
    ) -> Iterable[bytes]:
        _ = (timeout_seconds, chunk_size)
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


def _build_app_with_dependencies(deps: CliDependencies) -> typer.Typer:
    def build_with_shared_deps(
        *,
        config: PipelineConfig,
        cache_dir: str | Path,
        build_http_client: bool = False,
    ) -> CliDependencies:
        _ = (config, cache_dir, build_http_client)
        return deps

    return cli.create_app(build_with_shared_deps)


def test_cli_version_option_prints_package_version(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        _ = (cls, dotenv_path)
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )
    monkeypatch.setattr(cli, "__version__", "9.9.9", raising=False)

    app = _build_app()
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    plain_output = _strip_ansi(result.output)
    assert "9.9.9" in plain_output


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


def test_cli_transform_score_overrides_profile_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, PipelineConfig] = {}

    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        _ = (cls, dotenv_path)
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    def fake_run_transform_score(
        *,
        enriched_path: str | Path,
        out_dir: str | Path,
        config: PipelineConfig,
        fs: FileSystem,
    ) -> dict[str, Path]:
        _ = (enriched_path, out_dir, fs)
        captured["config"] = config
        return {"scored": Path("companies_scored.csv")}

    monkeypatch.setattr(cli, "run_transform_score", fake_run_transform_score)

    app = _build_app()
    result = runner.invoke(
        app,
        [
            "transform-score",
            "--sector-profile",
            "data/reference/scoring_profiles.json",
            "--sector",
            "tech",
        ],
    )

    assert result.exit_code == 0
    assert captured["config"].sector_profile_path == "data/reference/scoring_profiles.json"
    assert captured["config"].sector_name == "tech"


def test_cli_global_config_file_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, PipelineConfig] = {}
    fs = InMemoryFileSystem()
    fs.write_text(
        """
schema_version = 1
[pipeline]
tech_score_threshold = 0.4
geo_filter_region = "Manchester"
geo_filter_postcodes = ["M"]
""".strip(),
        Path("config/pipeline.toml"),
    )

    deps = CliDependencies(fs=fs, http_session=DummySession(), http_client=None)

    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        _ = (cls, dotenv_path)
        return PipelineConfig(
            tech_score_threshold=0.9,
            geo_filter_region="London",
            geo_filter_postcodes=("EC",),
        )

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    def fake_run_usage_shortlist(
        *,
        scored_path: str | Path,
        out_dir: str | Path,
        config: PipelineConfig,
        fs: FileSystem,
    ) -> dict[str, Path]:
        _ = (scored_path, out_dir, fs)
        captured["config"] = config
        return {"shortlist": Path("short.csv"), "explain": Path("explain.csv")}

    monkeypatch.setattr(cli, "run_usage_shortlist", fake_run_usage_shortlist)

    app = _build_app_with_dependencies(deps)
    result = runner.invoke(
        app,
        ["--config", "config/pipeline.toml", "usage-shortlist"],
    )

    assert result.exit_code == 0
    assert captured["config"].tech_score_threshold == 0.4
    assert captured["config"].geo_filter_region == "Manchester"
    assert captured["config"].geo_filter_postcodes == ("M",)


def test_cli_global_config_file_values_can_be_overridden_by_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, PipelineConfig] = {}
    fs = InMemoryFileSystem()
    fs.write_text(
        """
schema_version = 1
[pipeline]
tech_score_threshold = 0.4
geo_filter_region = "Manchester"
geo_filter_postcodes = ["M"]
""".strip(),
        Path("config/pipeline.toml"),
    )

    deps = CliDependencies(fs=fs, http_session=DummySession(), http_client=None)

    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        _ = (cls, dotenv_path)
        return PipelineConfig(
            tech_score_threshold=0.9,
            geo_filter_region="London",
            geo_filter_postcodes=("EC",),
        )

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    def fake_run_usage_shortlist(
        *,
        scored_path: str | Path,
        out_dir: str | Path,
        config: PipelineConfig,
        fs: FileSystem,
    ) -> dict[str, Path]:
        _ = (scored_path, out_dir, fs)
        captured["config"] = config
        return {"shortlist": Path("short.csv"), "explain": Path("explain.csv")}

    monkeypatch.setattr(cli, "run_usage_shortlist", fake_run_usage_shortlist)

    app = _build_app_with_dependencies(deps)
    result = runner.invoke(
        app,
        [
            "--config",
            "config/pipeline.toml",
            "usage-shortlist",
            "--threshold",
            "0.3",
            "--region",
            "Bristol",
            "--postcode-prefix",
            "BS",
        ],
    )

    assert result.exit_code == 0
    assert captured["config"].tech_score_threshold == 0.3
    assert captured["config"].geo_filter_region == "Bristol"
    assert captured["config"].geo_filter_postcodes == ("BS",)


def test_cli_global_config_file_missing_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    deps = CliDependencies(
        fs=InMemoryFileSystem(),
        http_session=DummySession(),
        http_client=None,
    )

    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        _ = (cls, dotenv_path)
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    app = _build_app_with_dependencies(deps)
    result = runner.invoke(
        app,
        ["--config", "config/missing.toml", "usage-shortlist"],
    )

    assert result.exit_code != 0
    plain_output = _strip_ansi(result.output)
    assert "Config file not found" in plain_output


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
    plain_output = _strip_ansi(result.output)
    assert "Only one" in plain_output
    assert "region" in plain_output
    assert "value is supported." in plain_output


def test_cli_run_all_rejects_multiple_regions(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        _ = (cls, dotenv_path)
        return PipelineConfig(ch_source_type="file")

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    app = _build_app()
    result = runner.invoke(
        app,
        ["run-all", "--region", "London", "--region", "Leeds"],
    )

    assert result.exit_code != 0
    plain_output = _strip_ansi(result.output)
    assert "Only one" in plain_output
    assert "region" in plain_output
    assert "value is supported." in plain_output


def test_cli_run_all_resolves_snapshot_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_config = PipelineConfig()
    captured_register_path = Path("unset")

    def fake_run_transform_enrich(
        *,
        register_path: Path,
        out_dir: str | Path,
        cache_dir: str | Path,
        config: PipelineConfig,
        http_client: object | None,
        fs: FileSystem,
        resume: bool = True,
        batch_start: int = 1,
        batch_count: int | None = None,
        batch_size: int | None = None,
    ) -> dict[str, Path]:
        nonlocal captured_config, captured_register_path
        _ = (out_dir, cache_dir, fs, http_client, resume, batch_start, batch_count, batch_size)
        captured_config = config
        captured_register_path = register_path
        return {"enriched": Path("enriched.csv")}

    def fake_run_transform_score(
        *,
        enriched_path: str | Path,
        out_dir: str | Path,
        config: PipelineConfig,
        fs: FileSystem,
    ) -> dict[str, Path]:
        _ = (enriched_path, out_dir, config, fs)
        return {"scored": Path("scored.csv")}

    def fake_run_usage_shortlist(
        *,
        scored_path: str | Path,
        out_dir: str | Path,
        config: PipelineConfig,
        fs: FileSystem,
    ) -> dict[str, Path]:
        _ = (scored_path, out_dir, config, fs)
        return {"shortlist": Path("short.csv"), "explain": Path("explain.csv")}

    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig(ch_source_type="file")

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )
    monkeypatch.setattr(cli, "run_transform_enrich", fake_run_transform_enrich)
    monkeypatch.setattr(cli, "run_transform_score", fake_run_transform_score)
    monkeypatch.setattr(cli, "run_usage_shortlist", fake_run_usage_shortlist)

    def fake_resolve_sponsor_clean_path(
        *,
        config: PipelineConfig,
        fs: FileSystem,
        snapshot_root: Path | None = None,
    ) -> Path:
        _ = (config, fs, snapshot_root)
        return Path("snapshots/sponsor/2026-02-01/clean.csv")

    def fake_resolve_companies_house_paths(
        *,
        config: PipelineConfig,
        fs: FileSystem,
        snapshot_root: Path | None = None,
    ) -> tuple[Path, Path]:
        _ = (config, fs, snapshot_root)
        return (
            Path("snapshots/companies_house/2026-02-01/clean.csv"),
            Path("snapshots/companies_house/2026-02-01"),
        )

    monkeypatch.setattr(cli, "_resolve_sponsor_clean_path", fake_resolve_sponsor_clean_path)
    monkeypatch.setattr(cli, "_resolve_companies_house_paths", fake_resolve_companies_house_paths)

    app = _build_app()
    result = runner.invoke(app, ["run-all"])

    assert result.exit_code == 0
    assert captured_register_path == Path("snapshots/sponsor/2026-02-01/clean.csv")
    assert captured_config.sponsor_clean_path == "snapshots/sponsor/2026-02-01/clean.csv"
    assert captured_config.ch_clean_path == "snapshots/companies_house/2026-02-01/clean.csv"
    assert captured_config.ch_token_index_dir == "snapshots/companies_house/2026-02-01"


def test_cli_run_all_reads_runtime_mode_and_snapshot_root_from_config_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fs = InMemoryFileSystem()
    fs.write_text(
        """
schema_version = 1
[pipeline]
ch_source_type = "file"
snapshot_root = "cfg/snapshots"
""".strip(),
        Path("config/pipeline.toml"),
    )
    deps = CliDependencies(fs=fs, http_session=DummySession(), http_client=None)
    captured_snapshot_root = Path("unset")

    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        _ = (cls, dotenv_path)
        return PipelineConfig(ch_source_type="api", snapshot_root="env/snapshots")

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    def fake_resolve_sponsor_clean_path(
        *,
        config: PipelineConfig,
        fs: FileSystem,
        snapshot_root: Path | None = None,
    ) -> Path:
        nonlocal captured_snapshot_root
        _ = (config, fs)
        captured_snapshot_root = snapshot_root if snapshot_root is not None else Path("missing")
        return Path("snapshots/sponsor/2026-02-01/clean.csv")

    def fake_resolve_companies_house_paths(
        *,
        config: PipelineConfig,
        fs: FileSystem,
        snapshot_root: Path | None = None,
    ) -> tuple[Path, Path]:
        _ = (config, fs, snapshot_root)
        return (
            Path("snapshots/companies_house/2026-02-01/clean.csv"),
            Path("snapshots/companies_house/2026-02-01"),
        )

    def fake_run_transform_enrich(**kwargs: object) -> dict[str, Path]:
        _ = kwargs
        return {"enriched": Path("enriched.csv")}

    monkeypatch.setattr(cli, "_resolve_sponsor_clean_path", fake_resolve_sponsor_clean_path)
    monkeypatch.setattr(cli, "_resolve_companies_house_paths", fake_resolve_companies_house_paths)
    monkeypatch.setattr(cli, "run_transform_enrich", fake_run_transform_enrich)

    app = _build_app_with_dependencies(deps)
    result = runner.invoke(
        app,
        ["--config", "config/pipeline.toml", "run-all", "--only", "transform-enrich"],
    )

    assert result.exit_code == 0
    assert captured_snapshot_root == Path("cfg/snapshots")


def test_cli_refresh_sponsor_discovery_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    called = False

    def fake_run_refresh_sponsor(**kwargs: object) -> object:
        nonlocal called
        _ = kwargs
        called = True
        return object()

    def fake_resolve_sponsor_csv_url(
        *,
        http_session: HttpSession,
        url: str | None,
        source_page_url: str,
        timeout_seconds: float = 30,
    ) -> str:
        _ = (http_session, url, source_page_url, timeout_seconds)
        return "https://example.com/sponsor.csv"

    monkeypatch.setattr(cli, "run_refresh_sponsor", fake_run_refresh_sponsor)
    monkeypatch.setattr(cli, "resolve_sponsor_csv_url", fake_resolve_sponsor_csv_url)

    app = _build_app()
    result = runner.invoke(app, ["refresh-sponsor", "--only", "discovery"])

    assert result.exit_code == 0
    assert called is False
    assert "https://example.com/sponsor.csv" in result.output


def test_cli_refresh_sponsor_acquire_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    called = False

    def fake_run_refresh_sponsor_acquire(**kwargs: object) -> SimpleNamespace:
        nonlocal called
        _ = kwargs
        called = True
        return SimpleNamespace(
            paths=SimpleNamespace(snapshot_date="2026-02-01"),
            source_url="https://example.com/sponsor.csv",
            raw_path=Path("snapshots/sponsor/.tmp-1/raw.csv"),
            bytes_raw=123,
        )

    monkeypatch.setattr(cli, "run_refresh_sponsor_acquire", fake_run_refresh_sponsor_acquire)

    app = _build_app()
    result = runner.invoke(app, ["refresh-sponsor", "--only", "acquire"])

    assert result.exit_code == 0
    assert called is True
    assert "Acquire sponsor complete" in result.output


def test_cli_refresh_sponsor_clean_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    called = False

    def fake_run_refresh_sponsor_clean(**kwargs: object) -> SimpleNamespace:
        nonlocal called
        _ = kwargs
        called = True
        return SimpleNamespace(
            snapshot_dir=Path("snapshots/sponsor/2026-02-01"),
            snapshot_date="2026-02-01",
            row_counts={"clean": 1},
        )

    monkeypatch.setattr(cli, "run_refresh_sponsor_clean", fake_run_refresh_sponsor_clean)

    app = _build_app()
    result = runner.invoke(app, ["refresh-sponsor", "--only", "clean"])

    assert result.exit_code == 0
    assert called is True
    assert "Refresh sponsor complete" in result.output


def test_cli_refresh_companies_house_discovery_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    called = False

    def fake_run_refresh_companies_house(**kwargs: object) -> object:
        nonlocal called
        _ = kwargs
        called = True
        return object()

    def fake_resolve_companies_house_zip_url(
        *,
        http_session: HttpSession,
        url: str | None,
        source_page_url: str,
        timeout_seconds: float = 30,
    ) -> str:
        _ = (http_session, url, source_page_url, timeout_seconds)
        return "https://example.com/basic.zip"

    monkeypatch.setattr(cli, "run_refresh_companies_house", fake_run_refresh_companies_house)
    monkeypatch.setattr(
        cli, "resolve_companies_house_zip_url", fake_resolve_companies_house_zip_url
    )

    app = _build_app()
    result = runner.invoke(app, ["refresh-companies-house", "--only", "discovery"])

    assert result.exit_code == 0
    assert called is False
    assert "https://example.com/basic.zip" in result.output


def test_cli_refresh_companies_house_acquire_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    called = False

    def fake_run_refresh_companies_house_acquire(**kwargs: object) -> SimpleNamespace:
        nonlocal called
        _ = kwargs
        called = True
        return SimpleNamespace(
            paths=SimpleNamespace(snapshot_date="2026-02-01"),
            source_url="https://example.com/basic.zip",
            raw_path=Path("snapshots/companies_house/.tmp-1/raw.zip"),
            raw_csv_path=Path("snapshots/companies_house/.tmp-1/raw.csv"),
            bytes_raw=456,
        )

    monkeypatch.setattr(
        cli,
        "run_refresh_companies_house_acquire",
        fake_run_refresh_companies_house_acquire,
    )

    app = _build_app()
    result = runner.invoke(app, ["refresh-companies-house", "--only", "acquire"])

    assert result.exit_code == 0
    assert called is True
    assert "Acquire Companies House complete" in result.output


def test_cli_refresh_companies_house_clean_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        return PipelineConfig()

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    called = False

    def fake_run_refresh_companies_house_clean(**kwargs: object) -> SimpleNamespace:
        nonlocal called
        _ = kwargs
        called = True
        return SimpleNamespace(
            snapshot_dir=Path("snapshots/companies_house/2026-02-01"),
            snapshot_date="2026-02-01",
            row_counts={"clean": 1},
        )

    monkeypatch.setattr(
        cli,
        "run_refresh_companies_house_clean",
        fake_run_refresh_companies_house_clean,
    )

    app = _build_app()
    result = runner.invoke(app, ["refresh-companies-house", "--only", "clean"])

    assert result.exit_code == 0
    assert called is True
    assert "Refresh Companies House complete" in result.output


def test_cli_run_all_only_usage_shortlist(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        _ = dotenv_path
        return PipelineConfig(ch_source_type="file")

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    enrich_called = False
    score_called = False
    usage_called = False

    def fake_run_transform_enrich(**kwargs: object) -> dict[str, Path]:
        nonlocal enrich_called
        _ = kwargs
        enrich_called = True
        return {"enriched": Path("enriched.csv")}

    def fake_run_transform_score(**kwargs: object) -> dict[str, Path]:
        nonlocal score_called
        _ = kwargs
        score_called = True
        return {"scored": Path("scored.csv")}

    def fake_run_usage_shortlist(
        *,
        scored_path: str | Path,
        out_dir: str | Path,
        config: PipelineConfig,
        fs: FileSystem,
    ) -> dict[str, Path]:
        nonlocal usage_called
        _ = (out_dir, config, fs)
        usage_called = True
        assert Path(scored_path) == cli.DEFAULT_SCORED_IN
        return {"shortlist": Path("short.csv"), "explain": Path("explain.csv")}

    monkeypatch.setattr(cli, "run_transform_enrich", fake_run_transform_enrich)
    monkeypatch.setattr(cli, "run_transform_score", fake_run_transform_score)
    monkeypatch.setattr(cli, "run_usage_shortlist", fake_run_usage_shortlist)

    app = _build_app()
    result = runner.invoke(app, ["run-all", "--only", "usage-shortlist"])

    assert result.exit_code == 0
    assert enrich_called is False
    assert score_called is False
    assert usage_called is True


def test_cli_transform_enrich_rejects_api_runtime_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        _ = dotenv_path
        return PipelineConfig(ch_source_type="api")

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    app = _build_app()
    result = runner.invoke(app, ["transform-enrich"])

    assert result.exit_code != 0
    assert "supports CH_SOURCE_TYPE=file only" in result.output


def test_cli_run_all_rejects_api_runtime_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_env(cls: type[PipelineConfig], dotenv_path: str | None = None) -> PipelineConfig:
        _ = dotenv_path
        return PipelineConfig(ch_source_type="api")

    monkeypatch.setattr(
        cli.PipelineConfig,
        "from_env",
        classmethod(fake_from_env),
    )

    app = _build_app()
    result = runner.invoke(app, ["run-all"])

    assert result.exit_code != 0
    assert "supports CH_SOURCE_TYPE=file only" in result.output
