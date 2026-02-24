# Generator

Renders `list[ToolDef]` + `Config` into Python source strings for the two output files.

## `generate_module`

::: cli2mcp.generators.mcp_server.generate_module
    options:
      show_source: true

---

Generates the content of the always-overwritten tools module (`mcp_tools_generated.py`).

The output consists of:

1. A module-level docstring with version, source dirs, and timestamp.
2. `from __future__ import annotations` and `import subprocess`.
3. A single `_register_tools(mcp)` function containing one `@mcp.tool()` function per `ToolDef`.

---

## `generate_server_scaffold`

::: cli2mcp.generators.mcp_server.generate_server_scaffold
    options:
      show_source: true

---

Generates the content of the one-time server scaffold (`mcp_server.py`). This file imports `_register_tools` from the tools module and calls it on a `FastMCP` instance.

The scaffold is intentionally minimal so it is easy to extend with hand-written tools.

---

## Internal helpers

These functions are not part of the public API but are documented here for contributors.

### `_render_tool`

Renders a single `@mcp.tool()` function block from a `ToolDef`. Called once per tool by `generate_module`.

The rendered block includes:
- A function signature with required parameters first, then optional ones with defaults.
- A NumPy-style docstring merging the tool description, per-parameter descriptions, and the return description.
- A `subprocess.run()` body that reconstructs the exact CLI invocation.
- A commented-out direct-import alternative.

### `_format_param_sig`

Formats the function signature parameter list. Required parameters come first (no default), optional parameters follow (with `= default`).

### `_format_param_docs`

Formats the `Parameters` section of the generated NumPy docstring. Appends `Choices: a, b, c.` to descriptions when `choices` is set.
