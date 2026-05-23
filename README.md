# kindling

Contains assorted shared utilities like logging for python applications


[![Tests](https://github.com/thomasbellio/kindling/actions/workflows/pr.yml/badge.svg)](https://github.com/thomasbellio/kindling/actions/workflows/pr.yml)


## Installation

```bash
pip install kindling
```

## Usage

```python
from kindling import example_function

result = example_function()
```

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
