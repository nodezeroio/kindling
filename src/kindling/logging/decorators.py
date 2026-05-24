"""The ``@trace`` decorator and its supporting machinery.

Supports four invocation forms (bare/configured × function/class) and four target
kinds (plain function, coroutine function, generator function, async-generator
function). Generators and async generators are call-only-traced in v1 — the call
produces enter/exit records but per-yield iteration is NOT traced.
"""

from __future__ import annotations

import dataclasses
import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any, Protocol, cast, overload

from kindling.logging.config import DecoratorOptions, _current_options


class _UnsetType:
  """Singleton marker class for "option not specified on this decorator"."""

  _instance: _UnsetType | None = None

  def __new__(cls) -> _UnsetType:
    if cls._instance is None:
      cls._instance = super().__new__(cls)
    return cls._instance

  def __repr__(self) -> str:
    return "<UNSET>"


_UNSET = _UnsetType()


@dataclasses.dataclass(frozen=True, slots=True)
class _FixedOpts:
  """Sparse view of options explicitly set on a single ``@trace`` invocation.

  Built once at decoration time. Fields default to ``_UNSET`` so that
  :func:`_resolve_opts` can overlay them on the live global defaults at call time.
  """

  include_private: bool | _UnsetType = _UNSET
  include_dunder: bool | _UnsetType = _UNSET
  log_arguments: bool | _UnsetType = _UNSET
  log_return: bool | _UnsetType = _UNSET
  max_repr_length: int | None | _UnsetType = _UNSET


@dataclasses.dataclass(frozen=True, slots=True)
class _ResolvedOpts:
  """All five decorator-relevant options resolved to concrete values."""

  include_private: bool
  include_dunder: bool
  log_arguments: bool
  log_return: bool
  max_repr_length: int | None


_RECURSION_BLOCKLIST: frozenset[str] = frozenset(
  {
    "__repr__",
    "__str__",
    "__format__",
    "__hash__",
    "__eq__",
    "__ne__",
    "__getattribute__",
  }
)


_TRUNCATION_MARKER = "...<truncated>"


def _options_dict_to_fixed(opts: DecoratorOptions) -> _FixedOpts:
  """Translate a user-facing options dict into the internal sparse struct.

  Uses ``key in opts`` rather than ``.get()`` so that an explicit
  ``{"max_repr_length": None}`` is distinguishable from omission.
  """
  fields: dict[str, Any] = {}
  if "include_private" in opts:
    fields["include_private"] = opts["include_private"]
  if "include_dunder" in opts:
    fields["include_dunder"] = opts["include_dunder"]
  if "log_arguments" in opts:
    fields["log_arguments"] = opts["log_arguments"]
  if "log_return" in opts:
    fields["log_return"] = opts["log_return"]
  if "max_repr_length" in opts:
    fields["max_repr_length"] = opts["max_repr_length"]
  return _FixedOpts(**fields)


def _resolve_opts(fixed: _FixedOpts) -> _ResolvedOpts:
  """Overlay per-decorator explicit options on the live global defaults."""
  current = _current_options()
  return _ResolvedOpts(
    include_private=(
      current.include_private
      if isinstance(fixed.include_private, _UnsetType)
      else fixed.include_private
    ),
    include_dunder=(
      current.include_dunder
      if isinstance(fixed.include_dunder, _UnsetType)
      else fixed.include_dunder
    ),
    log_arguments=(
      current.log_arguments if isinstance(fixed.log_arguments, _UnsetType) else fixed.log_arguments
    ),
    log_return=(
      current.log_return if isinstance(fixed.log_return, _UnsetType) else fixed.log_return
    ),
    max_repr_length=(
      current.max_repr_length
      if isinstance(fixed.max_repr_length, _UnsetType)
      else fixed.max_repr_length
    ),
  )


def _safe_repr(value: object, max_len: int | None) -> str:
  """Defensively render ``value`` to a string, never raising.

  - If ``repr(value)`` raises (including ``BaseException`` like ``SystemExit`` from a
    pathological ``__repr__``), returns a placeholder. Logging must never crash the
    application, even when an object's ``__repr__`` is broken.
  - If ``max_len`` is ``None``, returns the full repr (no truncation).
  - If ``max_len`` is a positive int and the repr exceeds it, returns
    ``repr[:max_len] + "...<truncated>"``. The marker is metadata; total length
    intentionally exceeds ``max_len`` by the marker's length.
  """
  try:
    rendered = repr(value)
  except BaseException as exc:  # noqa: BLE001 - logging must never crash the app
    return f"<unreprable {type(value).__name__}: {type(exc).__name__}>"
  if max_len is None:
    return rendered
  if len(rendered) <= max_len:
    return rendered
  return rendered[:max_len] + _TRUNCATION_MARKER


def _build_enter_extra(
  qualname: str,
  module: str,
  args: tuple[Any, ...],
  kwargs: dict[str, Any],
  opts: _ResolvedOpts,
) -> dict[str, Any]:
  extra: dict[str, Any] = {
    "kindling_event": "enter",
    "kindling_qualname": qualname,
    "kindling_module": module,
  }
  if opts.log_arguments:
    extra["kindling_args"] = [_safe_repr(a, opts.max_repr_length) for a in args]
    extra["kindling_kwargs"] = {k: _safe_repr(v, opts.max_repr_length) for k, v in kwargs.items()}
  return extra


def _build_exit_extra(
  qualname: str,
  module: str,
  result: Any,
  opts: _ResolvedOpts,
) -> dict[str, Any]:
  extra: dict[str, Any] = {
    "kindling_event": "exit",
    "kindling_qualname": qualname,
    "kindling_module": module,
  }
  if opts.log_return:
    extra["kindling_return"] = _safe_repr(result, opts.max_repr_length)
  return extra


def _build_exception_extra(
  qualname: str,
  module: str,
  exc: BaseException,
) -> dict[str, Any]:
  return {
    "kindling_event": "exception",
    "kindling_qualname": qualname,
    "kindling_module": module,
    "kindling_exception_type": type(exc).__name__,
  }


def _format_enter_message(
  qualname: str,
  args: tuple[Any, ...],
  kwargs: dict[str, Any],
  opts: _ResolvedOpts,
) -> str:
  if not opts.log_arguments:
    return f"-> {qualname}(...)"
  rendered_args = ", ".join(_safe_repr(a, opts.max_repr_length) for a in args)
  rendered_kwargs = ", ".join(
    f"{k}={_safe_repr(v, opts.max_repr_length)}" for k, v in kwargs.items()
  )
  parts = [p for p in (rendered_args, rendered_kwargs) if p]
  return f"-> {qualname}({', '.join(parts)})"


def _format_exit_message(qualname: str, result: Any, opts: _ResolvedOpts) -> str:
  if not opts.log_return:
    return f"<- {qualname}"
  return f"<- {qualname} returned {_safe_repr(result, opts.max_repr_length)}"


def _format_exception_message(qualname: str, exc: BaseException) -> str:
  return f"!! {qualname} raised {type(exc).__name__}: {exc}"


def _log_escaped_exception(
  logger: logging.Logger,
  qualname: str,
  module: str,
  exc: BaseException,
) -> None:
  # FUTURE EXTENSION POINT: when a per-exception-type handler registry is added,
  # dispatch happens here BEFORE the logger.error call. v1 just logs.
  logger.error(
    _format_exception_message(qualname, exc),
    exc_info=exc,
    extra=_build_exception_extra(qualname, module, exc),
  )


def _make_sync_wrapper(func: Callable[..., Any], fixed: _FixedOpts) -> Callable[..., Any]:
  module = func.__module__
  qualname = func.__qualname__

  @functools.wraps(func)
  def wrapper(*args: Any, **kwargs: Any) -> Any:
    opts = _resolve_opts(fixed)
    logger = logging.getLogger(module)
    logger.debug(
      _format_enter_message(qualname, args, kwargs, opts),
      extra=_build_enter_extra(qualname, module, args, kwargs, opts),
    )
    try:
      result = func(*args, **kwargs)
    except BaseException as exc:
      _log_escaped_exception(logger, qualname, module, exc)
      raise
    logger.debug(
      _format_exit_message(qualname, result, opts),
      extra=_build_exit_extra(qualname, module, result, opts),
    )
    return result

  return wrapper


def _make_async_wrapper(func: Callable[..., Any], fixed: _FixedOpts) -> Callable[..., Any]:
  module = func.__module__
  qualname = func.__qualname__

  @functools.wraps(func)
  async def wrapper(*args: Any, **kwargs: Any) -> Any:
    opts = _resolve_opts(fixed)
    logger = logging.getLogger(module)
    logger.debug(
      _format_enter_message(qualname, args, kwargs, opts),
      extra=_build_enter_extra(qualname, module, args, kwargs, opts),
    )
    try:
      result = await func(*args, **kwargs)
    except BaseException as exc:
      _log_escaped_exception(logger, qualname, module, exc)
      raise
    logger.debug(
      _format_exit_message(qualname, result, opts),
      extra=_build_exit_extra(qualname, module, result, opts),
    )
    return result

  return wrapper


def _decorate_callable(func: Callable[..., Any], fixed: _FixedOpts) -> Callable[..., Any]:
  """Dispatch on the original function's kind, then wrap.

  Detection MUST happen on the original function — if we wrapped a coroutine with the
  sync wrapper, ``inspect.iscoroutinefunction(wrapper)`` would return False and we'd
  log the coroutine object instead of the awaited result.

  Generator and async-generator functions reuse the sync wrapper: calling them returns
  a generator/async-generator object immediately, which is logged as the return value
  (v1 limitation — per-yield iteration is NOT traced).
  """
  if inspect.iscoroutinefunction(func):
    return _make_async_wrapper(func, fixed)
  return _make_sync_wrapper(func, fixed)


def _should_wrap(name: str, include_dunder: bool, include_private: bool) -> bool:
  """Decide whether a class attribute named ``name`` should be wrapped.

  ``__init__`` is special-cased as always eligible: it's the constructor, not a
  recursion risk, and tracing object creation is one of the most useful things
  ``@trace`` does at class level. All other dunders gate on ``include_dunder``.
  """
  if name in _RECURSION_BLOCKLIST:
    return False
  if name == "__init__":
    return True
  is_dunder = name.startswith("__") and name.endswith("__") and len(name) > 4
  if is_dunder:
    return include_dunder
  if name.startswith("_"):
    return include_private
  return True


def _wrap_class_attr(attr: Any, fixed: _FixedOpts) -> Any:
  """Wrap a single class attribute, preserving descriptor type."""
  if isinstance(attr, staticmethod):
    inner = attr.__func__
    if not inspect.isfunction(inner):
      return attr
    return staticmethod(_decorate_callable(inner, fixed))
  if isinstance(attr, classmethod):
    inner = attr.__func__
    if not inspect.isfunction(inner):
      return attr
    return classmethod(_decorate_callable(inner, fixed))
  if isinstance(attr, property):
    new_fget = _decorate_callable(attr.fget, fixed) if attr.fget is not None else None
    new_fset = _decorate_callable(attr.fset, fixed) if attr.fset is not None else None
    new_fdel = _decorate_callable(attr.fdel, fixed) if attr.fdel is not None else None
    return property(new_fget, new_fset, new_fdel, attr.__doc__)
  if inspect.isfunction(attr):
    return _decorate_callable(attr, fixed)
  return attr


def _decorate_class(cls: type, fixed: _FixedOpts) -> type:
  """Walk ``vars(cls)`` only — inherited methods are intentionally NOT re-wrapped."""
  resolved = _resolve_opts(fixed)
  for name, attr in list(vars(cls).items()):
    if not _should_wrap(name, resolved.include_dunder, resolved.include_private):
      continue
    new_attr = _wrap_class_attr(attr, fixed)
    if new_attr is not attr:
      setattr(cls, name, new_attr)
  return cls


class _ConfiguredDecorator(Protocol):
  """Return type of ``log({...})`` — a decorator that accepts a callable or class."""

  @overload
  def __call__[**FnP, FnR](self, target: Callable[FnP, FnR], /) -> Callable[FnP, FnR]: ...

  @overload
  def __call__[ClsT: type](self, target: ClsT, /) -> ClsT: ...

  def __call__(self, target: Any, /) -> Any: ...


@overload
def trace(target: DecoratorOptions, /) -> _ConfiguredDecorator: ...


@overload
def trace[ClsT: type](target: ClsT, /) -> ClsT: ...


@overload
def trace[**FnP, FnR](target: Callable[FnP, FnR], /) -> Callable[FnP, FnR]: ...


def trace(target: Any, /) -> Any:
  """Decorator that traces calls, returns, and exceptions via stdlib logging.

  Four invocation forms::

      @trace                              # bare on a function/method
      @trace({"include_private": True})   # configured on a function/method
      @trace                              # bare on a class
      @trace({"include_dunder": True})    # configured on a class

  Logging:
  - Enter and exit records emit at ``DEBUG`` on ``getLogger(func.__module__)``.
  - Exception records emit at ``ERROR`` with full traceback; the original exception
    is re-raised unchanged.

  v1 limitations:
  - Generator and async-generator functions: the *call* is traced and the returned
    generator object is logged as the return value, but per-yield iteration is NOT
    traced.
  - Class decoration walks ``vars(cls)`` only; inherited methods on parent classes
    are NOT re-wrapped.
  """
  if isinstance(target, dict):
    fixed = _options_dict_to_fixed(cast(DecoratorOptions, target))

    def _decorator(inner: Any) -> Any:
      if isinstance(inner, type):
        return _decorate_class(inner, fixed)
      if callable(inner):
        return _decorate_callable(inner, fixed)
      raise TypeError(f"@trace expected a callable or class; got {type(inner).__name__}")

    return _decorator
  if isinstance(target, type):
    return _decorate_class(target, _FixedOpts())
  if callable(target):
    return _decorate_callable(target, _FixedOpts())
  raise TypeError(
    f"@trace expected a callable, class, or DecoratorOptions dict; got {type(target).__name__}"
  )
