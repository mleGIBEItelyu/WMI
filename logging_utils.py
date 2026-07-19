"""Lightweight logging helpers.

Uses `rich` when available for readable terminal output, and degrades
gracefully to stdlib logging when it is not installed.
"""

from __future__ import annotations

import logging

try:  # pragma: no cover - presentation only
    from rich.console import Console
    from rich.logging import RichHandler

    _console: "Console | None" = Console(stderr=True)
    _handler: logging.Handler = RichHandler(
        console=_console, show_path=False, rich_tracebacks=True, markup=True
    )
    _FMT = "%(message)s"
except Exception:  # pragma: no cover - fallback path
    _console = None
    _handler = logging.StreamHandler()
    _FMT = "%(asctime)s [%(levelname)s] %(message)s"


def configure(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    _handler.setFormatter(logging.Formatter(_FMT, datefmt="%H:%M:%S"))
    root = logging.getLogger("wmi")
    root.handlers.clear()
    root.addHandler(_handler)
    root.setLevel(level)
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"wmi.{name}")
