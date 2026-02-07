"""Run fixture-driven file-first CLI validation end to end."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from uk_sponsor_pipeline.application.companies_house_bulk import RAW_HEADERS_TRIMMED
from uk_sponsor_pipeline.schemas import (
    TRANSFORM_ENRICH_OUTPUT_COLUMNS,
    TRANSFORM_SCORE_EXPLAIN_COLUMNS,
    TRANSFORM_SCORE_OUTPUT_COLUMNS,
)

_REQUIRED_OUTPUTS = (
    "companies_house_enriched.csv",
    "companies_house_unmatched.csv",
    "companies_house_candidates_top3.csv",
    "companies_house_checkpoint.csv",
    "companies_house_resume_report.json",
    "companies_scored.csv",
    "companies_shortlist.csv",
    "companies_explain.csv",
)


class _SilentHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        _ = (format, args)


@contextmanager
def _local_server(root: Path) -> str:
    handler = partial(_SilentHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _write_csv(path: Path, headers: list[str], row: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerow(row)


def _build_sponsor_fixture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = ["Organisation Name", "Town/City", "County", "Type & Rating", "Route"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerow(["Acme Ltd", "London", "Greater London", "A Rating", "Skilled Worker"])
        writer.writerow(
            [
                "Unknown Engineering Collective",
                "London",
                "Greater London",
                "A Rating",
                "Skilled Worker",
            ]
        )


def _build_companies_house_fixture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = (
        ("ACME LTD", "12345678"),
        ("UNKNOWN WORKS LTD", "20000001"),
        ("ENGINEERING SERVICES LTD", "20000002"),
        ("COLLECTIVE SOLUTIONS LTD", "20000003"),
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(RAW_HEADERS_TRIMMED)
        for company_name, company_number in rows:
            row_by_header = {header: "" for header in RAW_HEADERS_TRIMMED}
            row_by_header["CompanyName"] = company_name
            row_by_header["CompanyNumber"] = company_number
            row_by_header["RegAddress.PostTown"] = "London"
            row_by_header["RegAddress.County"] = "Greater London"
            row_by_header["RegAddress.PostCode"] = "EC1A 1BB"
            row_by_header["CompanyCategory"] = "Private Limited Company"
            row_by_header["CompanyStatus"] = "Active"
            row_by_header["IncorporationDate"] = "2015-01-01"
            row_by_header["SICCode.SicText_1"] = (
                "62020 - Information technology consultancy activities"
            )
            row_by_header["URI"] = (
                f"http://data.companieshouse.gov.uk/doc/company/{company_number}"
            )
            writer.writerow([row_by_header[header] for header in RAW_HEADERS_TRIMMED])


def _build_fixture_payloads(http_root: Path) -> tuple[Path, Path]:
    sponsor_csv = http_root / "sponsor_register.csv"
    companies_house_csv = http_root / "BasicCompanyDataAsOneFile-2026-02-06.csv"
    companies_house_zip = http_root / "BasicCompanyDataAsOneFile-2026-02-06.zip"
    _build_sponsor_fixture(sponsor_csv)
    _build_companies_house_fixture(companies_house_csv)

    with ZipFile(companies_house_zip, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.write(companies_house_csv, arcname=companies_house_csv.name)

    return sponsor_csv, companies_house_zip


def _run_cli(command: list[str], *, env: dict[str, str], cwd: Path) -> None:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )
    if result.returncode != 0:
        joined = " ".join(command)
        raise RuntimeError(
            f"Command failed ({result.returncode}): {joined}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def _read_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader)


def _assert_required_outputs(processed_dir: Path) -> None:
    for filename in _REQUIRED_OUTPUTS:
        path = processed_dir / filename
        if not path.exists():
            raise RuntimeError(f"Required output is missing: {path}")

    enriched_headers = _read_headers(processed_dir / "companies_house_enriched.csv")
    scored_headers = _read_headers(processed_dir / "companies_scored.csv")
    shortlist_headers = _read_headers(processed_dir / "companies_shortlist.csv")
    explain_headers = _read_headers(processed_dir / "companies_explain.csv")
    _assert_columns(
        present=enriched_headers,
        required=list(TRANSFORM_ENRICH_OUTPUT_COLUMNS),
        label="companies_house_enriched.csv",
    )
    _assert_columns(
        present=scored_headers,
        required=list(TRANSFORM_SCORE_OUTPUT_COLUMNS),
        label="companies_scored.csv",
    )
    _assert_columns(
        present=shortlist_headers,
        required=list(TRANSFORM_SCORE_OUTPUT_COLUMNS),
        label="companies_shortlist.csv",
    )
    _assert_columns(
        present=explain_headers,
        required=list(TRANSFORM_SCORE_EXPLAIN_COLUMNS),
        label="companies_explain.csv",
    )

    resume_report_path = processed_dir / "companies_house_resume_report.json"
    resume_payload = json.loads(resume_report_path.read_text(encoding="utf-8"))
    if not isinstance(resume_payload, dict):
        raise RuntimeError("Resume report must be a JSON object.")
    status = resume_payload.get("status")
    if status not in {"complete", "error", "interrupted"}:
        raise RuntimeError(f"Resume report status is invalid: {status}")


def _assert_columns(*, present: list[str], required: list[str], label: str) -> None:
    missing = sorted(set(required) - set(present))
    if missing:
        raise RuntimeError(f"{label}: missing required columns: {missing}")


def _run_fixture_flow(*, work_dir: Path) -> None:
    http_root = work_dir / "http"
    runtime_root = work_dir / "runtime"
    snapshot_root = runtime_root / "snapshots"
    processed_dir = runtime_root / "processed"

    if work_dir.exists():
        shutil.rmtree(work_dir)
    http_root.mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)
    _build_fixture_payloads(http_root)

    repo_root = Path(__file__).resolve().parents[1]
    with _local_server(http_root) as server_base_url:
        sponsor_url = f"{server_base_url}/sponsor_register.csv"
        companies_house_url = f"{server_base_url}/BasicCompanyDataAsOneFile-2026-02-06.zip"
        env = os.environ.copy()
        env.update(
            {
                "CH_SOURCE_TYPE": "file",
                "SNAPSHOT_ROOT": str(snapshot_root),
                "TECH_SCORE_THRESHOLD": "0.0",
            }
        )

        commands = [
            [
                "uv",
                "run",
                "uk-sponsor",
                "refresh-sponsor",
                "--only",
                "acquire",
                "--snapshot-root",
                str(snapshot_root),
                "--url",
                sponsor_url,
            ],
            [
                "uv",
                "run",
                "uk-sponsor",
                "refresh-sponsor",
                "--only",
                "clean",
                "--snapshot-root",
                str(snapshot_root),
            ],
            [
                "uv",
                "run",
                "uk-sponsor",
                "refresh-companies-house",
                "--only",
                "acquire",
                "--snapshot-root",
                str(snapshot_root),
                "--url",
                companies_house_url,
            ],
            [
                "uv",
                "run",
                "uk-sponsor",
                "refresh-companies-house",
                "--only",
                "clean",
                "--snapshot-root",
                str(snapshot_root),
            ],
            [
                "uv",
                "run",
                "uk-sponsor",
                "transform-enrich",
                "--output-dir",
                str(processed_dir),
            ],
            [
                "uv",
                "run",
                "uk-sponsor",
                "transform-score",
                "--input",
                str(processed_dir / "companies_house_enriched.csv"),
                "--output-dir",
                str(processed_dir),
            ],
            [
                "uv",
                "run",
                "uk-sponsor",
                "usage-shortlist",
                "--input",
                str(processed_dir / "companies_scored.csv"),
                "--output-dir",
                str(processed_dir),
                "--threshold",
                "0.0",
            ],
        ]

        for command in commands:
            _run_cli(command, env=env, cwd=repo_root)

    _assert_required_outputs(processed_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build local fixtures, run grouped refresh and runtime commands, "
            "and validate required outputs."
        )
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional working directory for generated fixtures and outputs.",
    )
    args = parser.parse_args(argv)

    if args.work_dir is None:
        with tempfile.TemporaryDirectory(prefix="uk-sponsor-validation-e2e-") as temp_dir:
            work_dir = Path(temp_dir)
            _run_fixture_flow(work_dir=work_dir)
            print(f"PASS validation e2e fixture run: {work_dir}")
            return 0

    _run_fixture_flow(work_dir=args.work_dir)
    print(f"PASS validation e2e fixture run: {args.work_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
