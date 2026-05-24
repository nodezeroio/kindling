"""Spec §10.1 — INFO hides DEBUG trace records; DEBUG shows them; ERROR always fires."""

import logging

import pytest

from kindling.logging import trace


@trace
def _add(a: int, b: int) -> int:
  return a + b


@trace
def _bang() -> None:
  raise RuntimeError("boom")


def test_enter_exit_absent_at_info(caplog) -> None:
  caplog.set_level(logging.INFO, logger=_add.__module__)
  _add(1, 2)
  trace_records = [
    r for r in caplog.records if getattr(r, "kindling_event", None) in {"enter", "exit"}
  ]
  assert trace_records == []


def test_enter_exit_present_at_debug(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_add.__module__)
  _add(1, 2)
  events = [getattr(r, "kindling_event", None) for r in caplog.records]
  assert events.count("enter") == 1
  assert events.count("exit") == 1


def test_exception_at_error_regardless_of_level(caplog) -> None:
  caplog.set_level(logging.WARNING, logger=_bang.__module__)
  with pytest.raises(RuntimeError):
    _bang()
  error_records = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exception"]
  assert len(error_records) == 1
  assert error_records[0].levelno == logging.ERROR
