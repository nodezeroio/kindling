"""Verify that importing kindling.logging attaches a NullHandler to the kindling logger."""

import logging

import kindling.logging  # noqa: F401 - import side effect under test


def test_null_handler_attached_to_kindling_logger() -> None:
  kindling_logger = logging.getLogger("kindling")
  null_handlers = [h for h in kindling_logger.handlers if isinstance(h, logging.NullHandler)]
  assert len(null_handlers) >= 1


def test_public_surface_exports() -> None:
  from kindling.logging import DecoratorOptions, LoggingConfig, configure, trace

  assert callable(trace)
  assert callable(configure)
  assert DecoratorOptions is not None
  assert LoggingConfig is not None
