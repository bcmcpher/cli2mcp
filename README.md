# cli2mcp

**Generate a working MCP server from your existing Python CLI — no manual wiring needed.**

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue) ![License: MIT](https://img.shields.io/badge/license-MIT-green)

---

## What it does

`cli2mcp` reads your existing Click or argparse CLI source code **without importing it** (AST-only, no side effects). It extracts commands, options, types, and NumPy docstrings, then writes two files:

- **`mcp_tools_generated.py`** — always overwritten on each `generate` run; contains all auto-generated `@mcp.tool()` functions wrapped in a `_register_tools(mcp)` function.
- **`mcp_server.py`** — written **once** (never overwritten); imports and calls `_register_tools`, and gives you a stable place to add your own custom tools.

```
your CLI source  →  cli2mcp  →  mcp_tools_generated.py  ←─ always regenerated
     (AST)           (scrape + render)   mcp_server.py       ←─ yours to keep
                                              ↓
                                    MCP host (Claude, Inspector, etc.)
```

---

## Installation

```bash
pip install cli2mcp
# or in-project dev install:
pip install -e "path/to/cli2mcp[dev]"
```

> **Note:** `mcp` (FastMCP) is a dependency of the **generated** server, not of `cli2mcp` itself. Install it in the environment where the generated server will run:
>
> ```bash
> pip install mcp
> ```

---

## Quick start

### Step 1 — Add config to your project's `pyproject.toml`

```toml
[tool.cli2mcp]
server_name = "My Project MCP Server"
entry_point = "myapp"                      # the CLI command name on PATH
source_dirs = ["src/mypackage"]            # directories to scan
output_file = "mcp_tools_generated.py"    # auto-generated tools module (always overwritten)
server_file = "mcp_server.py"             # server entry point (written once, then yours)
```

### Step 2 — Generate

```bash
cli2mcp generate
```

On the first run this writes **both** files. On subsequent runs only `mcp_tools_generated.py` is updated; `mcp_server.py` is left untouched.

### Step 3 — Run it

```bash
python mcp_server.py
# or via MCP inspector:
mcp dev mcp_server.py
```

---

## Writing CLI code that `cli2mcp` understands

### Click example

```python
import click

@click.group()
def cli():
    """Main CLI group."""

@cli.command()
@click.argument("name")
@click.option("--count", "-c", type=int, default=1, help="Number of greetings.")
@click.option("--loud", is_flag=True, default=False, help="Print in uppercase.")
def greet(name: str, count: int, loud: bool) -> None:
    """Greet a user by name.

    Parameters
    ----------
    name : str
        The name of the person to greet.
    count : int
        How many times to repeat the greeting.
    loud : bool
        Whether to shout the greeting.

    Returns
    -------
    str
        The greeting message(s).
    """
    for _ in range(count):
        msg = f"Hello, {name}!"
        if loud:
            msg = msg.upper()
        click.echo(msg)
```

If you omit the `Parameters` section, `cli2mcp` falls back to the `help=` string from each decorator.

### argparse example

```python
import argparse

def run_convert(args=None):
    """Convert files between formats.

    Parameters
    ----------
    args : list, optional
        Command line arguments (for testing).

    Returns
    -------
    str
        Conversion result summary.
    """
    parser = argparse.ArgumentParser(prog="convert", description="Convert files between formats.")
    parser.add_argument("input", type=str, help="Input file path.")
    parser.add_argument("output", type=str, help="Output file path.")
    parser.add_argument("--format", "-f", type=str, default="json", help="Output format.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output.")
    parsed = parser.parse_args(args)
    return f"Converting {parsed.input} to {parsed.output}"
```

The `prog=` argument on `ArgumentParser` is used as the CLI subcommand name.

### NumPy docstring format reference

```python
"""One-line summary.

Parameters
----------
name : str
    Description of name.
count : int
    Description of count.

Returns
-------
str
    Description of what is returned.
"""
```

---

## Configuration reference

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `server_name` | yes | — | Name passed to `FastMCP(...)` |
| `entry_point` | yes | — | CLI command name on PATH |
| `source_dirs` | yes | — | List of dirs to scan |
| `output_file` | no | `mcp_tools_generated.py` | Auto-generated tools module (always overwritten) |
| `server_file` | no | `mcp_server.py` | Server entry point (written once, then yours to keep) |
| `include_patterns` | no | `["*.py"]` | Glob patterns to include |
| `exclude_patterns` | no | `["test_*", "_*"]` | Glob patterns to exclude |
| `subprocess_timeout` | no | `None` (no limit) | Seconds before a subprocess call times out |

---

## CLI reference

```
cli2mcp init     [--server-name NAME] [--entry-point CMD] [--source-dir DIR] [--config FILE]
cli2mcp generate [--config FILE] [--output FILE] [--dry-run] [--force]
cli2mcp list     [--config FILE] [--format {text,json}]
cli2mcp validate FILE
```

- **`init`** — Scaffold a `[tool.cli2mcp]` section in `pyproject.toml` interactively. Prompts for server name, entry point, and source directory. Appends to an existing `pyproject.toml` or creates one from scratch.
- **`generate`** — Scrape source dirs, always write the tools module, and write the server scaffold only if it doesn't already exist. Use `--dry-run` to print both files to stdout instead of writing. Use `--output` to override the tools module path from config. Use `--force` to overwrite the server scaffold even if it already exists.
- **`list`** — Verify what tools were discovered without generating any files. Run this first to confirm `cli2mcp` found what you expect. Use `--format json` for machine-readable output.
- **`validate FILE`** — Parse-check a generated file for syntax errors (runs `ast.parse` without importing).

---

## What the generated files look like

For the `greet` command above, `cli2mcp generate` produces two files.

### `mcp_tools_generated.py` (always overwritten — do not edit)

```python
"""MCP tools generated by cli2mcp v0.1.0
Source: src/mypackage
Generated: 2026-01-01 00:00:00 UTC

DO NOT EDIT — this file is auto-generated.
Regenerate with: cli2mcp generate
Add custom tools to mcp_server.py instead.
"""
from __future__ import annotations

import subprocess


def _register_tools(mcp) -> None:
    """Register all auto-generated CLI tools with the given FastMCP instance."""

    @mcp.tool()
    def greet(name: str, count: int = 1, loud: bool = False) -> str:
        """Greet a user by name.

        Parameters
        ----------
        name : str
            The name of the person to greet.
        count : int
            How many times to repeat the greeting.
        loud : bool
            Whether to shout the greeting.

        Returns
        -------
        str
            The greeting message(s).
        """
        result = subprocess.run(
            [
                "myapp",       # entry_point from config
                "greet",       # CLI subcommand name
                str(name),     # positional argument
                "--count", str(count),
                *(['--loud'] if loud else []),  # is_flag: only pass when True
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"CLI command failed:\n{result.stderr}")
        return result.stdout

        # Direct import alternative (uncomment if greet returns a value):
        # from mypackage.commands import greet
        # return greet(name=name, count=count, loud=loud)
```

### `mcp_server.py` (written once — edit freely)

```python
"""MCP server for My Project MCP Server.

This file was generated once by cli2mcp and will NOT be overwritten on subsequent runs.
Add your own @mcp.tool() functions below the _register_tools(mcp) call.

To regenerate CLI tools, run: cli2mcp generate
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_tools_generated import _register_tools

mcp = FastMCP("My Project MCP Server")

# Register auto-generated CLI tools
_register_tools(mcp)

# Add your custom tools below:
# @mcp.tool()
# def my_custom_tool(arg: str) -> str:
#     """My custom tool description."""
#     ...

if __name__ == "__main__":
    mcp.run()
```

The subprocess call builds the exact command your CLI expects. The commented direct-import alternative lets you bypass subprocess if your function returns a value directly.

---

## Running & connecting the server

**Run directly:**
```bash
python mcp_server.py
```

**MCP inspector:**
```bash
mcp dev mcp_server.py
```

**Claude Desktop** — add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "my-project": {
      "command": "python",
      "args": ["/path/to/your/project/mcp_server.py"]
    }
  }
}
```

---

## How AI agents can use this tool

1. Add `[tool.cli2mcp]` to the project's `pyproject.toml` with the correct `entry_point` and `source_dirs`.
2. Run `cli2mcp list` to verify which tools were discovered and confirm names and parameter counts look right.
3. Run `cli2mcp generate` to produce `mcp_tools_generated.py` and (on first run) `mcp_server.py`.
4. Run `cli2mcp validate mcp_tools_generated.py` and `cli2mcp validate mcp_server.py` as a sanity check — confirms both files are valid Python.
5. Register the server with the MCP host using the `python mcp_server.py` invocation.

The `--dry-run` flag on `generate` prints both file contents to stdout (separated by a header comment), letting an agent preview the output before writing. `list` makes it easy to detect misconfigured `source_dirs` before wasting a generation step.

---

## Limitations

- **Python 3.11+ required** (`tomllib` is stdlib from 3.11; older versions need `tomli` installed separately).
- **Click and argparse only** — Typer, Fire, and other frameworks are not supported.
- **Tools always return `str`** (stdout of the subprocess). If your function returns a structured value, uncomment the direct-import alternative in the generated file and adapt it.
- **CLI must be on PATH** — the generated server delegates via `subprocess.run()`, so your CLI entry point must be installed and accessible in the same environment where `mcp_server.py` runs.
