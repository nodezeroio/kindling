"""Spec §10.8 — defensive repr never crashes; truncation honors max_repr_length."""

import logging

from kindling.logging import trace


class _Unreprable:
  def __repr__(self) -> str:
    raise RuntimeError("repr broken")


def test_unreprable_object_does_not_crash(caplog) -> None:
  @trace
  def f(x: object) -> int:
    return 1

  caplog.set_level(logging.DEBUG, logger=f.__module__)
  assert f(_Unreprable()) == 1
  enters = [r for r in caplog.records if getattr(r, "kindling_event", None) == "enter"]
  assert len(enters) == 1
  assert enters[0].kindling_args[0].startswith("<unreprable _Unreprable: RuntimeError>")


def test_long_repr_truncated_with_default(caplog) -> None:
  @trace
  def f(s: str) -> int:
    return len(s)

  caplog.set_level(logging.DEBUG, logger=f.__module__)
  big = "x" * 5000
  f(big)
  enters = [r for r in caplog.records if getattr(r, "kindling_event", None) == "enter"]
  rendered = enters[0].kindling_args[0]
  assert rendered.endswith("...<truncated>")
  # Default max_repr_length is 1000; the repr content is bounded by that, marker is extra.
  assert len(rendered) == 1000 + len("...<truncated>")


def test_positive_max_repr_length_truncates(caplog) -> None:
  @trace({"max_repr_length": 10})
  def f(s: str) -> None:
    pass

  caplog.set_level(logging.DEBUG, logger=f.__module__)
  f("a" * 100)
  enters = [r for r in caplog.records if getattr(r, "kindling_event", None) == "enter"]
  rendered = enters[0].kindling_args[0]
  assert rendered.endswith("...<truncated>")
  assert len(rendered) == 10 + len("...<truncated>")


def test_max_repr_length_none_disables_truncation(caplog) -> None:
  @trace({"max_repr_length": None})
  def f(s: str) -> None:
    pass

  caplog.set_level(logging.DEBUG, logger=f.__module__)
  big = "x" * 5000
  f(big)
  enters = [r for r in caplog.records if getattr(r, "kindling_event", None) == "enter"]
  rendered = enters[0].kindling_args[0]
  assert "...<truncated>" not in rendered
  # Repr of a 5000-char string is "'" + 5000 chars + "'" = 5002 chars
  assert len(rendered) == 5002


def test_short_repr_not_truncated(caplog) -> None:
  @trace
  def f(x: int) -> None:
    pass

  caplog.set_level(logging.DEBUG, logger=f.__module__)
  f(42)
  enters = [r for r in caplog.records if getattr(r, "kindling_event", None) == "enter"]
  assert enters[0].kindling_args[0] == "42"
