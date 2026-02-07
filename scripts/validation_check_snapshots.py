"""Validate refresh snapshot artefacts for file-first protocol runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from uk_sponsor_pipeline.devtools.validation_snapshots import (
    SnapshotValidationError,
    validate_snapshots,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate sponsor and Companies House snapshots.",
    )
    parser.add_argument(
        "--snapshot-root",
        required=True,
        type=Path,
        help="Snapshot root directory to validate.",
    )
    args = parser.parse_args(argv)

    try:
        result = validate_snapshots(args.snapshot_root)
    except SnapshotValidationError as exc:
        print(f"FAIL snapshot validation: {exc}", file=sys.stderr)
        return 1

    print(f"PASS snapshot validation: {result.snapshot_root}")
    for dataset in result.datasets:
        print(f"- {dataset.dataset}: {dataset.snapshot_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
