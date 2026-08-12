"""Logging configuration for the Search Engine."""

from __future__ import annotations

import logging
from pathlib import Path

_CONFIGURED = False


def setup_logging(output_dir: str | Path = "data/output", level: int = logging.INFO) -> logging.Logger:
    """Configure root logging to stdout + data/output/search.log. Idempotent."""
    global _CONFIGURED
    logger = logging.getLogger("karirlog_search")
    if _CONFIGURED:
        return logger

    log_dir = Path(output_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "search.log"

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(stream)
    logger.addHandler(file_handler)
    logger.propagate = False

    _CONFIGURED = True
    return logger
