# cli2mcp

**Generate a working MCP server from your existing Python CLI — no manual wiring needed.**

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

---

`cli2mcp` reads your existing Click or argparse CLI source code **without importing it** (AST-only, no side effects). It extracts commands, options, types, and NumPy docstrings, then writes two files:

- **`mcp_tools_generated.py`** — always overwritten on each `generate` run; contains all auto-generated `@mcp.tool()` functions.
- **`mcp_server.py`** — written **once** (never overwritten); imports the tools module and gives you a stable place to add your own custom tools.

## How it works

```
your CLI source  →  cli2mcp  →  mcp_tools_generated.py  ←─ always regenerated
     (AST)                       mcp_server.py           ←─ yours to keep
                                       ↓
                           MCP host (Claude, Inspector…)
```

## Key features

- **AST-only scraping** — never imports user code; no side effects, no `sys.path` pollution.
- **Click and argparse** support out of the box.
- **NumPy docstring** extraction for rich tool descriptions.
- **Two-file output** — regenerate the tools module freely without losing your customisations.
- **`subprocess_timeout`** support to guard against hanging CLI calls.

## Quick example

```bash
# 1. Add config to pyproject.toml, then:
cli2mcp generate

# 2. Run the generated server
python mcp_server.py
```

See the [Quick Start](getting-started/quickstart.md) for a full walkthrough.
