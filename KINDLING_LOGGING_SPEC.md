# kindling — Logging Module Specification (v1)

> **Audience:** an autonomous coding agent (e.g. Claude Code) implementing the first
> feature of the `kindling` library.
> **Scope of this document:** the **logging** module only. This is v1. Anything marked
> *Out of scope* must NOT be built, but the design must not foreclose it.

---

## 1. Project context

`kindling` is a public, pip-installable Python library of cross-cutting utilities
(logging, profiling, APM, etc.). The repository already exists with packaging,
tooling, and CI configured. Key facts the agent must respect:

- **Python:** `>=3.14`. Use modern syntax (`X | None`, `type` statements where
  helpful, builtin generics).
- **Layout:** `src/` layout. Package root is `src/kindling/`. Tests in `tests/`.
- **Tooling (already configured, do not change config):**
  - `ruff` for lint + format. **Indent width is 2 spaces** (`indent-width = 2`),
    line length 100, double-quote style. Match the existing files exactly.
  - `mypy` in strict-ish mode (`disallow_untyped_defs`, `disallow_incomplete_defs`,
    `warn_unused_ignores`, etc.). **All new non-test code must be fully typed and
    pass mypy.** `tests.*` is exempt from `disallow_untyped_defs`.
  - `pytest` for tests. `--strict-markers --strict-config`.
  - `py.typed` marker is present — this is a typed package; keep it that way.
- **Build/check command:** `./scripts/build.sh` runs ruff check, ruff format --check,
  mypy on `src/kindling`, and pytest. **The implementation is complete only when this
  script passes.**

---

## 2. What we are building (v1 scope)

A logging module providing:

1. A **`log` decorator** that adds automatic enter/exit/argument/return tracing and
   exception logging to functions, methods, and (applied at class level) all methods
   of a class.
2. A **`configure` function** so consuming applications can customize logging behavior
   and set decorator defaults, via a single typed config object.
3. **Exception logging** inside the decorator: catch, log with traceback, re-raise.

### Explicitly OUT of scope for v1 (do NOT build, but do NOT foreclose)
- ❌ Exception **handler registry / pipelines** (0–N handlers keyed by exception type).
  Leave a clear, documented seam for it but build none of it.
- ❌ Global uncaught-exception hooks (`sys.excepthook`, `threading.excepthook`,
  asyncio exception handlers).
- ❌ **Generator iteration tracing** (see §6.3 — generators are wrapped but iteration
  is not traced).
- ❌ Async generators (`async def` + `yield`) and async context managers.
- ❌ Redaction logic built into kindling (we expose structured data so consumers can
  redact via stdlib filters — see §7.4).

---

## 3. Logging backend & core principles

- **Backend is the stdlib `logging` module.** Do not introduce structlog, loguru, or a
  custom logger. No new runtime dependencies.
- **Levels carry the behavior** (this satisfies the product rule "INFO logs nothing,
  DEBUG logs everything" without bespoke level logic):
  - Enter / exit / argument / return trace records are emitted at **DEBUG**.
  - Exception records are emitted at **ERROR** (with traceback).
  - Therefore at an INFO threshold the trace records are filtered out automatically and
    only exceptions surface; at DEBUG everything surfaces.
- **Logger attribution:**
  - The decorator logs against the **consumer's module logger**:
    `logging.getLogger(func.__module__)`. This attributes trace output to the caller's
    code, not to kindling.
  - **kindling's own internal/diagnostic logging** (anything kindling says about itself)
    uses `logging.getLogger("kindling")`.
- **Library citizenship (handlers):**
  - At import time, attach a `NullHandler` to the `"kindling"` logger so the package
    never emits "no handler" warnings and never produces output unless the consumer
    opts in.
  - kindling **must not** attach any output handler implicitly. Real output handlers are
    attached only when the consumer explicitly opts in via `configure` (see §5).

---

## 4. Public API surface

```
kindling/
  logging/
    __init__.py        # public surface for the logging module
    config.py          # DecoratorOptions + LoggingConfig TypedDicts + configure() + internal state
    decorators.py      # the `log` decorator and its machinery
```

- **Canonical decorator location:** `kindling.logging.decorators.log`.
- **Re-exports** from `kindling.logging` (so both import styles work):
  - `from kindling.logging import log`
  - `from kindling.logging import configure`
  - `from kindling.logging import LoggingConfig`
  - `from kindling.logging import DecoratorOptions`
- `kindling.logging.__init__` defines
  `__all__ = ["log", "configure", "LoggingConfig", "DecoratorOptions"]`.
- The top-level `kindling/__init__.py` currently only exposes `__version__`; leave that
  as is. Do **not** auto-import the logging module at top level (avoid import side
  effects beyond the `NullHandler`).

---

## 5. Configuration

Configuration is passed as a **`TypedDict`**, not keyword arguments — at BOTH the global
(`configure`) level and the per-decorator (`@trace`) level, for a single consistent
configuration vocabulary.

The config is split into two `TypedDict`s using inheritance. `DecoratorOptions` holds the
keys that are meaningful on an individual decorator; `LoggingConfig` **extends** it with
the global-only keys. This is deliberate: the decorator accepts `DecoratorOptions` so the
type system makes it **impossible** to pass a global-only key (e.g. `add_console_handler`)
to an individual `@trace`, while `configure` accepts the full `LoggingConfig` superset.

```python
from typing import TypedDict

class DecoratorOptions(TypedDict, total=False):
  """Options meaningful on an individual @trace target. Also valid as configure() defaults."""
  include_private: bool            # default False; trace single-underscore-prefixed methods
  include_dunder: bool             # default False; trace __dunder__ methods (excludes recursion-prone ones — see §6.4)
  log_arguments: bool              # default True; include call args in enter records
  log_return: bool                 # default True; include return value in exit records
  max_repr_length: int | None      # default 1000; truncation length for defensive repr (§7.3).
                                    #   None => NO truncation (log the full repr).

class LoggingConfig(DecoratorOptions, total=False):
  """Full library config. Superset of DecoratorOptions + global-only keys. Used by configure()."""
  level: int | str                 # threshold for the kindling-configured surface; e.g. "DEBUG" or logging.DEBUG
  add_console_handler: bool        # default False; if True, attach a StreamHandler (stderr)
  console_format: str              # logging.Formatter format string used iff add_console_handler is True
  propagate: bool                  # whether the "kindling" logger propagates to root
```

Because `LoggingConfig` derives from `DecoratorOptions`, a value typed as `LoggingConfig`
is also a valid `DecoratorOptions` — the decorator-relevant keys carry the same names,
types, and defaults in both places. Define `DecoratorOptions` first; `LoggingConfig`
extends it. Both are `total=False` so every key is optional.

### `configure`

```python
def configure(config: LoggingConfig) -> None: ...
```

Called like:

```python
configure({"add_console_handler": True, "level": "DEBUG", "include_private": True})
```

Behavior:
- **Partial / optional:** because `LoggingConfig` is `total=False`, any subset of keys
  may be provided. Missing keys fall back to documented defaults. `configure` merges the
  provided keys over current state; it does not reset unspecified keys to defaults on
  every call (last-writer-wins per key). Document this clearly.
- **Decorator defaults:** the keys inherited from `DecoratorOptions` (`include_private`,
  `include_dunder`, `log_arguments`, `log_return`, `max_repr_length`) establish the
  **defaults** used by `@trace` when a given option is not specified on the decorator
  itself. Per-decorator options always override these. See §6.5 for precedence.
- **`max_repr_length`:** default `1000`. A positive `int` truncates; **`None` disables
  truncation entirely** (the full repr is logged — see §7.3). Treat the key being present
  with value `None` as an explicit "no truncation" instruction, distinct from the key
  being absent (which means "use the current default").
- **`add_console_handler`:** default **`False`**. When `True`, attach a single
  `logging.StreamHandler` (stderr) to the `"kindling"` logger, with a `Formatter` built
  from `console_format` (provide a sensible default format including timestamp, logger
  name, level, and message). When `False`, attach nothing beyond the import-time
  `NullHandler`.
  - **Idempotency:** calling `configure` repeatedly must not stack duplicate console
    handlers. Guard so at most one kindling-owned console handler exists. (Track the
    handler kindling itself added; remove/replace rather than append on reconfigure.)
- **State storage:** keep current decorator defaults in a module-level, typed structure
  in `config.py` (e.g. a frozen dataclass instance that the decorator reads). Provide a
  private accessor the decorator uses; do not require consumers to pass config into the
  decorator.
- `configure` returns `None`.

---

## 6. The `log` decorator

Location: `kindling.logging.decorators.log`.

### 6.1 Invocation forms — must support all of these

Per-decorator options are passed as a **`DecoratorOptions` dict** (mirroring how
`configure` takes a config dict), NOT as keyword arguments:

```python
@trace                              # bare, on a function/method
def f(...): ...

@trace({"include_private": True})  # with options (DecoratorOptions dict), on a function/method
def g(...): ...

@trace                              # bare, on a class -> wraps all eligible methods
class A: ...

@trace({"include_dunder": True})   # with options, on a class
class B: ...

@trace({"max_repr_length": None})  # disable repr truncation for this target
def h(...): ...
```

The decorator signature is `log(target_or_options)` where the argument is **either** the
callable/class being decorated (bare form) **or** a `DecoratorOptions` mapping (configured
form). Implement the "optional-arguments decorator" pattern by distinguishing these:
- if called with a single argument that is a callable or class **and** no options → bare
  form, decorate it directly;
- if called with a `DecoratorOptions` mapping (a `dict`) → return a configured decorator
  that then decorates the next callable/class.

A `DecoratorOptions` value is also accepted if a consumer passes a `LoggingConfig` (since
`LoggingConfig` is a subtype); the decorator only reads the decorator-relevant keys and
**ignores** any global-only keys present, but the *typed* entry point is `DecoratorOptions`
so global-only keys won't type-check on a literal passed to `@trace`. Keep this logic in one
place.

### 6.2 Sync functions/methods

Wrap with `functools.wraps`. On call:
1. Emit a **DEBUG** "enter" record: qualified function name + (if `log_arguments`)
   defensively-repr'd positional and keyword arguments.
2. Call the target inside `try`.
3. On success: emit a **DEBUG** "exit" record with (if `log_return`) the
   defensively-repr'd return value; return the value.
4. On exception: emit an **ERROR** record **with traceback** (use
   `logger.exception(...)` or `logger.error(..., exc_info=True)`), then **re-raise with a
   bare `raise`** to preserve the original traceback. Do not wrap, chain, or swallow.

### 6.3 Async functions and generators — branch on target type

Detect the target kind and pick the matching wrapper:

- **Coroutine function** (`inspect.iscoroutinefunction(func)`): return an `async def`
  wrapper that `await`s the call. Enter logs before await; exit logs after await with the
  awaited result; exceptions logged + bare `raise` exactly as sync. **Do not** apply the
  sync wrapper to a coroutine function (it would log the coroutine object, not the result).
- **Generator function** (`inspect.isgeneratorfunction(func)`): **v1 limitation.** Wrap it
  with the sync wrapper, i.e. trace the *call* and treat the returned generator object as
  the "return value". Do **not** drive/trace iteration or per-`yield` values. Document this
  limitation in the decorator docstring and the README.
- **Async generator function** (`inspect.isasyncgenfunction(func)`): out of scope — treat
  conservatively like the generator case (trace the call only) and document.
- **Plain function/method:** sync wrapper.

Keep the per-kind logging logic DRY (e.g. small shared helpers for building the enter/exit
records) so sync and async wrappers don't duplicate formatting.

### 6.4 Class-level decoration

When `log` is applied to a class, iterate the class's **own** attributes
(`vars(cls)` / `cls.__dict__`) and rewrap eligible callables in place. Notes:

- Only attributes defined directly on the class are wrapped. **Do not walk the MRO**
  (inherited methods are left alone). Document this.
- Handle descriptor types correctly:
  - **plain function** (`inspect.isfunction`): wrap directly (this includes `__init__`).
  - **`staticmethod`**: unwrap via `.__func__`, wrap the inner function, re-wrap in
    `staticmethod`.
  - **`classmethod`**: unwrap via `.__func__`, wrap, re-wrap in `classmethod`.
  - **`property`**: wrap `fget`/`fset`/`fdel` individually (each that exists), rebuild the
    `property` (`prop.getter(...)`/`.setter(...)`/`.deleter(...)` or construct a new one).
- **Eligibility filter** (`_should_wrap(name)` style):
  - `__dunder__` names → wrapped only if `include_dunder` is True. **Even when
    `include_dunder` is True, always exclude a hardcoded recursion/noise blocklist**
    containing at minimum `__repr__`, `__str__`, `__format__`, `__hash__`, `__eq__`,
    `__ne__`, and `__getattribute__`. Rationale: the decorator calls `repr()` on args; a
    traced `__repr__` would recurse. `__init__` is NOT in this blocklist (it's a plain
    method and should be traceable).
  - single-underscore `_name` (and name-mangled `_Cls__name`) → wrapped only if
    `include_private` is True.
  - otherwise → wrapped.
- Class-level options propagate as the per-method defaults for that class's wrapped
  methods.
- Return the (mutated) class.

### 6.5 Option precedence (highest wins)

1. Keys present in the `DecoratorOptions` dict passed to `@trace({...})` on the specific
   function/class.
2. Decorator-default keys set via `configure({...})`.
3. Built-in library defaults (§5).

Resolve precedence **at call time** for global defaults where reasonable, so a
`configure` call after import still affects already-decorated targets for the
config-derived defaults. (Per-decorator explicit keys are fixed at decoration time.)
Merging is **per key**: a decorator that only sets `include_private` still inherits the
configured/default `max_repr_length`, `log_return`, etc. Document the resolution timing
chosen.

---

## 7. Record content & safety

### 7.1 Naming in records
Use `func.__qualname__` (and include `func.__module__`) so methods read as
`ClassName.method`. The logger name already carries the module, but include qualname in
the message for readability.

### 7.2 Human-readable message + structured `extra`
Every record carries BOTH:
- a concise human-readable `message` (what a person reads in the console), AND
- a structured `extra=` payload so consumer-side `logging.Filter`s can act on individual
  values **before** they're rendered. Suggested `extra` keys (namespaced to avoid
  collisions with stdlib `LogRecord` attributes — e.g. prefix `kindling_`):
  - `kindling_event`: one of `"enter" | "exit" | "exception"`
  - `kindling_qualname`, `kindling_module`
  - `kindling_args`, `kindling_kwargs` (enter; structured, pre-repr or repr'd consistently)
  - `kindling_return` (exit)
  - `kindling_exception_type` (exception)
- **Important:** never use `extra` keys that collide with reserved `LogRecord` attributes
  (`args`, `msg`, `name`, `levelname`, `module`, etc.) — that raises `KeyError`. The
  `kindling_` prefix avoids this.

### 7.3 Defensive `repr`
All argument/return values are rendered through a defensive repr helper that:
- calls `repr(value)` inside `try/except`; on any exception returns a placeholder like
  `<unreprable {type_name}: {error_class}>` (never let formatting crash the app),
- truncates the result to `max_repr_length`:
  - when `max_repr_length` is a positive `int`, truncate with a clear ellipsis/truncation
    marker,
  - when `max_repr_length` is **`None`, do NOT truncate** — return the full repr,
- is used uniformly for args, kwargs values, and return values.

### 7.4 Redaction (consumer responsibility, v1)
kindling performs **no redaction**. Because structured values are exposed via `extra`
(§7.2), consumers can attach a stdlib `logging.Filter` to redact specific fields precisely.
Document a short example of this in the README. (A built-in redaction hook is a future
extension; do not build it.)

---

## 8. Exception handling (v1)

- Decorator catches exceptions escaping the decorated callable, logs at **ERROR** with
  traceback, and re-raises via **bare `raise`** (preserves original `__traceback__`; the
  only added frame is the wrapper's, which is acceptable and documented).
- **No** handler registry, **no** swallowing, **no** global hooks in v1.
- **Seam for the future (build nothing, just don't block it):** isolate the
  "an exception escaped a decorated callable" moment into a single internal function/path
  so a future handler-dispatch step could be inserted there. Add a brief code comment
  marking it as the planned extension point. Do not add public API for it.

---

## 9. Implementation notes & gotchas (call these out in code/tests)

- Nested traced calls produce nested enter/exit logs — this is intended at DEBUG.
- `functools.wraps` everywhere so `__name__`, `__doc__`, `__wrapped__`, signature
  introspection survive.
- The optional-args decorator pattern must not misfire: distinguish "bare on a
  callable/class" (single argument that is a function or class) from "configured with a
  `DecoratorOptions` dict" (single argument that is a mapping). A `dict` argument is never
  a decoration target, and a callable/class argument is never an options payload, so the
  two forms are unambiguous.
- Class decoration mutates the class in place and returns it; ensure descriptors are
  rebuilt, not left as wrapped-but-unbound functions.
- Reconfiguring must not duplicate the console handler (§5 idempotency).
- Keep all public functions fully type-annotated; the `log` decorator's typing should
  preserve the wrapped callable's signature as much as practical (use `ParamSpec` /
  `TypeVar` for the function overloads; the class-decoration overload returns the class
  type). Provide `@overload`s so the bare `@trace`, the configured `@trace({...})`, and class
  usage all type-check. The configured form's parameter type is `DecoratorOptions`.

---

## 10. Testing requirements

Tests live in `tests/` (pytest, 2-space indent). Use `caplog` and/or a custom handler to
assert on records. Cover at minimum:

1. **Levels:** at INFO threshold, enter/exit records are absent; at DEBUG they are present;
   exception records appear at ERROR regardless.
2. **Sync function:** enter logged with args, exit logged with return value.
3. **Async function:** exit record contains the **awaited result**, not a coroutine object;
   exceptions logged + re-raised. (Use `pytest.mark.asyncio` only if you add the dep — do
   NOT add a dependency; prefer driving the coroutine with `asyncio.run` in the test to
   avoid new deps.)
4. **Generator (limitation):** verify the call is traced and the return value is the
   generator object; verify per-yield values are NOT logged (documents the v1 limitation).
5. **Exception:** record emitted at ERROR with `exc_info`/traceback; original exception
   type and traceback preserved after re-raise (assert the original throw site is still in
   the traceback).
6. **Decorator forms:** bare `@trace` and configured `@trace({...})` both work on functions;
   passing a `DecoratorOptions` dict applies the keys correctly.
7. **Class decoration:** all eligible methods wrapped including `__init__`;
   `staticmethod`/`classmethod`/`property` still behave correctly and are traced;
   `include_private`/`include_dunder` filters work; recursion blocklist (e.g. `__repr__`)
   is never wrapped even with `include_dunder=True` (no infinite recursion).
8. **Defensive repr:** an object whose `__repr__` raises does not crash logging; long
   reprs are truncated to a positive `max_repr_length`; **`max_repr_length=None` logs the
   full untruncated repr**.
9. **Structured `extra`:** records carry the documented `kindling_*` keys; a consumer
   `logging.Filter` can read/redact a value.
10. **`configure`:** partial config merges (per-key, last-writer-wins); a global-only key
    (e.g. `add_console_handler`) is accepted by `configure` but is not part of
    `DecoratorOptions`; `add_console_handler=True` attaches exactly one handler and is
    idempotent across repeated calls; a decorator default set via `configure` is overridden
    by a key present in a per-decorator `DecoratorOptions` dict, while unset keys still
    inherit the configured default.
11. **Logger attribution:** decorated functions log under `getLogger(func.__module__)`.

The existing `tests/test_placeholder.py` may stay or be replaced; keep at least the version
import test passing.

---

## 11. Definition of done

- [ ] `src/kindling/logging/{__init__,config,decorators}.py` implemented per above.
- [ ] Public API re-exported: `log`, `configure`, `LoggingConfig`, `DecoratorOptions` from
      `kindling.logging`.
- [ ] `NullHandler` attached to `"kindling"` at import; no implicit output handler.
- [ ] Sync + async supported; generator limitation implemented and documented.
- [ ] Class decoration with descriptor handling + filters + recursion blocklist.
- [ ] Defensive repr + structured `extra` + bare re-raise.
- [ ] Fully typed; `mypy src/kindling` clean.
- [ ] Tests covering §10; `pytest` green.
- [ ] `ruff check .` and `ruff format --check .` clean (2-space indent, line length 100).
- [ ] **`./scripts/build.sh` passes end to end.**
- [ ] README "Usage" section updated with a real `@trace` + `configure` example and the
      generator limitation + redaction-via-filter note. Update `CHANGELOG.md` Unreleased.
```
