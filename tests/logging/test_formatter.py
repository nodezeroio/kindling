"""Tests for kindling.logging.formatter.ColorFormatter and its configure() integration."""

import io
import logging

from kindling.logging import ColorFormatter, configure
from kindling.logging import config as _config

_RESET = "\033[0m"
_LEVEL_CODES = {
  logging.DEBUG: "\033[0;34m",
  logging.INFO: "\033[0;32m",
  logging.WARNING: "\033[1;33m",
  logging.ERROR: "\033[0;31m",
  logging.CRITICAL: "\033[0;31m",
}


def _make_record(level: int, msg: str = "hello") -> logging.LogRecord:
  return logging.LogRecord(
    name="kindling.test",
    level=level,
    pathname=__file__,
    lineno=0,
    msg=msg,
    args=None,
    exc_info=None,
  )


def test_each_level_wraps_levelname_in_color_with_force_color() -> None:
  fmt = ColorFormatter("%(levelname)s %(message)s", force_color=True)
  for level, code in _LEVEL_CODES.items():
    rec = _make_record(level)
    out = fmt.format(rec)
    expected_level = f"{code}{logging.getLevelName(level)}{_RESET}"
    assert out.startswith(expected_level), f"level {level}: got {out!r}"


def test_no_color_on_non_tty_stream() -> None:
  fmt = ColorFormatter("%(levelname)s %(message)s", stream=io.StringIO())
  out = fmt.format(_make_record(logging.ERROR))
  assert "\033[" not in out
  assert out == "ERROR hello"


def test_force_color_emits_on_non_tty_stream() -> None:
  fmt = ColorFormatter("%(levelname)s %(message)s", stream=io.StringIO(), force_color=True)
  out = fmt.format(_make_record(logging.ERROR))
  assert _LEVEL_CODES[logging.ERROR] in out
  assert _RESET in out


def test_levelname_restored_after_format() -> None:
  fmt = ColorFormatter("%(levelname)s", force_color=True)
  rec = _make_record(logging.WARNING)
  fmt.format(rec)
  assert rec.levelname == "WARNING"  # not still wrapped in ANSI codes


def test_unknown_level_passes_through_without_color() -> None:
  fmt = ColorFormatter("%(levelname)s %(message)s", force_color=True)
  rec = _make_record(level=42, msg="custom")
  out = fmt.format(rec)
  assert "\033[" not in out


def test_format_string_otherwise_honored() -> None:
  fmt = ColorFormatter("%(name)s | %(levelname)s | %(message)s", force_color=True)
  out = fmt.format(_make_record(logging.INFO, msg="ok"))
  # Only levelname is wrapped; name and message stay plain.
  assert out.startswith("kindling.test | ")
  assert out.endswith(" | ok")
  assert _LEVEL_CODES[logging.INFO] in out


def _kindling_stream_handlers() -> list[logging.StreamHandler]:
  return [
    h
    for h in logging.getLogger("kindling").handlers
    if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.NullHandler)
  ]


def test_configure_color_true_attaches_color_formatter() -> None:
  configure({"add_console_handler": True, "color": True})
  handlers = _kindling_stream_handlers()
  assert len(handlers) == 1
  assert isinstance(handlers[0].formatter, ColorFormatter)


def test_configure_color_false_uses_plain_formatter() -> None:
  configure({"add_console_handler": True, "color": False})
  handlers = _kindling_stream_handlers()
  assert len(handlers) == 1
  assert handlers[0].formatter is not None
  assert not isinstance(handlers[0].formatter, ColorFormatter)
  assert isinstance(handlers[0].formatter, logging.Formatter)


def test_toggling_color_rebuilds_handler_without_duplicating() -> None:
  configure({"add_console_handler": True, "color": True})
  configure({"color": False})
  configure({"color": True})
  handlers = _kindling_stream_handlers()
  assert len(handlers) == 1
  assert isinstance(handlers[0].formatter, ColorFormatter)


def test_color_setting_persisted_across_calls() -> None:
  configure({"color": True})
  assert _config._current.color is True
  configure({"add_console_handler": True})
  handlers = _kindling_stream_handlers()
  assert len(handlers) == 1
  assert isinstance(handlers[0].formatter, ColorFormatter)
