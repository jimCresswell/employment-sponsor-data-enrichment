"""Shared scoring profile fixtures for tests."""

from __future__ import annotations

import json
from pathlib import Path

from uk_sponsor_pipeline.protocols import FileSystem


def write_default_scoring_profile_catalog(*, fs: FileSystem, path: Path) -> None:
    """Write a valid scoring profile catalogue to the given filesystem path."""
    payload = {
        "schema_version": 1,
        "default_profile": "tech",
        "profiles": [
            {
                "name": "tech",
                "job_type": "software_engineering",
                "sector_signals": {"technology": 0.0},
                "location_signals": {},
                "size_signals": {},
                "sic_positive_prefixes": {"620": 0.5, "631": 0.4, "711": 0.15},
                "sic_negative_prefixes": {"871": -0.25, "561": -0.2},
                "keyword_positive": ["software", "cloud", "platform"],
                "keyword_negative": ["care", "restaurant"],
                "keyword_weights": {
                    "positive_per_match": 0.05,
                    "positive_cap": 0.15,
                    "negative_per_match": 0.05,
                    "negative_cap": 0.1,
                },
                "company_status_scores": {"active": 0.1, "inactive": 0.0},
                "company_age_scores": {
                    "unknown": 0.05,
                    "bands": [
                        {"min_years": 10.0, "score": 0.12},
                        {"min_years": 5.0, "score": 0.1},
                        {"min_years": 2.0, "score": 0.07},
                        {"min_years": 1.0, "score": 0.04},
                        {"min_years": 0.0, "score": 0.02},
                    ],
                },
                "company_type_weights": {
                    "ltd": 0.08,
                    "private-limited-company": 0.08,
                    "plc": 0.05,
                },
                "bucket_thresholds": {"strong": 0.55, "possible": 0.35},
            }
        ],
    }
    fs.write_text(json.dumps(payload), path)
