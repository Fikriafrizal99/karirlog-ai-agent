"""Logging setup for the Execution Engine."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging(output_dir: str | Path = "data/output", level: int = logging.INFO) -> logging.Logger:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("karirlog_execution")
    root.setLevel(level)
    root.handlers.clear()

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(stream)

    file_handler = logging.FileHandler(out / "execution.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(file_handler)

    root.propagate = False
    return root
