"""Shared test fixtures.

The autouse `reset_kindling_config` fixture is required for test isolation because
`kindling.logging.configure()` mutates module-level state and the "kindling" logger.
It reaches into private module attributes (`_current`, `_kindling_console_handler`)
on purpose — that's the state we need to snapshot and restore.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from kindling.logging import config as _config


@pytest.fixture(autouse=True)
def reset_kindling_config() -> Iterator[None]:
  saved_current = _config._current
  saved_handler = _config._kindling_console_handler
  kindling_logger = logging.getLogger("kindling")
  saved_level = kindling_logger.level
  saved_propagate = kindling_logger.propagate
  saved_handlers = kindling_logger.handlers[:]
  try:
    yield
  finally:
    _config._current = saved_current
    _config._kindling_console_handler = saved_handler
    kindling_logger.setLevel(saved_level)
    kindling_logger.propagate = saved_propagate
    kindling_logger.handlers[:] = saved_handlers


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
