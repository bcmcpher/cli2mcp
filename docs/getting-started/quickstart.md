# Quick Start

This guide takes you from a bare Python CLI to a running MCP server in four steps.

## Step 1 — Scaffold the config

Run `cli2mcp init` in your project root to interactively create the `[tool.cli2mcp]` section in `pyproject.toml`:

```bash
cli2mcp init
```

Answer the prompts:

```
MCP server name: My Project MCP Server
CLI entry point (e.g. mycli): myapp
Source directory containing CLI code [src]: src/mypackage
```

This appends the following block to your `pyproject.toml` (or creates the file if it doesn't exist):

```toml
[tool.cli2mcp]
server_name = "My Project MCP Server"
entry_point = "myapp"
source_dirs = ["src/mypackage"]
output_file = "mcp_tools_generated.py"
server_file = "mcp_server.py"
include_patterns = ["*.py"]
exclude_patterns = ["test_*", "_*"]
```

You can also write this block manually — see [Configuration](configuration.md) for all available keys.

## Step 2 — Verify discovery

Before generating, confirm that `cli2mcp` finds the tools you expect:

```bash
cli2mcp list
```

Example output:

```
Discovered 3 tool(s):

  greet (click)
    command : myapp greet
    summary : Greet a user by name.
    params  : 3

  convert (argparse)
    command : myapp convert
    summary : Convert files between formats.
    params  : 5
```

If the list is empty or missing commands, check your `source_dirs` and `exclude_patterns` in the config.

## Step 3 — Generate

```bash
cli2mcp generate
```

On the first run this writes **both** files:

```
Generated mcp_tools_generated.py with 3 tool(s).
Created server scaffold: mcp_server.py
```

On subsequent runs only `mcp_tools_generated.py` is updated; `mcp_server.py` is left untouched so your customisations are safe.

Use `--dry-run` to preview the output without writing:

```bash
cli2mcp generate --dry-run
```

## Step 4 — Run the server

```bash
python mcp_server.py
```

Or use the MCP inspector for interactive testing:

```bash
mcp dev mcp_server.py
```

Your CLI tools are now available as MCP tools to any compatible host (Claude Desktop, custom agents, etc.).

---

!!! tip "Next steps"
    - Read [Writing CLI Code](../user-guide/writing-clis.md) to get the most out of docstring extraction.
    - See [Deployment](../user-guide/deployment.md) to connect the server to Claude Desktop.
    - Check [Generated Output](../user-guide/generated-output.md) to understand what was written and how to customise it.
