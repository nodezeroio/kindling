"""Kindling logging module: decorator-based tracing and exception logging."""

import logging

from kindling.logging.config import DecoratorOptions, LoggingConfig, configure
from kindling.logging.decorators import trace

# Library citizenship: attach a NullHandler to the "kindling" logger so that
# importing the package never produces "no handler" warnings and never emits
# output unless a consumer opts in via configure().
logging.getLogger("kindling").addHandler(logging.NullHandler())

__all__ = ["DecoratorOptions", "LoggingConfig", "configure", "trace"]
