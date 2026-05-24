"""Spec §10.7 — class decoration, descriptor handling, filters, recursion blocklist."""

import logging

from kindling.logging import trace


@trace
class _Plain:
  def __init__(self, name: str) -> None:
    self.name = name

  def greet(self) -> str:
    return f"hi {self.name}"

  @staticmethod
  def static_helper(x: int) -> int:
    return x + 1

  @classmethod
  def class_helper(cls, x: int) -> int:
    return x + 2

  @property
  def length(self) -> int:
    return len(self.name)

  @length.setter
  def length(self, value: int) -> None:
    self.name = "x" * value


@trace({"include_private": True})
class _WithPrivate:
  def _helper(self) -> int:
    return 1

  def public(self) -> int:
    return 2


@trace
class _DunderDefault:
  def __len__(self) -> int:
    return 0


@trace({"include_dunder": True})
class _DunderOpt:
  def __len__(self) -> int:
    return 0

  def __repr__(self) -> str:
    return "DunderOpt()"


class _Base:
  def base_method(self) -> int:
    return 99


@trace
class _Sub(_Base):
  def sub_method(self) -> int:
    return 1


def _events_for(records: list[logging.LogRecord], qualname_part: str) -> list[str]:
  return [
    getattr(r, "kindling_event", None)
    for r in records
    if qualname_part in getattr(r, "kindling_qualname", "")
  ]


def test_class_decoration_wraps_init(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_Plain.__module__)
  _Plain("alice")
  assert "enter" in _events_for(caplog.records, "_Plain.__init__")
  assert "exit" in _events_for(caplog.records, "_Plain.__init__")


def test_class_decoration_wraps_regular_method(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_Plain.__module__)
  p = _Plain("bob")
  caplog.clear()
  assert p.greet() == "hi bob"
  assert "enter" in _events_for(caplog.records, "_Plain.greet")


def test_staticmethod_traced(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_Plain.__module__)
  assert _Plain.static_helper(5) == 6
  assert "enter" in _events_for(caplog.records, "_Plain.static_helper")


def test_classmethod_traced(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_Plain.__module__)
  assert _Plain.class_helper(5) == 7
  assert "enter" in _events_for(caplog.records, "_Plain.class_helper")


def test_property_getter_traced(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_Plain.__module__)
  p = _Plain("xy")
  caplog.clear()
  assert p.length == 2
  assert "enter" in _events_for(caplog.records, "_Plain.length")


def test_property_setter_traced(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_Plain.__module__)
  p = _Plain("xy")
  caplog.clear()
  p.length = 4
  assert p.name == "xxxx"
  assert "enter" in _events_for(caplog.records, "_Plain.length")


def test_include_private_false_by_default(caplog) -> None:
  @trace
  class _NoPrivate:
    def _helper(self) -> int:
      return 1

    def public(self) -> int:
      return 2

  caplog.set_level(logging.DEBUG, logger=_NoPrivate.__module__)
  inst = _NoPrivate()
  inst._helper()
  inst.public()
  assert _events_for(caplog.records, "_NoPrivate._helper") == []
  assert "enter" in _events_for(caplog.records, "_NoPrivate.public")


def test_include_private_true_wraps_underscore(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_WithPrivate.__module__)
  inst = _WithPrivate()
  inst._helper()
  assert "enter" in _events_for(caplog.records, "_WithPrivate._helper")


def test_include_dunder_false_by_default(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_DunderDefault.__module__)
  inst = _DunderDefault()
  caplog.clear()
  len(inst)
  assert _events_for(caplog.records, "_DunderDefault.__len__") == []


def test_include_dunder_true_wraps_len(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_DunderOpt.__module__)
  inst = _DunderOpt()
  caplog.clear()
  len(inst)
  assert "enter" in _events_for(caplog.records, "_DunderOpt.__len__")


def test_repr_blocklist_prevents_recursion(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_DunderOpt.__module__)
  inst = _DunderOpt()
  caplog.clear()
  # If __repr__ were wrapped, repr() would recurse via the wrapper logging args
  # (which call repr on `self`). Just calling repr() and not stack-overflowing is
  # the assertion.
  assert repr(inst) == "DunderOpt()"
  assert _events_for(caplog.records, "_DunderOpt.__repr__") == []


def test_inherited_methods_not_rewrapped(caplog) -> None:
  caplog.set_level(logging.DEBUG, logger=_Sub.__module__)
  inst = _Sub()
  caplog.clear()
  assert inst.sub_method() == 1
  assert "enter" in _events_for(caplog.records, "_Sub.sub_method")
  caplog.clear()
  assert inst.base_method() == 99
  # base_method is defined on _Base, which was not decorated.
  assert _events_for(caplog.records, "base_method") == []
