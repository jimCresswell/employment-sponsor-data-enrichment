"""CLI for UK Sponsor Pipeline.

Commands:
- extract: Fetch latest sponsor register from GOV.UK
- transform-register: Filter to Skilled Worker + A-rated, aggregate by org
- transform-enrich: Enrich with Companies House data
- transform-score: Score for tech-likelihood (scored output)
- usage-shortlist: Filter scored output into shortlist and explainability
- run-all: Execute all steps sequentially
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Protocol

import typer
from rich import print as rprint

from .application.extract import ExtractResult, extract_register
from .application.pipeline import run_pipeline
from .application.transform_enrich import run_transform_enrich
from .application.transform_register import TransformRegisterResult, run_transform_register
from .application.transform_score import run_transform_score
from .application.usage import run_usage_shortlist
from .config import PipelineConfig
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


DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_REGISTER_OUT = Path("data/interim/sponsor_register_filtered.csv")
DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_ENRICHED_IN = Path("data/processed/companies_house_enriched.csv")
DEFAULT_SCORED_IN = Path("data/processed/companies_scored.csv")
DEFAULT_CACHE_DIR = Path("data/cache/companies_house")


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


def create_app(deps_builder: DependenciesBuilder) -> typer.Typer:
    """Create a Typer app wired with the provided dependencies builder."""
    app = typer.Typer(
        add_completion=False,
        help=(
            "UK sponsor register pipeline: extract → transform → enrich → score → usage-shortlist"
        ),
    )

    @app.callback()
    def main(ctx: typer.Context) -> None:
        """Initialise CLI context."""
        ctx.obj = CliContext(config=PipelineConfig.from_env(), deps_builder=deps_builder)

    @app.command()
    def extract(
        ctx: typer.Context,
        url: Annotated[
            str | None,
            typer.Option(
                "--url",
                "-u",
                help="Direct CSV URL (bypasses GOV.UK page scraping)",
            ),
        ] = None,
        data_dir: Annotated[
            Path,
            typer.Option(
                "--data-dir",
                "-d",
                help="Directory to save downloaded CSV",
            ),
        ] = DEFAULT_RAW_DIR,
    ) -> None:
        """Extract the latest sponsor register CSV from GOV.UK."""
        state = _get_context(ctx)
        deps = state.build_dependencies(cache_dir=DEFAULT_CACHE_DIR, build_http_client=False)
        result: ExtractResult = extract_register(
            url_override=url,
            data_dir=data_dir,
            session=deps.http_session,
            fs=deps.fs,
        )
        rprint(f"[green]✓ Downloaded:[/green] {result.output_path}")
        rprint(f"  Hash: {result.sha256_hash[:16]}...")
        rprint(f"  Valid schema: {result.schema_valid}")

    @app.command(name="transform-register")
    def transform_register(
        ctx: typer.Context,
        raw_dir: Annotated[
            Path,
            typer.Option(
                "--raw-dir",
                help="Directory containing raw CSV files",
            ),
        ] = DEFAULT_RAW_DIR,
        out_path: Annotated[
            Path,
            typer.Option(
                "--output",
                "-o",
                help="Output path for filtered/aggregated CSV",
            ),
        ] = DEFAULT_REGISTER_OUT,
    ) -> None:
        """Transform register: filter to Skilled Worker + A-rated and aggregate by organisation."""
        state = _get_context(ctx)
        deps = state.build_dependencies(cache_dir=DEFAULT_CACHE_DIR, build_http_client=False)
        result: TransformRegisterResult = run_transform_register(
            raw_dir=raw_dir,
            out_path=out_path,
            fs=deps.fs,
        )
        rprint(f"[green]✓ Transform register complete:[/green] {result.output_path}")
        rprint(
            f"  {result.total_raw_rows:,} raw → {result.filtered_rows:,} filtered → "
            f"{result.unique_orgs:,} unique orgs"
        )

    @app.command(name="transform-enrich")
    def transform_enrich(
        ctx: typer.Context,
        register_path: Annotated[
            Path,
            typer.Option(
                "--input",
                "-i",
                help="Path to register transform output CSV",
            ),
        ] = DEFAULT_REGISTER_OUT,
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
        outs = run_transform_enrich(
            register_path=register_path,
            out_dir=out_dir,
            cache_dir=DEFAULT_CACHE_DIR,
            resume=resume,
            batch_start=batch_start,
            batch_count=batch_count,
            batch_size=batch_size,
            config=config,
            http_client=deps.http_client,
            http_session=deps.http_session,
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
        skip_download: Annotated[
            bool,
            typer.Option(
                "--skip-download",
                help="Skip download if raw CSV already exists",
            ),
        ] = False,
    ) -> None:
        """Run all pipeline steps sequentially.

        Executes: extract → transform-register → transform-enrich → transform-score →
        usage-shortlist
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
        result = run_pipeline(
            config=config,
            skip_download=skip_download,
            cache_dir=DEFAULT_CACHE_DIR,
            fs=deps.fs,
            http_client=deps.http_client,
            http_session=deps.http_session,
            session=deps.http_session,
        )

        if skip_download:
            rprint("[yellow]Skipping download (--skip-download)[/yellow]")
        elif result.extract is not None:
            rprint(f"[green]✓ Downloaded:[/green] {result.extract.output_path}")

        rprint(f"[green]✓ {result.register.unique_orgs:,} unique organisations[/green]")
        rprint(f"[green]✓ Enriched: {result.enrich['enriched']}[/green]")

        rprint("\n[bold green]═══ Pipeline Complete ═══[/bold green]")
        rprint(f"Final shortlist: {result.usage['shortlist']}")
        rprint(f"Explainability: {result.usage['explain']}")

    _ = (
        main,
        extract,
        transform_register,
        transform_enrich,
        transform_score,
        usage_shortlist,
        run_all,
    )

    return app
