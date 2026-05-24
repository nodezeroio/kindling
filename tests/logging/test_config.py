"""Tests for kindling.logging.configure() — spec §10.10."""

import logging

from kindling.logging import LoggingConfig, configure, trace
from kindling.logging import config as _config


def _kindling_stream_handlers() -> list[logging.StreamHandler]:
  return [
    h
    for h in logging.getLogger("kindling").handlers
    if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.NullHandler)
  ]


def test_partial_configure_merges_per_key() -> None:
  configure({"include_private": True})
  assert _config._current.include_private is True
  assert _config._current.log_return is True  # default preserved

  configure({"log_return": False})
  assert _config._current.include_private is True  # still set from earlier
  assert _config._current.log_return is False


def test_console_handler_idempotent() -> None:
  configure({"add_console_handler": True})
  configure({"add_console_handler": True})
  configure({"add_console_handler": True})
  assert len(_kindling_stream_handlers()) == 1


def test_console_handler_can_be_disabled() -> None:
  configure({"add_console_handler": True})
  assert len(_kindling_stream_handlers()) == 1
  configure({"add_console_handler": False})
  assert len(_kindling_stream_handlers()) == 0


def test_configure_level_applied() -> None:
  configure({"level": "DEBUG"})
  assert logging.getLogger("kindling").level == logging.DEBUG
  configure({"level": logging.WARNING})
  assert logging.getLogger("kindling").level == logging.WARNING


def test_configure_propagate_applied() -> None:
  configure({"propagate": False})
  assert logging.getLogger("kindling").propagate is False
  configure({"propagate": True})
  assert logging.getLogger("kindling").propagate is True


def test_per_decorator_overrides_configure_default(caplog) -> None:
  configure({"log_return": False})

  @trace({"log_return": True})
  def f() -> int:
    return 7

  caplog.set_level("DEBUG", logger=f.__module__)
  f()
  exit_records = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exit"]
  assert len(exit_records) == 1
  assert exit_records[0].kindling_return == "7"


def test_unset_per_decorator_inherits_configure_default(caplog) -> None:
  configure({"log_return": False})

  @trace
  def g() -> int:
    return 9

  caplog.set_level("DEBUG", logger=g.__module__)
  g()
  exit_records = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exit"]
  assert len(exit_records) == 1
  assert not hasattr(exit_records[0], "kindling_return")


def test_configure_after_decoration_affects_targets(caplog) -> None:
  @trace
  def h() -> int:
    return 42

  caplog.set_level("DEBUG", logger=h.__module__)
  configure({"log_return": False})
  h()
  exit_records = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exit"]
  assert len(exit_records) == 1
  assert not hasattr(exit_records[0], "kindling_return")


def test_loggingconfig_global_only_keys_accepted_by_configure() -> None:
  cfg: LoggingConfig = {
    "add_console_handler": True,
    "console_format": "%(message)s",
    "level": "DEBUG",
    "propagate": False,
    "include_private": True,
  }
  configure(cfg)
  assert _config._current.add_console_handler is True
  assert _config._current.console_format == "%(message)s"
  assert _config._current.include_private is True


def test_max_repr_length_none_distinguished_from_missing(caplog) -> None:
  configure({"max_repr_length": 50})
  assert _config._current.max_repr_length == 50
  configure({"max_repr_length": None})
  assert _config._current.max_repr_length is None
  configure({"include_private": True})  # absence should preserve None
  assert _config._current.max_repr_length is None
