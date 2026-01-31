from __future__ import annotations

import typer
from rich import print as rprint

from .stages.download import download_latest
from .stages.stage1 import run_stage1
from .stages.stage2_companies_house import run_stage2
from .stages.stage3_scoring import run_stage3

app = typer.Typer(add_completion=False, help="UK sponsor register pipeline CLI")


@app.command()
def download():
    """Download the latest sponsor register CSV from GOV.UK."""
    out = download_latest()
    rprint(f"[green]Downloaded:[/green] {out}")


@app.command()
def stage1():
    """Stage 1: Skilled Worker + A-rated + aggregate organisations."""
    out = run_stage1()
    rprint(f"[green]Stage 1 output:[/green] {out}")


@app.command()
def stage2():
    """Stage 2: Enrich Stage 1 output using Companies House API."""
    outs = run_stage2()
    rprint("[green]Stage 2 outputs:[/green]")
    for k, v in outs.items():
        rprint(f"  - {k}: {v}")


@app.command()
def stage3():
    """Stage 3: Score for tech-likelihood using SIC codes + heuristics."""
    outs = run_stage3()
    rprint("[green]Stage 3 outputs:[/green]")
    for k, v in outs.items():
        rprint(f"  - {k}: {v}")
