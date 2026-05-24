"""Spec §10.2 + §10.6 — sync function tracing and decorator invocation forms."""

import logging

from kindling.logging import trace


@trace
def _add(a: int, b: int) -> int:
  return a + b


@trace({"log_return": False})
def _no_return(x: int) -> int:
  return x * 2


@trace({"log_arguments": False})
def _no_args(x: int) -> int:
  return x + 1


def test_sync_enter_logs_args(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_add.__module__)
  _add(1, 2)
  enters = [r for r in caplog.records if getattr(r, "kindling_event", None) == "enter"]
  assert len(enters) == 1
  assert enters[0].kindling_args == ["1", "2"]
  assert enters[0].kindling_kwargs == {}
  assert "_add" in enters[0].getMessage()


def test_sync_enter_logs_kwargs(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_add.__module__)
  _add(a=1, b=2)
  enters = [r for r in caplog.records if getattr(r, "kindling_event", None) == "enter"]
  assert enters[0].kindling_kwargs == {"a": "1", "b": "2"}


def test_sync_exit_logs_return(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_add.__module__)
  assert _add(1, 2) == 3
  exits = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exit"]
  assert len(exits) == 1
  assert exits[0].kindling_return == "3"


def test_bare_log_form_works(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_add.__module__)
  assert _add(2, 3) == 5
  events = [getattr(r, "kindling_event", None) for r in caplog.records]
  assert "enter" in events
  assert "exit" in events


def test_configured_log_form_disables_return(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_no_return.__module__)
  _no_return(5)
  exits = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exit"]
  assert len(exits) == 1
  assert not hasattr(exits[0], "kindling_return")


def test_configured_log_form_disables_arguments(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_no_args.__module__)
  _no_args(5)
  enters = [r for r in caplog.records if getattr(r, "kindling_event", None) == "enter"]
  assert len(enters) == 1
  assert not hasattr(enters[0], "kindling_args")
  assert not hasattr(enters[0], "kindling_kwargs")


def test_functools_wraps_preserves_metadata() -> None:
  assert _add.__name__ == "_add"
  assert _add.__wrapped__(1, 2) == 3  # type: ignore[attr-defined]
