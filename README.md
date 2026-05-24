# kindling

Contains assorted shared utilities like logging for python applications


[![Tests](https://github.com/nodezeroio/kindling/actions/workflows/pr.yml/badge.svg)](https://github.com/nodezeroio/kindling/actions/workflows/pr.yml)


## Installation

`kindling` is installed directly from this GitHub repo — it is not
published to PyPI.

### pip

```bash
# Latest from the default branch
pip install git+https://github.com/nodezeroio/kindling.git

# Pin to a tag, branch, or commit SHA
pip install git+https://github.com/nodezeroio/kindling.git@v0.1.0
pip install git+https://github.com/nodezeroio/kindling.git@master
pip install git+https://github.com/nodezeroio/kindling.git@<commit-sha>
```

To pin in a `requirements.txt`:

```
kindling @ git+https://github.com/nodezeroio/kindling.git@v0.1.0
```

### Poetry

```bash
poetry add git+https://github.com/nodezeroio/kindling.git
# Pin to a ref:
poetry add git+https://github.com/nodezeroio/kindling.git#v0.1.0
```

Or declare the dependency directly in your `pyproject.toml`:

```toml
[tool.poetry.dependencies]
kindling = { git = "https://github.com/nodezeroio/kindling.git", branch = "master" }
# Or pin: tag = "v0.1.0"  /  rev = "<commit-sha>"
```

## Usage

`kindling.logging` provides a `@trace` decorator that traces calls, returns, and
exceptions via the stdlib `logging` module, plus a `configure()` function for
library-wide defaults.

```python
import logging
from kindling.logging import trace, configure

# 1. Opt in to output. Without this, kindling emits nothing.
configure({"add_console_handler": True, "level": "DEBUG"})

# 2. Decorate a function — bare form.
@trace
def add(a: int, b: int) -> int:
  return a + b

# 3. Decorate with per-call options — a DecoratorOptions dict.
@trace({"include_private": True, "max_repr_length": None})
def process(payload: dict) -> str:
  return payload["id"]

# 4. Decorate an entire class — all eligible methods are wrapped, including
#    __init__. staticmethod, classmethod, and property are handled correctly.
#    Dunder methods are skipped by default; pass {"include_dunder": True} to
#    include them (a small recursion-safety blocklist always applies).
@trace
class Service:
  def __init__(self, name: str) -> None:
    self.name = name

  def greet(self) -> str:
    return f"hello, {self.name}"

# 5. Redact sensitive fields via a stdlib logging.Filter — kindling exposes
#    structured values on every record as `kindling_*` attributes.
class RedactPasswords(logging.Filter):
  def filter(self, record: logging.LogRecord) -> bool:
    kwargs = getattr(record, "kindling_kwargs", None)
    if isinstance(kwargs, dict) and "password" in kwargs:
      kwargs["password"] = "'***'"
    return True

logging.getLogger(__name__).addFilter(RedactPasswords())
```

### Colorized console output

Set `color: True` when enabling the console handler to colorize the
`%(levelname)s` field by severity (blue DEBUG, green INFO, yellow WARNING,
red ERROR/CRITICAL). Colors auto-disable when stderr is not a TTY, so piped
output and CI logs stay free of escape sequences.

```python
from kindling.logging import configure
configure({"add_console_handler": True, "color": True, "level": "DEBUG"})
```

`ColorFormatter` is also exported for consumers who manage their own
handlers; pass `force_color=True` if you need codes on a non-TTY stream.

### Using kindling's handler for your own loggers

`kindling` uses stdlib `logging` — create loggers with
`logging.getLogger(__name__)` as you would with any library. Both
`@trace`-decorated functions and inline `log.info(...)` calls go to those
consumer-owned loggers, NOT to the `"kindling"` logger.

By default the handler installed by
`configure({"add_console_handler": True})` is attached only to
`getLogger("kindling")`, so it never sees records emitted under your
application's namespace. To route your loggers through kindling's colored
output, pass `attach_to` with the logger name(s) you want covered:

```python
import logging
from kindling.logging import configure, trace

# Attach the managed console handler to your app namespace (and/or "" for root).
configure({
  "add_console_handler": True,
  "color": True,
  "level": "DEBUG",
  "attach_to": ["myapp"],
})

log = logging.getLogger(__name__)  # e.g. "myapp.services"

@trace
def fetch(id: int) -> dict:
  log.info("starting fetch for %s", id)   # surfaces through kindling's handler
  return {"id": id}

fetch(42)
```

This produces both the `DEBUG` enter/exit records from `@trace` AND the
`INFO` line from the inline `log.info(...)` call, all formatted by the
kindling-managed handler and colored by level.

Notes:
- `attach_to` defaults to `["kindling"]`. Override it with one or more
  logger names; pass `[""]` to attach to the root logger if you want
  global catchment.
- When `level` and `propagate` are supplied to `configure(...)`, they
  apply to every logger in `attach_to`.
- Reconfiguring is idempotent: a fresh `configure(...)` detaches the
  managed handler from its previous targets before re-attaching, so
  duplicates never stack.
- Listing both an ancestor and one of its descendants (e.g.
  `["myapp", "myapp.db"]`) will cause records under the descendant to be
  emitted twice (once directly, once via propagation). This is a config
  choice on the consumer side, not auto-detected by kindling.

### Levels and behavior

- Enter, exit, argument, and return tracing emit at `DEBUG`.
- Exceptions caught by the decorator emit at `ERROR` with full traceback, then
  the original exception is re-raised unchanged.
- At `INFO`, only exceptions surface; at `DEBUG`, everything surfaces.

### v1 limitations

- **Generators:** the *call* is traced (and the returned generator object is
  logged as the return value), but per-`yield` iteration is NOT traced.
- **Async generators:** same as generators — call-only tracing.
- **Inherited methods** of a `@trace`-decorated class are NOT re-wrapped; only
  attributes defined directly on the class are.
- **Redaction** is not built in — use a stdlib `logging.Filter` as shown above.

## Development

This project uses [uv](https://github.com/astral-sh/uv) for environment management and [Poetry](https://python-poetry.org/) for dependency management.

### Setup

1. Install uv (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create a virtual environment:
```bash
uv venv
```

3. Activate the virtual environment:
```bash
# On Unix/macOS
source .venv/bin/activate

# On Windows
.venv\Scripts\activate
```

4. Install dependencies:
```bash
uv pip install poetry
poetry install
```

### Development Tools

This project uses the following development tools:

- **ruff**: Linting and formatting
- **mypy**: Type checking
- **pytest**: Testing
- **lefthook**: Git hooks for pre-commit checks

Install lefthook:
```bash
# On macOS
brew install lefthook

# On Linux
curl -1sLf 'https://dl.cloudsmith.io/public/evilmartians/lefthook/setup.rpm.sh' | sudo -E bash
sudo yum install lefthook

# Or using go
go install github.com/evilmartians/lefthook@latest
```

Initialize git hooks:
```bash
lefthook install
```

### Running Tests

```bash
pytest
```

### Running Linting and Type Checks

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type check
mypy src/kindling
```

Or run all checks at once:
```bash
./scripts/build.sh
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.
