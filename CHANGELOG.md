# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `kindling.logging` module providing the `@trace` decorator for sync, async,
  generator, and class-level call tracing, plus `configure()` for library-wide
  defaults via the `LoggingConfig` TypedDict.
- `DecoratorOptions` and `LoggingConfig` TypedDicts for type-safe configuration
  at both the per-decorator and global levels.
- Defensive `repr` of arguments and return values with configurable truncation
  (`max_repr_length`; `None` disables truncation entirely).
- Structured `kindling_*` payload on every log record so consumers can filter or
  redact individual values via stdlib `logging.Filter`.
- `NullHandler` attached to the `"kindling"` logger at import so the library
  never produces output unless the consumer opts in via
  `configure({"add_console_handler": True})`.
- `ColorFormatter` and `color: bool` flag on `LoggingConfig` for colorized
  console output (blue DEBUG, green INFO, yellow WARNING, red ERROR/CRITICAL);
  auto-disables on non-TTY streams unless `force_color=True`.
- `attach_to: list[str]` flag on `LoggingConfig` letting the managed console
  handler attach to additional logger names (e.g., the consumer's app
  namespace or root via `[""]`). Defaults to `["kindling"]`. `level` and
  `propagate` now apply to every logger in `attach_to`.

### Changed
- Consolidated `pyproject.toml` metadata under PEP 621 `[project]`
  (single source of truth for name, version, description, authors,
  license, readme, requires-python); removed the duplicated fields from
  `[tool.poetry]`. Version aligned to `0.1.0`.
- README install section now documents git-based install for pip and
  Poetry (with branch / tag / commit pinning) and notes that this package
  is not published to PyPI. Fixed stale GitHub Actions badge URL.

### Deprecated

### Removed

### Fixed

### Security

## [0.1.0] - YYYY-MM-DD

### Added
- Initial release
