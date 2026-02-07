"""Package metadata for uk_sponsor_pipeline."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

_PACKAGE_NAME = "uk-sponsor-tech-hiring-pipeline"


def _resolve_version() -> str:
    try:
        return version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.0.0+unknown"


__version__ = _resolve_version()
