"""Spec §10.9 — structured kindling_* extras; consumer Filter can read/redact."""

import logging

import pytest

from kindling.logging import trace


@trace
def _ping(user: str, password: str) -> str:
  return f"hi {user}"


@trace
def _explode() -> None:
  raise RuntimeError("kaboom")


def test_enter_record_has_kindling_keys(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_ping.__module__)
  _ping("alice", password="hunter2")
  enters = [r for r in caplog.records if getattr(r, "kindling_event", None) == "enter"]
  assert len(enters) == 1
  rec = enters[0]
  assert rec.kindling_event == "enter"
  assert rec.kindling_qualname == "_ping"
  assert rec.kindling_module == _ping.__module__
  assert rec.kindling_args == ["'alice'"]
  assert rec.kindling_kwargs == {"password": "'hunter2'"}


def test_exit_record_has_kindling_return(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_ping.__module__)
  _ping("alice", password="x")
  exits = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exit"]
  assert exits[0].kindling_return == "'hi alice'"


def test_exception_record_has_kindling_exception_type(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_explode.__module__)
  with pytest.raises(RuntimeError):
    _explode()
  errors = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exception"]
  assert errors[0].kindling_exception_type == "RuntimeError"


def test_consumer_filter_can_redact_kwarg(caplog) -> None:
  class RedactPassword(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
      kwargs = getattr(record, "kindling_kwargs", None)
      if isinstance(kwargs, dict) and "password" in kwargs:
        kwargs["password"] = "'***'"
      return True

  logger = logging.getLogger(_ping.__module__)
  logger.addFilter(RedactPassword())
  try:
    caplog.set_level(logging.DEBUG, logger=_ping.__module__)
    _ping("alice", password="hunter2")
    enters = [r for r in caplog.records if getattr(r, "kindling_event", None) == "enter"]
    assert enters[0].kindling_kwargs == {"password": "'***'"}
  finally:
    logger.removeFilter(RedactPassword())
