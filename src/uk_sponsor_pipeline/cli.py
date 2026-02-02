"""CLI for UK Sponsor Pipeline.

Commands:
- extract: Fetch latest sponsor register from GOV.UK
- transform-register: Filter to Skilled Worker + A-rated, aggregate by org
- transform-enrich: Enrich with Companies House data
- transform-score: Score for tech-likelihood, produce shortlist
- run-all: Execute all steps sequentially
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint

from .application.extract import ExtractResult, extract_register
from .application.pipeline import run_pipeline
from .application.transform_enrich import run_transform_enrich
from .application.transform_register import TransformRegisterResult, run_transform_register
from .application.transform_score import run_transform_score
from .config import PipelineConfig

app = typer.Typer(
    add_completion=False,
    help="UK sponsor register pipeline: extract → transform → enrich → score → shortlist",
)

DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_REGISTER_OUT = Path("data/interim/sponsor_register_filtered.csv")
DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_ENRICHED_IN = Path("data/processed/companies_house_enriched.csv")


def _single_region(region: list[str] | None) -> str | None:
    if not region:
        return None
    if len(region) > 1:
        raise typer.BadParameter("Only one --region value is supported.")
    return region[0]


@app.command()
def extract(
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
    result: ExtractResult = extract_register(url_override=url, data_dir=data_dir)
    rprint(f"[green]✓ Downloaded:[/green] {result.output_path}")
    rprint(f"  Hash: {result.sha256_hash[:16]}...")
    rprint(f"  Valid schema: {result.schema_valid}")


@app.command(name="transform-register")
def transform_register(
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
    result: TransformRegisterResult = run_transform_register(raw_dir=raw_dir, out_path=out_path)
    rprint(f"[green]✓ Transform register complete:[/green] {result.output_path}")
    rprint(
        f"  {result.total_raw_rows:,} raw → {result.filtered_rows:,} filtered → "
        f"{result.unique_orgs:,} unique orgs"
    )


@app.command(name="transform-enrich")
def transform_enrich(
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
    config = PipelineConfig.from_env()
    outs = run_transform_enrich(
        register_path=register_path,
        out_dir=out_dir,
        resume=resume,
        batch_start=batch_start,
        batch_count=batch_count,
        batch_size=batch_size,
        config=config,
    )
    rprint("[green]✓ Transform enrich complete:[/green]")
    for k, v in outs.items():
        rprint(f"  {k}: {v}")


@app.command(name="transform-score")
def transform_score(
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
    """Transform score: score for tech-likelihood and produce shortlist.

    Supports geographic filtering with --region and --postcode-prefix options.
    """
    # Load base config and apply CLI overrides
    config = PipelineConfig.from_env()

    if threshold is not None or region or postcode_prefix:
        config = config.with_overrides(
            tech_score_threshold=threshold,
            geo_filter_region=_single_region(region),
            geo_filter_postcodes=tuple(postcode_prefix) if postcode_prefix else None,
        )

    outs = run_transform_score(enriched_path=enriched_path, out_dir=out_dir, config=config)
    rprint("[green]✓ Transform score complete:[/green]")
    for k, v in outs.items():
        rprint(f"  {k}: {v}")


@app.command(name="run-all")
def run_all(
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

    Executes: extract → transform-register → transform-enrich → transform-score
    Geographic filters apply to the final shortlist.
    """
    config = PipelineConfig.from_env()
    if threshold is not None or region or postcode_prefix:
        config = config.with_overrides(
            tech_score_threshold=threshold,
            geo_filter_region=_single_region(region),
            geo_filter_postcodes=tuple(postcode_prefix) if postcode_prefix else None,
        )

    result = run_pipeline(config=config, skip_download=skip_download)

    if skip_download:
        rprint("[yellow]Skipping download (--skip-download)[/yellow]")
    elif result.extract is not None:
        rprint(f"[green]✓ Downloaded:[/green] {result.extract.output_path}")

    rprint(f"[green]✓ {result.register.unique_orgs:,} unique organisations[/green]")
    rprint(f"[green]✓ Enriched: {result.enrich['enriched']}[/green]")

    rprint("\n[bold green]═══ Pipeline Complete ═══[/bold green]")
    rprint(f"Final shortlist: {result.score['shortlist']}")
    rprint(f"Explainability: {result.score['explain']}")
