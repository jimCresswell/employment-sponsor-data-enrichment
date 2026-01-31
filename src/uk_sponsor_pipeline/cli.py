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
from typing import Optional

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


@app.command()
def download(
    url: Optional[str] = typer.Option(
        None,
        "--url",
        "-u",
        help="Direct CSV URL (bypasses GOV.UK page scraping)",
    ),
    data_dir: Path = typer.Option(
        Path("data/raw"),
        "--data-dir",
        "-d",
        help="Directory to save downloaded CSV",
    ),
) -> None:
    """Download the latest sponsor register CSV from GOV.UK."""
    result: DownloadResult = download_latest(url_override=url, data_dir=data_dir)
    rprint(f"[green]✓ Downloaded:[/green] {result.output_path}")
    rprint(f"  Hash: {result.sha256_hash[:16]}...")
    rprint(f"  Valid schema: {result.schema_valid}")


@app.command()
def stage1(
    raw_dir: Path = typer.Option(
        Path("data/raw"),
        "--raw-dir",
        help="Directory containing raw CSV files",
    ),
    out_path: Path = typer.Option(
        Path("data/interim/stage1_skilled_worker_A_rated_aggregated_by_org.csv"),
        "--output",
        "-o",
        help="Output path for filtered/aggregated CSV",
    ),
) -> None:
    """Stage 1: Filter to Skilled Worker + A-rated and aggregate by organization."""
    result: Stage1Result = run_stage1(raw_dir=raw_dir, out_path=out_path)
    rprint(f"[green]✓ Stage 1 complete:[/green] {result.output_path}")
    rprint(f"  {result.total_raw_rows:,} raw → {result.filtered_rows:,} filtered → {result.unique_orgs:,} unique orgs")


@app.command()
def stage2(
    stage1_path: Path = typer.Option(
        Path("data/interim/stage1_skilled_worker_A_rated_aggregated_by_org.csv"),
        "--input",
        "-i",
        help="Path to Stage 1 output CSV",
    ),
    out_dir: Path = typer.Option(
        Path("data/processed"),
        "--output-dir",
        "-o",
        help="Directory for output files",
    ),
    resume: bool = typer.Option(
        True,
        "--resume/--no-resume",
        help="Resume from previous run (skip already-processed orgs)",
    ),
) -> None:
    """Stage 2: Enrich Stage 1 output using Companies House API."""
    outs = run_stage2(stage1_path=stage1_path, out_dir=out_dir, resume=resume)
    rprint("[green]✓ Stage 2 complete:[/green]")
    for k, v in outs.items():
        rprint(f"  {k}: {v}")


@app.command()
def stage3(
    stage2_path: Path = typer.Option(
        Path("data/processed/stage2_enriched_companies_house.csv"),
        "--input",
        "-i",
        help="Path to Stage 2 enriched CSV",
    ),
    out_dir: Path = typer.Option(
        Path("data/processed"),
        "--output-dir",
        "-o",
        help="Directory for output files",
    ),
    threshold: Optional[float] = typer.Option(
        None,
        "--threshold",
        "-t",
        help="Override tech score threshold (default: 0.55)",
    ),
    region: Optional[list[str]] = typer.Option(
        None,
        "--region",
        "-r",
        help="Filter by region (repeatable, e.g. --region London --region Manchester)",
    ),
    postcode_prefix: Optional[list[str]] = typer.Option(
        None,
        "--postcode-prefix",
        "-p",
        help="Filter by postcode prefix (repeatable, e.g. --postcode-prefix EC --postcode-prefix SW)",
    ),
) -> None:
    """Stage 3: Score for tech-likelihood and produce shortlist.
    
    Supports geographic filtering with --region and --postcode-prefix options.
    """
    # Load base config and apply CLI overrides
    config = PipelineConfig.from_env()
    
    overrides = {}
    if threshold is not None:
        overrides["tech_score_threshold"] = threshold
    if region:
        overrides["geo_filter_regions"] = tuple(region)
    if postcode_prefix:
        overrides["geo_filter_postcodes"] = tuple(postcode_prefix)
    
    if overrides:
        config = config.with_overrides(**overrides)

    outs = run_stage3(stage2_path=stage2_path, out_dir=out_dir, config=config)
    rprint("[green]✓ Stage 3 complete:[/green]")
    for k, v in outs.items():
        rprint(f"  {k}: {v}")


@app.command(name="run-all")
def run_all(
    region: Optional[list[str]] = typer.Option(
        None,
        "--region",
        "-r",
        help="Filter final shortlist by region (repeatable)",
    ),
    postcode_prefix: Optional[list[str]] = typer.Option(
        None,
        "--postcode-prefix",
        "-p",
        help="Filter final shortlist by postcode prefix (repeatable)",
    ),
    threshold: Optional[float] = typer.Option(
        None,
        "--threshold",
        "-t",
        help="Override tech score threshold for Stage 3",
    ),
    skip_download: bool = typer.Option(
        False,
        "--skip-download",
        help="Skip download if raw CSV already exists",
    ),
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

    # Stage 2
    rprint("\n[bold cyan]═══ Stage 2: Companies House Enrichment ═══[/bold cyan]")
    stage2_outs = run_stage2()
    rprint(f"[green]✓ Enriched: {stage2_outs['enriched']}[/green]")

    # Stage 3
    rprint("\n[bold cyan]═══ Stage 3: Tech Scoring & Shortlist ═══[/bold cyan]")
    
    config = PipelineConfig.from_env()
    overrides = {}
    if threshold is not None:
        overrides["tech_score_threshold"] = threshold
    if region:
        overrides["geo_filter_regions"] = tuple(region)
    if postcode_prefix:
        overrides["geo_filter_postcodes"] = tuple(postcode_prefix)
    
    if overrides:
        config = config.with_overrides(**overrides)

    stage3_outs = run_stage3(config=config)
    
    rprint("\n[bold green]═══ Pipeline Complete ═══[/bold green]")
    rprint(f"Final shortlist: {stage3_outs['shortlist']}")
    rprint(f"Explainability: {stage3_outs['explain']}")
