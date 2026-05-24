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
  attach_to: list[str]


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
  attach_to: tuple[str, ...] = (_KINDLING_LOGGER_NAME,)


_DEFAULTS: _ResolvedConfig = _ResolvedConfig()
_current: _ResolvedConfig = _DEFAULTS
_kindling_console_handler: logging.Handler | None = None
_kindling_console_handler_targets: tuple[str, ...] = ()
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
  "attach_to",
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
  - **Console handler idempotency:** the single managed handler instance is detached
    from every logger it was previously attached to before a fresh one is built, so
    repeated calls never stack duplicates.
  - **``attach_to``:** controls which loggers the managed console handler is attached
    to (default: ``["kindling"]``). Names may be any valid logger name, including
    ``""`` for the root logger. Duplicates are silently de-duplicated, preserving
    first occurrence order. When present, ``level`` and ``propagate`` are also
    applied to every logger named in the (post-merge) ``attach_to``.
  """
  global _current, _kindling_console_handler, _kindling_console_handler_targets
  with _lock:
    changes: dict[str, Any] = {}
    for key in _ALL_KEYS:
      if key in config:
        if key == "attach_to":
          # Dedupe while preserving first-occurrence order; store as tuple for frozen dataclass.
          changes[key] = tuple(dict.fromkeys(config[key]))  # type: ignore[literal-required]
        else:
          changes[key] = config[key]  # type: ignore[literal-required]
    new_config = dataclasses.replace(_current, **changes)
    _current = new_config

    if "level" in config and new_config.level is not None:
      for name in new_config.attach_to:
        logging.getLogger(name).setLevel(new_config.level)
    if "propagate" in config:
      for name in new_config.attach_to:
        logging.getLogger(name).propagate = new_config.propagate

    if (
      "add_console_handler" in config
      or "console_format" in config
      or "color" in config
      or "attach_to" in config
    ):
      if _kindling_console_handler is not None:
        for name in _kindling_console_handler_targets:
          logging.getLogger(name).removeHandler(_kindling_console_handler)
        _kindling_console_handler = None
        _kindling_console_handler_targets = ()
      if new_config.add_console_handler:
        handler = logging.StreamHandler()
        formatter: logging.Formatter
        if new_config.color:
          formatter = ColorFormatter(new_config.console_format, stream=handler.stream)
        else:
          formatter = logging.Formatter(new_config.console_format)
        handler.setFormatter(formatter)
        for name in new_config.attach_to:
          logging.getLogger(name).addHandler(handler)
        _kindling_console_handler = handler
        _kindling_console_handler_targets = new_config.attach_to
