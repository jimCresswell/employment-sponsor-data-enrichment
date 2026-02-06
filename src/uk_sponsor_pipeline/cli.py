"""CLI for UK Sponsor Pipeline.

Commands:
- refresh-sponsor: Download and snapshot the sponsor register
- refresh-companies-house: Download and snapshot Companies House bulk data
- transform-enrich: Enrich with Companies House data
- transform-score: Score for tech-likelihood (scored output)
- usage-shortlist: Filter scored output into shortlist and explainability
- run-all: Execute cache-only steps sequentially
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Protocol

import typer
from rich import print as rprint

from .application.refresh_companies_house import (
    run_refresh_companies_house,
    run_refresh_companies_house_acquire,
    run_refresh_companies_house_clean,
)
from .application.refresh_sponsor import (
    run_refresh_sponsor,
    run_refresh_sponsor_acquire,
    run_refresh_sponsor_clean,
)
from .application.snapshots import resolve_latest_snapshot_path
from .application.source_links import (
    COMPANIES_HOUSE_SOURCE_PAGE_URL,
    SPONSOR_SOURCE_PAGE_URL,
    resolve_companies_house_zip_url,
    resolve_sponsor_csv_url,
)
from .application.transform_enrich import run_transform_enrich
from .application.transform_score import run_transform_score
from .application.usage import run_usage_shortlist
from .cli_progress import CliProgressReporter
from .config import PipelineConfig
from .exceptions import SnapshotArtefactMissingError
from .protocols import FileSystem, HttpClient, HttpSession


class DependenciesBuilder(Protocol):
    """Protocol for constructing CLI dependencies."""

    def __call__(
        self,
        *,
        config: PipelineConfig,
        cache_dir: str | Path,
        build_http_client: bool,
    ) -> CliDependencies:
        """Build dependencies for CLI commands."""
        ...


@dataclass(frozen=True)
class CliDependencies:
    """Concrete dependencies required by the CLI."""

    fs: FileSystem
    http_session: HttpSession
    http_client: HttpClient | None


@dataclass(frozen=True)
class CliContext:
    """Runtime CLI context for a single command invocation."""

    config: PipelineConfig
    deps_builder: DependenciesBuilder

    def build_dependencies(
        self,
        *,
        cache_dir: str | Path,
        build_http_client: bool,
        config: PipelineConfig | None = None,
    ) -> CliDependencies:
        """Return dependencies using the configured builder."""
        config_value = config or self.config
        return self.deps_builder(
            config=config_value,
            cache_dir=cache_dir,
            build_http_client=build_http_client,
        )


class SingleRegionError(typer.BadParameter):
    """Raised when multiple regions are supplied to CLI filters."""

    def __init__(self) -> None:
        super().__init__("Only one --region value is supported.")


class CliContextNotInitialisedError(typer.BadParameter):
    """Raised when CLI context is missing."""

    def __init__(self) -> None:
        super().__init__("CLI context is not initialised. Use the uk-sponsor entry point.")


class UrlWithCleanOnlyError(typer.BadParameter):
    """Raised when --url is supplied with --only clean."""

    def __init__(self) -> None:
        super().__init__("--url is not supported with --only clean.")


DEFAULT_SNAPSHOT_ROOT = Path("data/cache/snapshots")
DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_ENRICHED_IN = Path("data/processed/companies_house_enriched.csv")
DEFAULT_SCORED_IN = Path("data/processed/companies_scored.csv")
DEFAULT_CACHE_DIR = Path("data/cache/companies_house")


class RefreshOnly(StrEnum):
    """Allowed logical groups for refresh commands."""

    ALL = "all"
    DISCOVERY = "discovery"
    ACQUIRE = "acquire"
    CLEAN = "clean"


class RunAllOnly(StrEnum):
    """Allowed logical groups for run-all."""

    ALL = "all"
    TRANSFORM_ENRICH = "transform-enrich"
    TRANSFORM_SCORE = "transform-score"
    USAGE_SHORTLIST = "usage-shortlist"


def _single_region(region: list[str] | None) -> str | None:
    if not region:
        return None
    if len(region) > 1:
        raise SingleRegionError()
    return region[0]


def _get_context(ctx: typer.Context) -> CliContext:
    if not isinstance(ctx.obj, CliContext):
        raise CliContextNotInitialisedError()
    return ctx.obj


def _require_path(path: Path, fs: FileSystem) -> Path:
    if not fs.exists(path):
        raise SnapshotArtefactMissingError(str(path))
    return path


def _resolve_sponsor_clean_path(
    *, config: PipelineConfig, fs: FileSystem, snapshot_root: Path | None = None
) -> Path:
    if config.sponsor_clean_path:
        return _require_path(Path(config.sponsor_clean_path), fs)
    root = snapshot_root or Path(config.snapshot_root or DEFAULT_SNAPSHOT_ROOT)
    return resolve_latest_snapshot_path(
        snapshot_root=root,
        dataset="sponsor",
        filename="clean.csv",
        fs=fs,
    )


def _resolve_companies_house_paths(
    *, config: PipelineConfig, fs: FileSystem, snapshot_root: Path | None = None
) -> tuple[Path, Path]:
    if config.ch_clean_path:
        clean_path = _require_path(Path(config.ch_clean_path), fs)
    else:
        root = snapshot_root or Path(config.snapshot_root or DEFAULT_SNAPSHOT_ROOT)
        clean_path = resolve_latest_snapshot_path(
            snapshot_root=root,
            dataset="companies_house",
            filename="clean.csv",
            fs=fs,
        )
    index_dir = Path(config.ch_token_index_dir) if config.ch_token_index_dir else clean_path.parent
    return clean_path, index_dir


def _with_snapshot_paths(
    *,
    config: PipelineConfig,
    sponsor_clean_path: Path,
    ch_clean_path: Path,
    ch_token_index_dir: Path,
) -> PipelineConfig:
    return replace(
        config,
        sponsor_clean_path=str(sponsor_clean_path),
        ch_clean_path=str(ch_clean_path),
        ch_token_index_dir=str(ch_token_index_dir),
    )


def create_app(deps_builder: DependenciesBuilder) -> typer.Typer:
    """Create a Typer app wired with the provided dependencies builder."""
    app = typer.Typer(
        add_completion=False,
        help=("UK sponsor pipeline: refresh → enrich → score → usage-shortlist"),
    )

    @app.callback()
    def main(ctx: typer.Context) -> None:
        """Initialise CLI context."""
        ctx.obj = CliContext(config=PipelineConfig.from_env(), deps_builder=deps_builder)

    @app.command(name="refresh-sponsor")
    def refresh_sponsor(
        ctx: typer.Context,
        url: Annotated[
            str | None,
            typer.Option(
                "--url",
                "-u",
                help="Direct CSV URL for the sponsor register (optional)",
            ),
        ] = None,
        snapshot_root: Annotated[
            Path | None,
            typer.Option(
                "--snapshot-root",
                help="Snapshot root directory (defaults to SNAPSHOT_ROOT)",
            ),
        ] = None,
        only: Annotated[
            RefreshOnly,
            typer.Option(
                "--only",
                help="Run only one logical refresh group (default: all).",
            ),
        ] = RefreshOnly.ALL,
    ) -> None:
        """Refresh sponsor register snapshot (download + clean)."""
        state = _get_context(ctx)
        config = state.config
        root = snapshot_root or Path(config.snapshot_root or DEFAULT_SNAPSHOT_ROOT)
        deps = state.build_dependencies(cache_dir=DEFAULT_CACHE_DIR, build_http_client=False)
        if only == RefreshOnly.DISCOVERY:
            resolved_url = resolve_sponsor_csv_url(
                http_session=deps.http_session,
                url=url,
                source_page_url=SPONSOR_SOURCE_PAGE_URL,
            )
            rprint("[green]✓ Sponsor discovery complete:[/green]")
            rprint(f"  URL: {resolved_url}")
            return
        if only == RefreshOnly.ACQUIRE:
            result = run_refresh_sponsor_acquire(
                url=url,
                snapshot_root=root,
                fs=deps.fs,
                http_session=deps.http_session,
                command_line=" ".join(sys.argv),
                progress=CliProgressReporter(),
            )
            rprint("[green]✓ Acquire sponsor complete:[/green]")
            rprint(f"  Snapshot date: {result.paths.snapshot_date}")
            rprint(f"  Source URL: {result.source_url}")
            rprint(f"  Raw path: {result.raw_path}")
            rprint(f"  Raw bytes: {result.bytes_raw:,}")
            return
        if only == RefreshOnly.CLEAN:
            if url is not None:
                raise UrlWithCleanOnlyError()
            result = run_refresh_sponsor_clean(
                snapshot_root=root,
                fs=deps.fs,
                command_line=" ".join(sys.argv),
                progress=CliProgressReporter(),
            )
            rprint(f"[green]✓ Refresh sponsor complete:[/green] {result.snapshot_dir}")
            rprint(f"  Snapshot date: {result.snapshot_date}")
            rprint(f"  Clean rows: {result.row_counts['clean']:,}")
            return
        result = run_refresh_sponsor(
            url=url,
            snapshot_root=root,
            fs=deps.fs,
            http_session=deps.http_session,
            command_line=" ".join(sys.argv),
            progress=CliProgressReporter(),
        )
        rprint(f"[green]✓ Refresh sponsor complete:[/green] {result.snapshot_dir}")
        rprint(f"  Snapshot date: {result.snapshot_date}")
        rprint(f"  Clean rows: {result.row_counts['clean']:,}")

    @app.command(name="refresh-companies-house")
    def refresh_companies_house(
        ctx: typer.Context,
        url: Annotated[
            str | None,
            typer.Option(
                "--url",
                "-u",
                help="Direct ZIP URL for Companies House bulk data (optional)",
            ),
        ] = None,
        snapshot_root: Annotated[
            Path | None,
            typer.Option(
                "--snapshot-root",
                help="Snapshot root directory (defaults to SNAPSHOT_ROOT)",
            ),
        ] = None,
        only: Annotated[
            RefreshOnly,
            typer.Option(
                "--only",
                help="Run only one logical refresh group (default: all).",
            ),
        ] = RefreshOnly.ALL,
    ) -> None:
        """Refresh Companies House bulk snapshot (download + clean + index)."""
        state = _get_context(ctx)
        config = state.config
        root = snapshot_root or Path(config.snapshot_root or DEFAULT_SNAPSHOT_ROOT)
        deps = state.build_dependencies(cache_dir=DEFAULT_CACHE_DIR, build_http_client=False)
        if only == RefreshOnly.DISCOVERY:
            resolved_url = resolve_companies_house_zip_url(
                http_session=deps.http_session,
                url=url,
                source_page_url=COMPANIES_HOUSE_SOURCE_PAGE_URL,
            )
            rprint("[green]✓ Companies House discovery complete:[/green]")
            rprint(f"  URL: {resolved_url}")
            return
        if only == RefreshOnly.ACQUIRE:
            result = run_refresh_companies_house_acquire(
                url=url,
                snapshot_root=root,
                fs=deps.fs,
                http_session=deps.http_session,
                command_line=" ".join(sys.argv),
                progress=CliProgressReporter(),
            )
            rprint("[green]✓ Acquire Companies House complete:[/green]")
            rprint(f"  Snapshot date: {result.paths.snapshot_date}")
            rprint(f"  Source URL: {result.source_url}")
            rprint(f"  Raw path: {result.raw_path}")
            rprint(f"  Raw CSV path: {result.raw_csv_path}")
            rprint(f"  Raw bytes: {result.bytes_raw:,}")
            return
        if only == RefreshOnly.CLEAN:
            if url is not None:
                raise UrlWithCleanOnlyError()
            result = run_refresh_companies_house_clean(
                snapshot_root=root,
                fs=deps.fs,
                command_line=" ".join(sys.argv),
                progress=CliProgressReporter(),
            )
            rprint(f"[green]✓ Refresh Companies House complete:[/green] {result.snapshot_dir}")
            rprint(f"  Snapshot date: {result.snapshot_date}")
            rprint(f"  Clean rows: {result.row_counts['clean']:,}")
            return
        result = run_refresh_companies_house(
            url=url,
            snapshot_root=root,
            fs=deps.fs,
            http_session=deps.http_session,
            command_line=" ".join(sys.argv),
            progress=CliProgressReporter(),
        )
        rprint(f"[green]✓ Refresh Companies House complete:[/green] {result.snapshot_dir}")
        rprint(f"  Snapshot date: {result.snapshot_date}")
        rprint(f"  Clean rows: {result.row_counts['clean']:,}")

    @app.command(name="transform-enrich")
    def transform_enrich(
        ctx: typer.Context,
        register_path: Annotated[
            Path | None,
            typer.Option(
                "--input",
                "-i",
                help="Path to sponsor clean CSV (defaults to latest snapshot)",
            ),
        ] = None,
        out_dir: Annotated[
            Path,
            typer.Option(
                "--output-dir",
                "-o",
                help="Directory for output files",
            ),
        ] = DEFAULT_PROCESSED_DIR,
        resume: Annotated[
            bool,
            typer.Option(
                "--resume/--no-resume",
                help="Resume from previous run (skip already-processed orgs)",
            ),
        ] = True,
        batch_start: Annotated[
            int,
            typer.Option(
                "--batch-start",
                help="1-based batch index to start from (after resume filtering)",
            ),
        ] = 1,
        batch_count: Annotated[
            int | None,
            typer.Option(
                "--batch-count",
                help="Number of batches to run (default: all remaining)",
            ),
        ] = None,
        batch_size: Annotated[
            int | None,
            typer.Option(
                "--batch-size",
                help="Override batch size for this run (default: CH_BATCH_SIZE)",
            ),
        ] = None,
    ) -> None:
        """Transform enrich: enrich register output using Companies House data.

        Batching: use --batch-start/--batch-count/--batch-size.
        Resume: --resume and check data/processed/companies_house_resume_report.json.
        """
        state = _get_context(ctx)
        config = state.config
        deps = state.build_dependencies(
            cache_dir=DEFAULT_CACHE_DIR,
            build_http_client=True,
            config=config,
        )
        register_value = register_path or _resolve_sponsor_clean_path(
            config=config,
            fs=deps.fs,
        )
        if config.ch_source_type == "file":
            ch_clean_path, ch_token_index_dir = _resolve_companies_house_paths(
                config=config,
                fs=deps.fs,
            )
            config = _with_snapshot_paths(
                config=config,
                sponsor_clean_path=register_value,
                ch_clean_path=ch_clean_path,
                ch_token_index_dir=ch_token_index_dir,
            )
        else:
            config = replace(config, sponsor_clean_path=str(register_value))
        outs = run_transform_enrich(
            register_path=register_value,
            out_dir=out_dir,
            cache_dir=DEFAULT_CACHE_DIR,
            resume=resume,
            batch_start=batch_start,
            batch_count=batch_count,
            batch_size=batch_size,
            config=config,
            http_client=deps.http_client,
            fs=deps.fs,
        )
        rprint("[green]✓ Transform enrich complete:[/green]")
        for k, v in outs.items():
            rprint(f"  {k}: {v}")

    @app.command(name="transform-score")
    def transform_score(
        ctx: typer.Context,
        enriched_path: Annotated[
            Path,
            typer.Option(
                "--input",
                "-i",
                help="Path to enriched Companies House CSV",
            ),
        ] = DEFAULT_ENRICHED_IN,
        out_dir: Annotated[
            Path,
            typer.Option(
                "--output-dir",
                "-o",
                help="Directory for output files",
            ),
        ] = DEFAULT_PROCESSED_DIR,
    ) -> None:
        """Transform score: score for tech-likelihood and write scored output."""
        state = _get_context(ctx)
        config = state.config
        deps = state.build_dependencies(
            cache_dir=DEFAULT_CACHE_DIR,
            build_http_client=False,
            config=config,
        )
        outs = run_transform_score(
            enriched_path=enriched_path,
            out_dir=out_dir,
            config=config,
            fs=deps.fs,
        )
        rprint("[green]✓ Transform score complete:[/green]")
        for k, v in outs.items():
            rprint(f"  {k}: {v}")

    @app.command(name="usage-shortlist")
    def usage_shortlist(
        ctx: typer.Context,
        scored_path: Annotated[
            Path,
            typer.Option(
                "--input",
                "-i",
                help="Path to scored Companies House CSV",
            ),
        ] = DEFAULT_SCORED_IN,
        out_dir: Annotated[
            Path,
            typer.Option(
                "--output-dir",
                "-o",
                help="Directory for output files",
            ),
        ] = DEFAULT_PROCESSED_DIR,
        threshold: Annotated[
            float | None,
            typer.Option(
                "--threshold",
                "-t",
                help="Override tech score threshold (default: 0.55)",
            ),
        ] = None,
        region: Annotated[
            list[str] | None,
            typer.Option(
                "--region",
                "-r",
                help="Filter by region (single value, e.g. --region London)",
            ),
        ] = None,
        postcode_prefix: Annotated[
            list[str] | None,
            typer.Option(
                "--postcode-prefix",
                "-p",
                help=(
                    "Filter by postcode prefix (repeatable, e.g. --postcode-prefix EC "
                    "--postcode-prefix SW)"
                ),
            ),
        ] = None,
    ) -> None:
        """Usage shortlist: filter scored output into shortlist and explainability."""
        state = _get_context(ctx)
        config = state.config
        if threshold is not None or region or postcode_prefix:
            config = config.with_overrides(
                tech_score_threshold=threshold,
                geo_filter_region=_single_region(region),
                geo_filter_postcodes=tuple(postcode_prefix) if postcode_prefix else None,
            )

        deps = state.build_dependencies(
            cache_dir=DEFAULT_CACHE_DIR,
            build_http_client=False,
            config=config,
        )
        outs = run_usage_shortlist(
            scored_path=scored_path,
            out_dir=out_dir,
            config=config,
            fs=deps.fs,
        )
        rprint("[green]✓ Usage shortlist complete:[/green]")
        for k, v in outs.items():
            rprint(f"  {k}: {v}")

    @app.command(name="run-all")
    def run_all(
        ctx: typer.Context,
        snapshot_root: Annotated[
            Path | None,
            typer.Option(
                "--snapshot-root",
                help="Snapshot root directory (defaults to SNAPSHOT_ROOT)",
            ),
        ] = None,
        region: Annotated[
            list[str] | None,
            typer.Option(
                "--region",
                "-r",
                help="Filter final shortlist by region (single value)",
            ),
        ] = None,
        postcode_prefix: Annotated[
            list[str] | None,
            typer.Option(
                "--postcode-prefix",
                "-p",
                help="Filter final shortlist by postcode prefix (repeatable)",
            ),
        ] = None,
        threshold: Annotated[
            float | None,
            typer.Option(
                "--threshold",
                "-t",
                help="Override tech score threshold for scoring",
            ),
        ] = None,
        only: Annotated[
            RunAllOnly,
            typer.Option(
                "--only",
                help="Run only one logical group (default: all).",
            ),
        ] = RunAllOnly.ALL,
    ) -> None:
        """Run cache-only pipeline steps sequentially.

        Executes: transform-enrich → transform-score → usage-shortlist
        Geographic filters apply to the final shortlist.
        """
        state = _get_context(ctx)
        config = state.config
        if threshold is not None or region or postcode_prefix:
            config = config.with_overrides(
                tech_score_threshold=threshold,
                geo_filter_region=_single_region(region),
                geo_filter_postcodes=tuple(postcode_prefix) if postcode_prefix else None,
            )

        deps = state.build_dependencies(
            cache_dir=DEFAULT_CACHE_DIR,
            build_http_client=True,
            config=config,
        )
        if only in (RunAllOnly.ALL, RunAllOnly.TRANSFORM_ENRICH):
            root = snapshot_root or Path(config.snapshot_root or DEFAULT_SNAPSHOT_ROOT)
            register_path = _resolve_sponsor_clean_path(
                config=config,
                fs=deps.fs,
                snapshot_root=root,
            )
            if config.ch_source_type == "file":
                ch_clean_path, ch_token_index_dir = _resolve_companies_house_paths(
                    config=config,
                    fs=deps.fs,
                    snapshot_root=root,
                )
                config = _with_snapshot_paths(
                    config=config,
                    sponsor_clean_path=register_path,
                    ch_clean_path=ch_clean_path,
                    ch_token_index_dir=ch_token_index_dir,
                )
            else:
                config = replace(config, sponsor_clean_path=str(register_path))
            enrich_outs = run_transform_enrich(
                register_path=register_path,
                out_dir=DEFAULT_PROCESSED_DIR,
                cache_dir=DEFAULT_CACHE_DIR,
                config=config,
                http_client=deps.http_client,
                fs=deps.fs,
            )
            rprint(f"[green]✓ Enriched: {enrich_outs['enriched']}[/green]")
            if only == RunAllOnly.TRANSFORM_ENRICH:
                return

        scored_path = DEFAULT_ENRICHED_IN
        if only in (RunAllOnly.ALL, RunAllOnly.TRANSFORM_SCORE):
            score_outs = run_transform_score(
                enriched_path=DEFAULT_ENRICHED_IN,
                out_dir=DEFAULT_PROCESSED_DIR,
                config=config,
                fs=deps.fs,
            )
            scored_path = score_outs["scored"]
            rprint(f"[green]✓ Scored: {scored_path}[/green]")
            if only == RunAllOnly.TRANSFORM_SCORE:
                return

        usage_outs = run_usage_shortlist(
            scored_path=DEFAULT_SCORED_IN if only == RunAllOnly.USAGE_SHORTLIST else scored_path,
            out_dir=DEFAULT_PROCESSED_DIR,
            config=config,
            fs=deps.fs,
        )
        if only == RunAllOnly.USAGE_SHORTLIST:
            rprint(f"[green]✓ Shortlist: {usage_outs['shortlist']}[/green]")
            rprint(f"[green]✓ Explainability: {usage_outs['explain']}[/green]")
            return

        rprint("\n[bold green]═══ Pipeline Complete ═══[/bold green]")
        rprint(f"Final shortlist: {usage_outs['shortlist']}")
        rprint(f"Explainability: {usage_outs['explain']}")

    _ = (
        main,
        refresh_sponsor,
        refresh_companies_house,
        transform_enrich,
        transform_score,
        usage_shortlist,
        run_all,
    )

    return app
