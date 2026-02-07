"""Validate processed pipeline outputs for file-first protocol runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from uk_sponsor_pipeline.devtools.validation_outputs import (
    OutputValidationError,
    validate_outputs,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate processed output artefacts and resume report.",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        type=Path,
        help="Processed output directory to validate.",
    )
    args = parser.parse_args(argv)

    try:
        result = validate_outputs(args.out_dir)
    except OutputValidationError as exc:
        print(f"FAIL output validation: {exc}", file=sys.stderr)
        return 1

    print(f"PASS output validation: {result.out_dir}")
    print(f"- resume status: {result.resume_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
