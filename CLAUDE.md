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
cli2mcp init                            # first-time setup
cli2mcp list --config pyproject.toml
cli2mcp generate --dry-run
cli2mcp check                           # CI drift detection
cli2mcp validate mcp/mcp_tools_generated.py
cli2mcp inspect mcp/mcp_server.py      # interactive MCP Inspector (requires npx)
```

## Architecture

`cli2mcp` is a **build dependency** for Python CLI developers. It reads CLI source files via AST (never importing them), extracts command metadata, and generates an MCP server that wraps each command as an `@mcp.tool()`. Developers add it to `[build-system].requires` so their CLI tools are automatically usable by MCP clients (Claude Code, etc.) without any changes to existing CLI code.

### Two-layer output

`generate` produces two files with different ownership:
- `mcp_tools_generated.py` — always overwritten; gitignored; imported by the scaffold
- `mcp_server.py` — written once, never overwritten; developer edits this to exclude tools or add MCP-only tools

### Data flow

```
pyproject.toml [tool.cli2mcp]
      ↓ config.py → Config
source .py files
      ↓ scrapers/ → list[ToolDef]
      ↓ generators/mcp_server.py → str (Python source)
      → mcp_tools_generated.py  (always overwritten)
      → mcp_server.py           (written once; user-owned scaffold)
```

### Core models (`models.py`)

- **`ParamDef`** — one CLI parameter (name, type, default, flags, whether it's a boolean flag).
- **`ToolDef`** — one CLI command (name, description, list of `ParamDef`, source module/function, CLI command/subcommand, framework label).

### Scrapers (`scrapers/`)

Each scraper implements `BaseScraper` with two methods:
- `detect(tree)` — returns `True` if the AST contains imports for that framework.
- `scrape_file(path)` — parses the file and returns `list[ToolDef]`.

`cli.py::_collect_tools` tries scrapers in order: `ClickScraper` → `TyperScraper` → `ArgparseScraper`. All scrapers are purely AST-based — no `exec`/`import` of user code.

### Parsers (`parsers/`)

- **`docstring.py`** — pure-Python NumPy-style docstring parser. Extracts summary, per-parameter descriptions, and returns description into `ParsedDocstring`. No third-party deps.
- **`type_mapper.py`** — maps AST type nodes from Click/argparse declarations to Python type annotation strings (e.g. `ast.Name("int")` → `"int"`).

### Generator (`generators/mcp_server.py`)

`generate_server(tools, config)` renders the output file as a plain string using string formatting (no templating library). Each `ToolDef` becomes an `@mcp.tool()` function with:
- A NumPy-style docstring (merged from CLI decorators and parsed docstrings).
- A `subprocess.run()` body that reconstructs the exact CLI invocation.
- A commented-out direct-import alternative for functions that return values.

### CLI (`cli.py`)

Six Click subcommands, all sharing `_collect_tools()` for config loading and scraping:
- `init` — scaffolds `[tool.cli2mcp]` in `pyproject.toml` (run once)
- `generate` — writes `mcp_tools_generated.py` + `mcp_server.py` (scaffold only)
- `check` — verifies generated file is current; exits nonzero if stale (use in CI / pre-commit)
- `list` — shows discovered tools without writing files
- `validate` — syntax/import-checks a generated file
- `inspect` — launches MCP Inspector via npx against a server file

### Tests

Tests use real fixture files in `tests/fixtures/` (`sample_click_cli.py`, `sample_argparse_cli.py`) as the source CLIs to scrape. Add new fixture files there when testing new CLI patterns.

## Key constraints

- **AST-only scraping** — scrapers must never import user code; all analysis is via `ast.parse`.
- **No runtime deps beyond `click`** — `mcp` (FastMCP) is a dependency of the *generated* server, not of `cli2mcp` itself.
- **Python 3.11+** — uses stdlib `tomllib`; older Python requires `tomli`.
- **Generated tools always return `str`** — the subprocess stdout. Structured return values require the user to uncomment the direct-import alternative.
