# cli2mcp

**Generate a working MCP server from your existing Python CLI — no manual wiring needed.**

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue) ![License: MIT](https://img.shields.io/badge/license-MIT-green)

---

## What it does

`cli2mcp` reads your existing Click, Typer, or argparse CLI source code **without importing it** (AST-only, no side effects). It extracts commands, options, types, and docstrings, then writes two files:

- **`mcp/mcp_tools_generated.py`** — always overwritten on each `generate` run; contains all auto-generated `@mcp.tool()` functions wrapped in a `_register_tools(mcp)` function.
- **`mcp/mcp_server.py`** — written **once** (never overwritten); imports and calls `_register_tools`, and gives you a stable place to add your own custom tools.

```
your CLI source  →  cli2mcp  →  mcp/mcp_tools_generated.py  ←─ always regenerated
     (AST)           (scrape + render)   mcp/mcp_server.py       ←─ yours to keep
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

### Step 1 — Scaffold config

```bash
cli2mcp init
```

Prompts for server name, entry point, and source directory, then appends a `[tool.cli2mcp]` section to `pyproject.toml`. Or write it manually:

```toml
[tool.cli2mcp]
server_name = "My Project MCP Server"
entry_point = "myapp"                          # the CLI command name on PATH
source_dirs = ["src/mypackage"]                # directories to scan
output_file = "mcp/mcp_tools_generated.py"    # auto-generated module (always overwritten)
server_file = "mcp/mcp_server.py"             # server entry point (written once, then yours)
```

### Step 2 — Preview what will be discovered

```bash
cli2mcp list
```

Confirms which tools were found and their parameter counts before writing anything.

### Step 3 — Generate

```bash
cli2mcp generate
```

First run writes **both** files. Subsequent runs only update `mcp_tools_generated.py`; `mcp_server.py` is left untouched.

Gitignore the generated file — it is rebuilt on every `generate` run:

```bash
echo 'mcp/mcp_tools_generated.py' >> .gitignore
```

### Step 4 — Run it

```bash
python mcp/mcp_server.py
# or via the built-in MCP Inspector:
cli2mcp inspect mcp/mcp_server.py
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

If you omit the `Parameters` section, `cli2mcp` falls back to the `help=` string from each decorator. Google-style and Sphinx-style docstrings are also supported.

### Typer example

```python
import typer

app = typer.Typer()

@app.command()
def process(path: str, verbose: bool = False) -> None:
    """Process a file."""
    ...
```

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
| `output_file` | no | `mcp/mcp_tools_generated.py` | Auto-generated tools module (always overwritten) |
| `server_file` | no | `mcp/mcp_server.py` | Server entry point (written once, then yours to keep) |
| `include_patterns` | no | `["*.py"]` | Glob patterns for files to include |
| `exclude_patterns` | no | `["test_*", "_*"]` | Glob patterns for files to exclude |
| `include_tools` | no | `[]` | Allowlist of tool names to expose (empty = all) |
| `exclude_tools` | no | `[]` | Denylist of tool names to suppress |
| `subprocess_timeout` | no | `None` | Seconds before a subprocess call times out |
| `capture_stderr` | no | `false` | Include stderr in successful tool output |
| `prefer_direct_import` | no | `false` | Generate direct function-import calls instead of subprocess |
| `prefix_tool_names` | no | `true` | Prefix tool names with the entry point slug (e.g. `myapp_greet`) |

Per-tool annotation overrides:

```toml
[tool.cli2mcp.annotations.delete_user]
destructiveHint = true
idempotentHint = false
```

---

## CLI reference

```
cli2mcp init     [--server-name NAME] [--entry-point CMD] [--source-dir DIR] [--config FILE]
cli2mcp generate [--config FILE] [--output FILE] [--dry-run] [--force]
cli2mcp check    [--config FILE]
cli2mcp list     [--config FILE] [--format {text,json}]
cli2mcp validate FILE [--import-check]
cli2mcp inspect  FILE [--transport {stdio,sse}]
```

- **`init`** — Scaffold a `[tool.cli2mcp]` section in `pyproject.toml` interactively. Appends to an existing `pyproject.toml` or creates one from scratch. Prints next-step instructions including the gitignore and pre-commit hook setup.
- **`generate`** — Scrape source dirs, always write the tools module, write the server scaffold only if it doesn't already exist. `--dry-run` prints both files to stdout. `--force` overwrites the server scaffold even if it exists.
- **`check`** — Verify that `mcp_tools_generated.py` is current with the CLI source. Exits nonzero if the file is missing or stale. Use in CI or as a pre-commit hook to catch drift.
- **`list`** — Show discovered tools without writing any files. Use `--format json` for machine-readable output.
- **`validate FILE`** — Syntax-check a generated file via `ast.parse`. Add `--import-check` to also attempt a live import (requires `mcp` and `pydantic` installed).
- **`inspect FILE`** — Launch the MCP Inspector against a server file via `npx` (requires Node.js on PATH).

---

## What the generated files look like

For the `greet` command above, `cli2mcp generate` produces two files.

### `mcp/mcp_tools_generated.py` (always overwritten — do not edit)

```python
"""MCP tools generated by cli2mcp v0.1.0
Source: src/mypackage
Generated: 2026-01-01 00:00:00 UTC

DO NOT EDIT — this file is auto-generated.
Regenerate with: cli2mcp generate
Add custom tools to mcp_server.py instead.
"""
from __future__ import annotations

import asyncio
from typing import Any, Literal

from pydantic import BaseModel, Field


class GreetInput(BaseModel):
    name: str = Field(..., description='The name of the person to greet.')
    count: int = Field(1, description='Number of greetings.')
    loud: bool = Field(False, description='Print in uppercase.')


def _register_tools(mcp) -> None:
    """Register all auto-generated CLI tools with the given FastMCP instance."""

    @mcp.tool(
        name="myapp_greet",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    )
    async def myapp_greet(params: GreetInput) -> str:
        """Greet a user by name.

        Parameters
        ----------
        name : str
            The name of the person to greet.
        count : int
            Number of greetings.
        loud : bool
            Print in uppercase.

        Returns
        -------
        str
            The greeting message(s).
        """
        _cmd = [
            'myapp',
            'greet',
            str(params.name),
            '--count', str(params.count),
            *(['--loud'] if params.loud else []),
        ]
        _proc = await asyncio.create_subprocess_exec(
            *_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout_b, _stderr_b = await _proc.communicate()
        _stdout = _stdout_b.decode()
        _stderr = _stderr_b.decode()
        if _proc.returncode != 0:
            return (
                f"Error (exit {_proc.returncode}):\n"
                f"stdout: {_stdout}\nstderr: {_stderr}"
            )
        return _stdout

        # Direct import alternative (uncomment if greet returns a value):
        # from mypackage.cli import greet
        # return greet(name=params.name, count=params.count, loud=params.loud)
```

Key things to note in the generated output:
- Each tool's parameters become a **Pydantic `BaseModel`** (`GreetInput`) — gives the MCP host a full JSON schema for validation and LLM-visible field descriptions.
- Tool functions are **`async`** and use `asyncio.create_subprocess_exec` — no blocking the event loop.
- Tool names are **prefixed** with the entry point slug (`myapp_greet`) by default; set `prefix_tool_names = false` to disable.
- MCP **annotations** (`readOnlyHint`, `destructiveHint`, etc.) are inferred from the tool name's first word and can be overridden per-tool in config.
- Errors are returned as **strings** rather than raised as exceptions — MCP errors belong in the result object.

### `mcp/mcp_server.py` (written once — edit freely)

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
python mcp/mcp_server.py
```

**MCP Inspector (via cli2mcp):**
```bash
cli2mcp inspect mcp/mcp_server.py
```

**Claude Desktop** — add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "my-project": {
      "command": "python",
      "args": ["/path/to/your/project/mcp/mcp_server.py"]
    }
  }
}
```

---

## How AI agents can use this tool

1. Add `[tool.cli2mcp]` to the project's `pyproject.toml` with the correct `entry_point` and `source_dirs`.
2. Run `cli2mcp list` to verify which tools were discovered and confirm names and parameter counts look right.
3. Run `cli2mcp generate` to produce `mcp/mcp_tools_generated.py` and (on first run) `mcp/mcp_server.py`.
4. Run `cli2mcp validate mcp/mcp_tools_generated.py` as a sanity check — confirms the file is valid Python.
5. Register the server with the MCP host using the `python mcp/mcp_server.py` invocation.

The `--dry-run` flag on `generate` prints both file contents to stdout, letting an agent preview the output before writing. `list` makes it easy to detect misconfigured `source_dirs` before wasting a generation step.

## Keeping the generated file current

`mcp_tools_generated.py` can drift from the CLI source if commands are added or changed without re-running `generate`. Use `cli2mcp check` to detect this in CI:

```yaml
# .github/workflows/ci.yml
- run: cli2mcp check
```

Or as a pre-commit hook:

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: cli2mcp-check
      name: Check MCP module is up to date
      entry: cli2mcp check
      language: system
      files: \.py$
```

`check` exits nonzero if the generated file is missing or stale, with a clear message directing the developer to run `cli2mcp generate`.

---

## Limitations

- **Python 3.11+ required** (`tomllib` is stdlib from 3.11; older versions need `tomli` installed separately).
- **Click, Typer, and argparse only** — Fire and other frameworks are not supported.
- **Tools always return `str`** (stdout of the subprocess) by default. Set `prefer_direct_import = true` in config to generate direct function-call bodies instead, which can return richer types.
- **CLI must be on PATH** — the generated server delegates via subprocess, so your CLI entry point must be installed and accessible in the same environment where `mcp_server.py` runs. `cli2mcp generate` warns if the entry point is not found on PATH.
