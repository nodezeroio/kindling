"""Color-aware ``logging.Formatter`` for kindling's console output.

Wraps the ``%(levelname)s`` field in ANSI color codes selected by record level.
Colors auto-disable when the target stream is not a TTY, unless ``force_color``
is set. No global state; safe to attach to any handler.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping
from typing import Any, Literal, TextIO

_RESET = "\033[0m"

# Codes chosen to match the bash logging script this formatter is modeled on:
# log() -> blue, success() -> green, warn() -> yellow, error() -> red.
_LEVEL_COLORS: dict[int, str] = {
  logging.DEBUG: "\033[0;34m",
  logging.INFO: "\033[0;32m",
  logging.WARNING: "\033[1;33m",
  logging.ERROR: "\033[0;31m",
  logging.CRITICAL: "\033[0;31m",
}


class ColorFormatter(logging.Formatter):
  """A :class:`logging.Formatter` that colorizes the ``%(levelname)s`` field.

  The user-supplied format string is otherwise honored verbatim — timestamp,
  logger name, and message stay plain so colorized output remains grep-friendly.
  Color codes are emitted only when ``stream.isatty()`` is true, unless
  ``force_color=True``; this keeps escape sequences out of piped output and CI
  logs by default. ``stream`` defaults to :data:`sys.stderr` to match
  :class:`logging.StreamHandler`'s default.
  """

  def __init__(
    self,
    fmt: str | None = None,
    datefmt: str | None = None,
    style: Literal["%", "{", "$"] = "%",
    validate: bool = True,
    *,
    defaults: Mapping[str, Any] | None = None,
    stream: TextIO | None = None,
    force_color: bool = False,
  ) -> None:
    super().__init__(fmt, datefmt, style, validate, defaults=defaults)
    self._stream: TextIO = stream if stream is not None else sys.stderr
    self._force_color = force_color

  def _use_color(self) -> bool:
    if self._force_color:
      return True
    try:
      return self._stream.isatty()
    except (AttributeError, ValueError):
      return False

  def format(self, record: logging.LogRecord) -> str:
    color = _LEVEL_COLORS.get(record.levelno)
    if color is None or not self._use_color():
      return super().format(record)
    original = record.levelname
    record.levelname = f"{color}{original}{_RESET}"
    try:
      return super().format(record)
    finally:
      record.levelname = original
