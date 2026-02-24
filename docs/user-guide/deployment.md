# Deployment

## Running the server directly

```bash
python mcp/mcp_server.py
```

The server starts and listens for MCP connections over stdio (the default FastMCP transport).

## MCP Inspector

The MCP Inspector is a browser-based tool for testing your server interactively:

```bash
mcp dev mcp/mcp_server.py
```

This starts both the server and the inspector UI, letting you call tools and inspect inputs/outputs without a full MCP host.

## Claude Desktop

Add an entry to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "my-project": {
      "command": "python",
      "args": ["/absolute/path/to/your/project/mcp/mcp_server.py"]
    }
  }
}
```

The config file is typically located at:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Restart Claude Desktop after editing the config.

## Environment requirements

The generated server delegates to your CLI via `subprocess.run()`. This means:

- Your CLI entry point (`entry_point` in config) must be installed and on `PATH` in the same environment where `mcp/mcp_server.py` runs.
- The `mcp` package (FastMCP) must be installed in that environment.

A typical setup for a project called `myapp`:

```bash
pip install myapp mcp
python mcp/mcp_server.py
```

## Using a virtual environment

If your CLI lives in a virtual environment, run the server inside it:

```bash
source .venv/bin/activate
python mcp/mcp_server.py
```

Or point Claude Desktop at the venv's Python directly:

```json
{
  "mcpServers": {
    "my-project": {
      "command": "/path/to/.venv/bin/python",
      "args": ["/path/to/mcp/mcp_server.py"]
    }
  }
}
```

## Subprocess timeout

If your CLI commands can block (network calls, long computations), set `subprocess_timeout` in config to prevent the server from hanging:

```toml
[tool.cli2mcp]
subprocess_timeout = 30
```

Any call that exceeds the timeout raises `subprocess.TimeoutExpired`, which the MCP host will see as a tool error.
