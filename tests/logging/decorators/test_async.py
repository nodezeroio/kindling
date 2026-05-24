"""Spec §10.3 — async function tracing without pytest-asyncio dep."""

import asyncio
import logging

import pytest

from kindling.logging import trace


@trace
async def _fetch() -> int:
  return 42


@trace
async def _boom() -> None:
  raise ValueError("nope")


def test_async_function_logs_awaited_result(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_fetch.__module__)
  result = asyncio.run(_fetch())
  assert result == 42
  exits = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exit"]
  assert len(exits) == 1
  assert exits[0].kindling_return == "42"


def test_async_exception_logged_and_reraised(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_boom.__module__)
  with pytest.raises(ValueError):
    asyncio.run(_boom())
  errors = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exception"]
  assert len(errors) == 1
  assert errors[0].levelno == logging.ERROR
  assert errors[0].kindling_exception_type == "ValueError"
