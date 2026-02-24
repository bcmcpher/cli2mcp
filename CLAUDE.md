# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file
pytest tests/test_click_scraper.py

# Run a single test
pytest tests/test_click_scraper.py::test_greet_tool_params

# Run with coverage
pytest --cov=src/cli2mcp

# Exercise the CLI directly
cli2mcp list --config pyproject.toml
cli2mcp generate --dry-run
cli2mcp validate mcp_server.py
```

## Architecture

`cli2mcp` is a code-generation tool. It reads Python CLI source files via AST (never importing them), extracts CLI command metadata, and renders a standalone `mcp_server.py` that wraps each command as an `@mcp.tool()` function delegating to the CLI via `subprocess.run()`.

### Data flow

```
pyproject.toml [tool.cli2mcp]
      ↓ config.py → Config
source .py files
      ↓ scrapers/ → list[ToolDef]
      ↓ generators/mcp_server.py → str (Python source)
      → mcp_server.py written to disk
```

### Core models (`models.py`)

- **`ParamDef`** — one CLI parameter (name, type, default, flags, whether it's a boolean flag).
- **`ToolDef`** — one CLI command (name, description, list of `ParamDef`, source module/function, CLI command/subcommand, framework label).

### Scrapers (`scrapers/`)

Each scraper implements `BaseScraper` with two methods:
- `detect(tree)` — returns `True` if the AST contains imports for that framework.
- `scrape_file(path)` — parses the file and returns `list[ToolDef]`.

`cli.py::_collect_tools` tries `ClickScraper` first; if `detect` is False, falls back to `ArgparseScraper`. Both scrapers are purely AST-based — no `exec`/`import` of user code.

### Parsers (`parsers/`)

- **`docstring.py`** — pure-Python NumPy-style docstring parser. Extracts summary, per-parameter descriptions, and returns description into `ParsedDocstring`. No third-party deps.
- **`type_mapper.py`** — maps AST type nodes from Click/argparse declarations to Python type annotation strings (e.g. `ast.Name("int")` → `"int"`).

### Generator (`generators/mcp_server.py`)

`generate_server(tools, config)` renders the output file as a plain string using string formatting (no templating library). Each `ToolDef` becomes an `@mcp.tool()` function with:
- A NumPy-style docstring (merged from CLI decorators and parsed docstrings).
- A `subprocess.run()` body that reconstructs the exact CLI invocation.
- A commented-out direct-import alternative for functions that return values.

### CLI (`cli.py`)

Three Click subcommands — `generate`, `list`, `validate` — all sharing `_collect_tools()` for config loading and scraping.

### Tests

Tests use real fixture files in `tests/fixtures/` (`sample_click_cli.py`, `sample_argparse_cli.py`) as the source CLIs to scrape. Add new fixture files there when testing new CLI patterns.

## Key constraints

- **AST-only scraping** — scrapers must never import user code; all analysis is via `ast.parse`.
- **No runtime deps beyond `click`** — `mcp` (FastMCP) is a dependency of the *generated* server, not of `cli2mcp` itself.
- **Python 3.11+** — uses stdlib `tomllib`; older Python requires `tomli`.
- **Generated tools always return `str`** — the subprocess stdout. Structured return values require the user to uncomment the direct-import alternative.
