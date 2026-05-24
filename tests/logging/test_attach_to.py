"""Tests for the `attach_to` LoggingConfig key and the multi-logger handler routing."""

import io
import logging

from kindling.logging import config as _config
from kindling.logging import configure, trace


def _capture_managed_stream() -> io.StringIO:
  """Replace the managed handler's stream with a StringIO and return the buffer."""
  handler = _config._kindling_console_handler
  assert isinstance(handler, logging.StreamHandler)
  buf = io.StringIO()
  handler.setStream(buf)
  return buf


def test_attach_to_default_is_kindling() -> None:
  assert _config._current.attach_to == ("kindling",)


def test_default_attaches_handler_to_kindling_logger() -> None:
  configure({"add_console_handler": True})
  handler = _config._kindling_console_handler
  assert handler is not None
  assert handler in logging.getLogger("kindling").handlers
  assert _config._kindling_console_handler_targets == ("kindling",)


def test_custom_attach_to_attaches_to_named_logger_only() -> None:
  configure({"add_console_handler": True, "attach_to": ["myapp"]})
  handler = _config._kindling_console_handler
  assert handler is not None
  assert handler in logging.getLogger("myapp").handlers
  assert handler not in logging.getLogger("kindling").handlers


def test_attach_to_multiple_loggers() -> None:
  configure({"add_console_handler": True, "attach_to": ["alpha", "beta", "kindling"]})
  handler = _config._kindling_console_handler
  assert handler is not None
  assert handler in logging.getLogger("alpha").handlers
  assert handler in logging.getLogger("beta").handlers
  assert handler in logging.getLogger("kindling").handlers


def test_reconfigure_narrows_attach_to_detaches_old_targets() -> None:
  configure({"add_console_handler": True, "attach_to": ["a", "b"]})
  first_handler = _config._kindling_console_handler
  assert first_handler is not None
  assert first_handler in logging.getLogger("a").handlers
  assert first_handler in logging.getLogger("b").handlers

  configure({"attach_to": ["c"]})
  new_handler = _config._kindling_console_handler
  assert new_handler is not None
  assert first_handler not in logging.getLogger("a").handlers
  assert first_handler not in logging.getLogger("b").handlers
  assert new_handler in logging.getLogger("c").handlers


def test_attach_to_root_via_empty_string() -> None:
  configure({"add_console_handler": True, "attach_to": [""]})
  handler = _config._kindling_console_handler
  assert handler is not None
  assert handler in logging.getLogger().handlers


def test_duplicate_names_in_attach_to_are_deduped() -> None:
  configure({"add_console_handler": True, "attach_to": ["x", "x", "y", "x"]})
  handler = _config._kindling_console_handler
  assert handler is not None
  assert logging.getLogger("x").handlers.count(handler) == 1
  assert logging.getLogger("y").handlers.count(handler) == 1
  assert _config._current.attach_to == ("x", "y")


def test_level_applied_to_every_attach_to_logger() -> None:
  configure({"add_console_handler": True, "attach_to": ["alpha", "beta"], "level": "DEBUG"})
  assert logging.getLogger("alpha").level == logging.DEBUG
  assert logging.getLogger("beta").level == logging.DEBUG


def test_propagate_applied_to_every_attach_to_logger() -> None:
  configure({"add_console_handler": True, "attach_to": ["alpha", "beta"], "propagate": False})
  assert logging.getLogger("alpha").propagate is False
  assert logging.getLogger("beta").propagate is False


def test_trace_records_flow_through_managed_handler() -> None:
  """End-to-end: a @trace-decorated function in the consumer's namespace surfaces."""
  target = "tests.logging.attached_trace"
  configure(
    {
      "add_console_handler": True,
      "attach_to": [target],
      "level": "DEBUG",
      "console_format": "%(levelname)s %(name)s %(message)s",
    }
  )
  buf = _capture_managed_stream()

  def f() -> int:
    return 7

  f.__module__ = target
  decorated = trace(f)
  assert decorated() == 7

  output = buf.getvalue()
  assert "DEBUG" in output
  assert target in output
  # Both enter and exit records emit; loose substring checks keep us format-agnostic.
  assert output.count("DEBUG") >= 2


def test_inline_log_flows_through_managed_handler() -> None:
  """End-to-end: a plain log.info(...) under the consumer's namespace surfaces."""
  target = "tests.logging.attached_inline"
  configure(
    {
      "add_console_handler": True,
      "attach_to": [target],
      "level": "DEBUG",
      "console_format": "%(levelname)s %(name)s %(message)s",
    }
  )
  buf = _capture_managed_stream()

  logging.getLogger(f"{target}.submodule").info("inline-call-marker")

  output = buf.getvalue()
  assert "INFO" in output
  assert "inline-call-marker" in output


def test_disable_handler_detaches_from_all_targets() -> None:
  configure({"add_console_handler": True, "attach_to": ["a", "b"]})
  handler = _config._kindling_console_handler
  assert handler is not None
  configure({"add_console_handler": False})
  assert _config._kindling_console_handler is None
  assert handler not in logging.getLogger("a").handlers
  assert handler not in logging.getLogger("b").handlers
