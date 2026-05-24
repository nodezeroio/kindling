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

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.1.0] - YYYY-MM-DD

### Added
- Initial release
