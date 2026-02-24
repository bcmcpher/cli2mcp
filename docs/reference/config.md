# Config

Configuration loading from `pyproject.toml`.

## `Config`

::: cli2mcp.config.Config
    options:
      show_source: true

---

A frozen snapshot of all settings read from `[tool.cli2mcp]`. Constructed by `load_config()` and passed through the scrape → generate pipeline.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `server_name` | `str` | — | Passed to `FastMCP(...)` in the generated server. |
| `entry_point` | `str` | — | CLI command name on PATH. |
| `source_dirs` | `list[Path]` | — | Resolved absolute paths to scan. |
| `output_file` | `Path` | `mcp_tools_generated.py` | Tools module output path. |
| `server_file` | `Path` | `mcp_server.py` | Server scaffold output path. |
| `include_patterns` | `list[str]` | `["*.py"]` | Filename glob patterns to include. |
| `exclude_patterns` | `list[str]` | `["test_*", "_*"]` | Filename glob patterns to exclude. |
| `subprocess_timeout` | `int \| None` | `None` | Subprocess timeout in seconds. |

---

## `load_config`

::: cli2mcp.config.load_config
    options:
      show_source: true

---

Reads and validates the `[tool.cli2mcp]` section from a `pyproject.toml` file.

**Raises:**

- `FileNotFoundError` — if the config file does not exist.
- `ValueError` — if the `[tool.cli2mcp]` section is absent, or a required key (`server_name`, `entry_point`, `source_dirs`) is missing.
