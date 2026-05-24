"""Spec §10.4 — generator call is traced; per-yield iteration is NOT."""

import logging
from collections.abc import AsyncIterator, Iterator

from kindling.logging import trace


@trace
def _counter(n: int) -> Iterator[int]:
  yield from range(n)


@trace
async def _async_counter(n: int) -> AsyncIterator[int]:
  for i in range(n):
    yield i


def test_generator_call_traced_iteration_not_traced(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_counter.__module__)
  gen = _counter(3)
  enters = [r for r in caplog.records if getattr(r, "kindling_event", None) == "enter"]
  exits = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exit"]
  assert len(enters) == 1
  assert len(exits) == 1
  assert "generator" in exits[0].kindling_return

  records_before_iteration = len(caplog.records)
  assert list(gen) == [0, 1, 2]
  records_after_iteration = len(caplog.records)
  assert records_before_iteration == records_after_iteration


def test_async_generator_call_traced_iteration_not_traced(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_async_counter.__module__)
  agen = _async_counter(2)
  enters = [r for r in caplog.records if getattr(r, "kindling_event", None) == "enter"]
  exits = [r for r in caplog.records if getattr(r, "kindling_event", None) == "exit"]
  assert len(enters) == 1
  assert len(exits) == 1

  records_before = len(caplog.records)

  import asyncio

  async def drain() -> list[int]:
    out: list[int] = []
    async for x in agen:
      out.append(x)
    return out

  assert asyncio.run(drain()) == [0, 1]
  assert len(caplog.records) == records_before
