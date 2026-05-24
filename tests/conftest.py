"""Shared test fixtures.

The autouse `reset_kindling_config` fixture is required for test isolation because
`kindling.logging.configure()` mutates module-level state and (potentially many)
loggers via the `attach_to` config key. It reaches into private module attributes
(`_current`, `_kindling_console_handler`, `_kindling_console_handler_targets`) on
purpose — that's the state we need to snapshot and restore. It also snapshots and
restores the handlers/level/propagate of every existing logger so a test that
attaches the managed handler to `"myapp"` cannot leak into the next test.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from kindling.logging import config as _config

_LoggerSnap = tuple[list[logging.Handler], int, bool]


def _snap(lg: logging.Logger) -> _LoggerSnap:
  return (lg.handlers[:], lg.level, lg.propagate)


def _restore(lg: logging.Logger, snap: _LoggerSnap) -> None:
  lg.handlers[:] = snap[0]
  lg.setLevel(snap[1])
  lg.propagate = snap[2]


@pytest.fixture(autouse=True)
def reset_kindling_config() -> Iterator[None]:
  saved_current = _config._current
  saved_handler = _config._kindling_console_handler
  saved_targets = _config._kindling_console_handler_targets

  pre: dict[str, _LoggerSnap] = {"": _snap(logging.getLogger())}
  for name, existing in list(logging.Logger.manager.loggerDict.items()):
    if isinstance(existing, logging.Logger):
      pre[name] = _snap(existing)
  pre.setdefault("kindling", _snap(logging.getLogger("kindling")))

  try:
    yield
  finally:
    # Detach the managed handler from its current targets first so subsequent
    # tests start with a fully clean slate, regardless of which loggers the
    # just-finished test attached it to.
    current_handler = _config._kindling_console_handler
    current_targets = _config._kindling_console_handler_targets
    if current_handler is not None:
      for name in current_targets:
        logging.getLogger(name).removeHandler(current_handler)

    _config._current = saved_current
    _config._kindling_console_handler = saved_handler
    _config._kindling_console_handler_targets = saved_targets

    # Restore every pre-existing logger; wipe any logger created during the test.
    for name, existing in list(logging.Logger.manager.loggerDict.items()):
      if not isinstance(existing, logging.Logger):
        continue
      snap = pre.get(name)
      if snap is not None:
        _restore(existing, snap)
      else:
        _restore(existing, ([], logging.NOTSET, True))
    _restore(logging.getLogger(), pre[""])


class ListHandler(logging.Handler):
  """Test handler that simply appends every record to a list."""

  def __init__(self) -> None:
    super().__init__(level=logging.DEBUG)
    self.records: list[logging.LogRecord] = []

  def emit(self, record: logging.LogRecord) -> None:
    self.records.append(record)


@pytest.fixture
def list_handler() -> ListHandler:
  return ListHandler()
