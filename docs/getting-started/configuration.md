# Configuration

All configuration lives in a `[tool.cli2mcp]` section inside your project's `pyproject.toml`.

## Minimal example

```toml
[tool.cli2mcp]
server_name = "My Project MCP Server"
entry_point = "myapp"
source_dirs = ["src/mypackage"]
```

## Full example

```toml
[tool.cli2mcp]
server_name      = "My Project MCP Server"
entry_point      = "myapp"
source_dirs      = ["src/mypackage", "src/plugins"]
output_file      = "mcp_tools_generated.py"
server_file      = "mcp_server.py"
include_patterns = ["*.py"]
exclude_patterns = ["test_*", "_*", "conftest.py"]
subprocess_timeout = 30
```

## Reference

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `server_name` | yes | — | Name passed to `FastMCP(...)` in the generated server. |
| `entry_point` | yes | — | CLI command name on PATH (e.g. `myapp`). Used as the first token in every subprocess call. |
| `source_dirs` | yes | — | List of directories to scan for CLI source files, relative to the `pyproject.toml` directory. |
| `output_file` | no | `mcp_tools_generated.py` | Path for the auto-generated tools module. Always overwritten by `cli2mcp generate`. |
| `server_file` | no | `mcp_server.py` | Path for the one-time server scaffold. Written only if the file does not exist (unless `--force` is passed). |
| `include_patterns` | no | `["*.py"]` | Glob patterns a filename must match to be scanned. |
| `exclude_patterns` | no | `["test_*", "_*"]` | Glob patterns that cause a file to be skipped even if it matches `include_patterns`. |
| `subprocess_timeout` | no | `None` (no limit) | Maximum seconds to wait for a subprocess call before raising `TimeoutExpired`. |

## Notes

### `source_dirs`

Paths are resolved relative to the directory containing `pyproject.toml`, not the working directory. You can list multiple directories:

```toml
source_dirs = ["src/mypackage", "src/plugins"]
```

### `include_patterns` / `exclude_patterns`

Patterns are matched against the **filename only** (not the full path) using `fnmatch`. A file is included if it matches at least one `include_patterns` entry *and* does not match any `exclude_patterns` entry.

### `subprocess_timeout`

If your CLI commands can block (e.g. waiting for network I/O), set a timeout to prevent the MCP server from hanging:

```toml
subprocess_timeout = 30
```

This value is passed directly to `subprocess.run(timeout=...)` in every generated tool function.
