"""Spec §10.11 — decorated functions log under getLogger(func.__module__)."""

import logging

from kindling.logging import trace


@trace
def _f() -> int:
  return 1


def test_records_emit_on_function_module_logger(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_f.__module__)
  _f()
  records = [r for r in caplog.records if getattr(r, "kindling_event", None) in {"enter", "exit"}]
  assert len(records) == 2
  for r in records:
    assert r.name == _f.__module__
    assert r.name != "kindling"
