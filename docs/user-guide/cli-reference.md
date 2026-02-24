# CLI Reference

`cli2mcp` exposes four subcommands. All accept `--help` for inline usage.

```
cli2mcp init     [--server-name NAME] [--entry-point CMD] [--source-dir DIR] [--config FILE]
cli2mcp generate [--config FILE] [--output FILE] [--dry-run] [--force]
cli2mcp list     [--config FILE] [--format {text,json}]
cli2mcp validate FILE
```

---

## `cli2mcp init`

Scaffold a `[tool.cli2mcp]` section in `pyproject.toml` interactively.

```bash
cli2mcp init
cli2mcp init --server-name "My Server" --entry-point myapp --source-dir src/mypackage
```

| Option | Default | Description |
|--------|---------|-------------|
| `--server-name` | *(prompted)* | Name of the MCP server (`server_name` in config). |
| `--entry-point` | *(prompted)* | CLI entry point command name (`entry_point` in config). |
| `--source-dir` | `src` *(prompted)* | Source directory containing CLI code (`source_dirs` in config). |
| `--config` | `pyproject.toml` | Path to the `pyproject.toml` to update. |

**Behaviour:**

- If the target file exists and already contains `[tool.cli2mcp]`, the command exits with an error.
- If the target file exists without `[tool.cli2mcp]`, the section is appended.
- If the target file does not exist, it is created.

---

## `cli2mcp generate`

Scrape source directories and write the tools module and server scaffold.

```bash
cli2mcp generate
cli2mcp generate --dry-run
cli2mcp generate --output custom_tools.py
cli2mcp generate --force
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config` | `pyproject.toml` | Path to config file. |
| `--output` | *(from config)* | Override the output path for the tools module. |
| `--dry-run` | `False` | Print both generated files to stdout instead of writing them. |
| `--force` | `False` | Overwrite `server_file` even if it already exists. |

**Behaviour:**

- The tools module (`output_file`) is **always** overwritten.
- The server scaffold (`server_file`) is written only if it does not exist, unless `--force` is passed.
- Exits with a non-zero code if no tools are discovered.

---

## `cli2mcp list`

List discovered tools without writing any files. Use this to verify configuration before running `generate`.

```bash
cli2mcp list
cli2mcp list --format json
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config` | `pyproject.toml` | Path to config file. |
| `--format` | `text` | Output format: `text` for human-readable, `json` for machine-readable. |

**JSON output shape:**

```json
[
  {
    "name": "greet",
    "framework": "click",
    "command": "myapp greet",
    "description": "Greet a user by name.",
    "param_count": 3,
    "params": [
      {"name": "name", "type": "str", "required": true, "default": null, "choices": null},
      {"name": "count", "type": "int", "required": false, "default": 1, "choices": null},
      {"name": "loud", "type": "bool", "required": false, "default": false, "choices": null}
    ]
  }
]
```

---

## `cli2mcp validate`

Parse-check a generated file for syntax errors without importing it.

```bash
cli2mcp validate mcp_tools_generated.py
cli2mcp validate mcp_server.py
```

| Argument | Description |
|----------|-------------|
| `FILE` | Path to the Python file to validate (must exist). |

Exits with code `0` and prints `OK` if the file parses cleanly; exits with code `1` and prints the syntax error otherwise.
