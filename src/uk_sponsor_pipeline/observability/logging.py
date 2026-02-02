"""Shared logging utilities for consistent pipeline observability.

Usage example:
    from uk_sponsor_pipeline.observability.logging import get_logger

    logger = get_logger("uk_sponsor_pipeline.transform_register")
    logger.info("Processing %s rows", row_count)
"""

from __future__ import annotations

import logging
import time

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def get_logger(name: str) -> logging.Logger:
    """Return a standard logger configured for UTC timestamps.

    Args:
        name: Logger name (use a stable module-qualified name).

    Returns:
        A logger with a single stream handler and a consistent UTC format.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)
        formatter.converter = time.gmtime
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
