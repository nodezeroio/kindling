"""Configuration types, defaults, and the `configure()` function for kindling.logging.

Module-level state for decorator defaults lives here. The decorator reads the current
snapshot via `_current_options()` on every invocation, so a `configure()` call made
after decoration takes effect immediately.
"""

from __future__ import annotations

import dataclasses
import logging
import threading
from typing import Any, TypedDict

from kindling.logging.formatter import ColorFormatter


class DecoratorOptions(TypedDict, total=False):
  """Options meaningful on an individual ``@trace`` target.

  Also valid as ``configure()`` defaults. All keys are optional. Note that because
  ``bool`` is a subtype of ``int`` in Python, ``{"max_repr_length": True}`` will
  type-check but is almost certainly a mistake; pass an explicit ``int`` or ``None``.
  """

  include_private: bool
  include_dunder: bool
  log_arguments: bool
  log_return: bool
  max_repr_length: int | None


class LoggingConfig(DecoratorOptions, total=False):
  """Full library configuration accepted by :func:`configure`.

  Superset of :class:`DecoratorOptions` plus the global-only keys. Decorator-relevant
  keys (those inherited from :class:`DecoratorOptions`) establish the defaults used by
  ``@trace`` when an option is not specified on the decorator itself.
  """

  level: int | str
  add_console_handler: bool
  console_format: str
  propagate: bool
  color: bool


_KINDLING_LOGGER_NAME = "kindling"
_DEFAULT_CONSOLE_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"


@dataclasses.dataclass(frozen=True, slots=True)
class _ResolvedConfig:
  """Fully-resolved snapshot of the current library configuration.

  This is the immutable struct the decorator reads on every invocation. ``configure``
  rebinds the module-level singleton rather than mutating in place, so a wrapper that
  reads the snapshot at the top of a call cannot see a torn state mid-call.
  """

  include_private: bool = False
  include_dunder: bool = False
  log_arguments: bool = True
  log_return: bool = True
  max_repr_length: int | None = 1000
  level: int | str | None = None
  add_console_handler: bool = False
  console_format: str = _DEFAULT_CONSOLE_FORMAT
  propagate: bool = True
  color: bool = False


_DEFAULTS: _ResolvedConfig = _ResolvedConfig()
_current: _ResolvedConfig = _DEFAULTS
_kindling_console_handler: logging.Handler | None = None
_lock = threading.Lock()

_ALL_KEYS: tuple[str, ...] = (
  "include_private",
  "include_dunder",
  "log_arguments",
  "log_return",
  "max_repr_length",
  "level",
  "add_console_handler",
  "console_format",
  "propagate",
  "color",
)


def _current_options() -> _ResolvedConfig:
  """Return the current resolved configuration snapshot. Lock-free hot path."""
  return _current


def configure(config: LoggingConfig) -> None:
  """Merge ``config`` into the current library configuration.

  Semantics:
  - **Partial / optional:** any subset of keys may be provided. Missing keys are
    preserved at their current value (last-writer-wins per key across calls).
  - **``None`` vs missing for ``max_repr_length``:** an explicit ``None`` disables
    truncation; omitting the key preserves the current value.
  - **Console handler idempotency:** repeated calls never stack duplicate
    kindling-owned console handlers. The single tracked handler is removed before a
    fresh one is attached.
  """
  global _current, _kindling_console_handler
  with _lock:
    changes: dict[str, Any] = {}
    for key in _ALL_KEYS:
      if key in config:
        changes[key] = config[key]  # type: ignore[literal-required]
    new_config = dataclasses.replace(_current, **changes)
    _current = new_config

    kindling_logger = logging.getLogger(_KINDLING_LOGGER_NAME)
    if "level" in config and new_config.level is not None:
      kindling_logger.setLevel(new_config.level)
    if "propagate" in config:
      kindling_logger.propagate = new_config.propagate

    if "add_console_handler" in config or "console_format" in config or "color" in config:
      if _kindling_console_handler is not None:
        kindling_logger.removeHandler(_kindling_console_handler)
        _kindling_console_handler = None
      if new_config.add_console_handler:
        handler = logging.StreamHandler()
        formatter: logging.Formatter
        if new_config.color:
          formatter = ColorFormatter(new_config.console_format, stream=handler.stream)
        else:
          formatter = logging.Formatter(new_config.console_format)
        handler.setFormatter(formatter)
        kindling_logger.addHandler(handler)
        _kindling_console_handler = handler
