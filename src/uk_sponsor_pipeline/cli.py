"""CLI for UK Sponsor Pipeline.

Commands:
- download: Fetch latest sponsor register from GOV.UK
- stage1: Filter to Skilled Worker + A-rated, aggregate by org
- stage2: Enrich with Companies House data
- stage3: Score for tech-likelihood, produce shortlist
- run-all: Execute all stages sequentially
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint

from .config import PipelineConfig
from .stages.download import DownloadResult, download_latest
from .stages.stage1 import Stage1Result, run_stage1
from .stages.stage2_companies_house import run_stage2
from .stages.stage3_scoring import run_stage3

app = typer.Typer(
    add_completion=False,
    help="UK sponsor register pipeline: download → filter → enrich → score → shortlist",
)

DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_STAGE1_OUT = Path("data/interim/stage1_skilled_worker_A_rated_aggregated_by_org.csv")
DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_STAGE2_IN = Path("data/processed/stage2_enriched_companies_house.csv")


@app.command()
def download(
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
    """Download the latest sponsor register CSV from GOV.UK."""
    result: DownloadResult = download_latest(url_override=url, data_dir=data_dir)
    rprint(f"[green]✓ Downloaded:[/green] {result.output_path}")
    rprint(f"  Hash: {result.sha256_hash[:16]}...")
    rprint(f"  Valid schema: {result.schema_valid}")


@app.command()
def stage1(
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
    ] = DEFAULT_STAGE1_OUT,
) -> None:
    """Stage 1: Filter to Skilled Worker + A-rated and aggregate by organization."""
    result: Stage1Result = run_stage1(raw_dir=raw_dir, out_path=out_path)
    rprint(f"[green]✓ Stage 1 complete:[/green] {result.output_path}")
    rprint(
        f"  {result.total_raw_rows:,} raw → {result.filtered_rows:,} filtered → "
        f"{result.unique_orgs:,} unique orgs"
    )


@app.command()
def stage2(
    stage1_path: Annotated[
        Path,
        typer.Option(
            "--input",
            "-i",
            help="Path to Stage 1 output CSV",
        ),
    ] = DEFAULT_STAGE1_OUT,
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
    """Stage 2: Enrich Stage 1 output using Companies House API.

    Batching: use --batch-start/--batch-count/--batch-size.
    Resume: --resume and check data/processed/stage2_resume_report.json.
    """
    config = PipelineConfig.from_env()
    outs = run_stage2(
        stage1_path=stage1_path,
        out_dir=out_dir,
        resume=resume,
        batch_start=batch_start,
        batch_count=batch_count,
        batch_size=batch_size,
        config=config,
    )
    rprint("[green]✓ Stage 2 complete:[/green]")
    for k, v in outs.items():
        rprint(f"  {k}: {v}")


@app.command()
def stage3(
    stage2_path: Annotated[
        Path,
        typer.Option(
            "--input",
            "-i",
            help="Path to Stage 2 enriched CSV",
        ),
    ] = DEFAULT_STAGE2_IN,
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
            help="Filter by region (repeatable, e.g. --region London --region Manchester)",
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
    """Stage 3: Score for tech-likelihood and produce shortlist.

    Supports geographic filtering with --region and --postcode-prefix options.
    """
    # Load base config and apply CLI overrides
    config = PipelineConfig.from_env()

    if threshold is not None or region or postcode_prefix:
        config = config.with_overrides(
            tech_score_threshold=threshold,
            geo_filter_regions=tuple(region) if region else None,
            geo_filter_postcodes=tuple(postcode_prefix) if postcode_prefix else None,
        )

    outs = run_stage3(stage2_path=stage2_path, out_dir=out_dir, config=config)
    rprint("[green]✓ Stage 3 complete:[/green]")
    for k, v in outs.items():
        rprint(f"  {k}: {v}")


@app.command(name="run-all")
def run_all(
    region: Annotated[
        list[str] | None,
        typer.Option(
            "--region",
            "-r",
            help="Filter final shortlist by region (repeatable)",
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
            help="Override tech score threshold for Stage 3",
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
    """Run all pipeline stages sequentially.

    Executes: download → stage1 → stage2 → stage3
    Geographic filters apply to the final Stage 3 shortlist.
    """
    # Stage 0: Download
    if not skip_download:
        rprint("\n[bold cyan]═══ Stage 0: Download ═══[/bold cyan]")
        download_result = download_latest()
        rprint(f"[green]✓ Downloaded:[/green] {download_result.output_path}")
    else:
        rprint("[yellow]Skipping download (--skip-download)[/yellow]")

    # Stage 1
    rprint("\n[bold cyan]═══ Stage 1: Filter & Aggregate ═══[/bold cyan]")
    stage1_result = run_stage1()
    rprint(f"[green]✓ {stage1_result.unique_orgs:,} unique organizations[/green]")

    config = PipelineConfig.from_env()

    # Stage 2
    rprint("\n[bold cyan]═══ Stage 2: Companies House Enrichment ═══[/bold cyan]")
    stage2_outs = run_stage2(config=config)
    rprint(f"[green]✓ Enriched: {stage2_outs['enriched']}[/green]")

    # Stage 3
    rprint("\n[bold cyan]═══ Stage 3: Tech Scoring & Shortlist ═══[/bold cyan]")

    if threshold is not None or region or postcode_prefix:
        config = config.with_overrides(
            tech_score_threshold=threshold,
            geo_filter_regions=tuple(region) if region else None,
            geo_filter_postcodes=tuple(postcode_prefix) if postcode_prefix else None,
        )

    stage3_outs = run_stage3(config=config)

    rprint("\n[bold green]═══ Pipeline Complete ═══[/bold green]")
    rprint(f"Final shortlist: {stage3_outs['shortlist']}")
    rprint(f"Explainability: {stage3_outs['explain']}")
