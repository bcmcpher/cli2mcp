# Architecture

## Overview

`cli2mcp` is a **code-generation tool**. It reads Python CLI source files via AST (never importing them), extracts CLI command metadata, and renders a standalone `mcp_tools_generated.py` that wraps each command as an `@mcp.tool()` function delegating to the CLI via `subprocess.run()`.

## Data flow

```
pyproject.toml [tool.cli2mcp]
      │
      ▼
  config.py ──────────────► Config
                                │
source .py files ◄──────────────┤
      │                         │
      ▼                         │
  scrapers/                     │
  ClickScraper                  │
  ArgparseScraper               │
      │                         │
      ▼                         ▼
  list[ToolDef] ──► generators/mcp_server.py
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
  mcp_tools_generated.py        mcp_server.py
  (always overwritten)          (written once)
```

## Core modules

### `models.py`

Defines the two data classes that flow through the entire pipeline:

- **`ParamDef`** — one CLI parameter (name, type, default, flags, whether it's a boolean flag or list-valued).
- **`ToolDef`** — one CLI command (name, description, parameters, source location, CLI invocation tokens, framework).

These are plain `dataclass` instances with no methods — they are pure data.

### `config.py`

Loads and validates the `[tool.cli2mcp]` section from `pyproject.toml` using `tomllib` (stdlib on 3.11+). Produces a `Config` dataclass. No logic beyond parsing and validation happens here.

### `scrapers/`

Each scraper implements `BaseScraper`:

```python
class BaseScraper(ABC):
    def detect(self, tree: ast.AST) -> bool: ...
    def scrape_file(self, path: Path) -> list[ToolDef]: ...
```

`detect()` is a fast check (walk the import nodes) used to decide which scraper to use for each file. `scrape_file()` does the full parse.

**Key invariant:** scrapers never call `import`, `exec`, or `eval` on user code. All analysis is done with `ast.walk` and `ast.parse`.

`cli.py::_collect_tools` tries `ClickScraper` first; if `detect()` returns `False`, it falls back to `ArgparseScraper`.

### `parsers/`

- **`docstring.py`** — pure-Python NumPy-style docstring parser. No third-party dependencies. Splits the docstring into sections (`Parameters`, `Returns`, body), then extracts the summary, per-parameter descriptions, and return description.
- **`type_mapper.py`** — maps AST type nodes from Click/argparse declarations to Python type annotation strings.

### `generators/mcp_server.py`

`generate_module(tools, config)` renders the tools module as a plain string using string formatting (no templating library). Each `ToolDef` becomes an `@mcp.tool()` function nested inside `_register_tools(mcp)`.

`generate_server_scaffold(config, module_stem)` renders the one-time server scaffold.

### `cli.py`

Four Click subcommands — `init`, `generate`, `list`, `validate` — sharing `_collect_tools()` for config loading and scraping.

## Design decisions

### AST-only scraping

User CLI code may have side effects (network calls, database connections, `sys.exit`) at import time. Scraping via AST avoids all of these and means `cli2mcp` works even on partially broken environments.

### No runtime deps beyond `click`

`mcp` (FastMCP) is a dependency of the *generated* server, not of `cli2mcp` itself. This keeps the tool lightweight and avoids version conflicts between the generator and the generated server.

### Two-file output

Separating the always-regenerated tools module from the hand-editable server scaffold means users can:

- Re-run `cli2mcp generate` freely as their CLI evolves, without losing custom tools.
- Add custom `@mcp.tool()` functions in `mcp_server.py` that are never touched by the generator.

### subprocess delegation

Generated tools delegate to the CLI via `subprocess.run()` rather than direct function calls. This matches exactly how a human would invoke the CLI, handles entry-point wiring automatically, and isolates the MCP server process from CLI state (environment, working directory, globals). The commented-out direct-import alternative is available when a function returns a structured value.

## Extension points

To add support for a new CLI framework:

1. Create a new module under `scrapers/` that subclasses `BaseScraper`.
2. Implement `detect(tree)` to identify files using that framework.
3. Implement `scrape_file(path)` to return `list[ToolDef]`.
4. Register the new scraper in `cli.py::_collect_tools`.

The generator and models are framework-agnostic and require no changes.
