"""Logging configuration for power_scrapper."""

from __future__ import annotations

import logging
import sys


def setup_logging(debug: bool = False) -> logging.Logger:
    """Configure and return the package-level logger.

    Parameters
    ----------
    debug:
        When *True* the log level is set to ``DEBUG``; otherwise ``INFO``.

    Returns
    -------
    logging.Logger
        Logger named ``"power_scrapper"``.
    """
    logger = logging.getLogger("power_scrapper")

    # Avoid adding duplicate handlers when called more than once.
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)

    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    return logger
