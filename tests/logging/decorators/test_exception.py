"""Spec §10.5 — exceptions logged at ERROR with traceback; bare re-raise preserves info."""

import logging
import traceback

import pytest

from kindling.logging import trace


class _CustomError(Exception):
  pass


@trace
def _raises() -> None:
  raise _CustomError("specific")


@trace
def _inner() -> None:
  raise ValueError("from inner")


@trace
def _outer() -> None:
  _inner()


def test_exception_record_emitted_at_error_with_exc_info(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_raises.__module__)
  with pytest.raises(_CustomError):
    _raises()
  errors = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exception"]
  assert len(errors) == 1
  assert errors[0].levelno == logging.ERROR
  assert errors[0].exc_info is not None
  assert errors[0].exc_info[0] is _CustomError


def test_original_traceback_preserved_after_reraise(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_raises.__module__)
  try:
    _raises()
  except _CustomError as exc:
    tb_text = "".join(traceback.format_tb(exc.__traceback__))
    assert "_raises" in tb_text
  else:
    pytest.fail("expected _CustomError")


def test_original_exception_type_not_chained_or_wrapped() -> None:
  with pytest.raises(_CustomError) as info:
    _raises()
  assert info.value.__cause__ is None


def test_nested_exception_propagates_through_both_wrappers(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_outer.__module__)
  with pytest.raises(ValueError):
    _outer()
  errors = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exception"]
  # Both _inner and _outer wrappers log the escaped exception.
  assert len(errors) == 2
