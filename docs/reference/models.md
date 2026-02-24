# Models

Core data classes that flow through the scrape → generate pipeline.

## `ParamDef`

::: cli2mcp.models.ParamDef
    options:
      show_source: true

---

Represents a single CLI parameter (option or positional argument) extracted from a source file.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Python-safe parameter name (dashes replaced with underscores). |
| `cli_flags` | `list[str]` | Raw flag strings as they appear in the source (e.g. `["--verbose", "-v"]`). |
| `type_annotation` | `str` | Python type annotation string (e.g. `"int"`, `"list[str]"`). |
| `default` | `Any` | Default value, or `None` if not specified. |
| `required` | `bool` | Whether the parameter is required. Positional args are required by default. |
| `description` | `str` | Help text, populated from `help=` string or NumPy docstring. |
| `is_flag` | `bool` | `True` for boolean flags (`store_true` / `is_flag=True`). |
| `is_multiple` | `bool` | `True` for list-valued parameters (`nargs="+"`, `action="append"`, `multiple=True`). |
| `choices` | `list[str] \| None` | Allowed values, if any (from `click.Choice` or argparse `choices=`). |

---

## `ToolDef`

::: cli2mcp.models.ToolDef
    options:
      show_source: true

---

Represents a single CLI command that will become an MCP tool.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Python-safe tool name used as the MCP function name. |
| `description` | `str` | One-line summary from the docstring or `help=` text. |
| `parameters` | `list[ParamDef]` | Ordered list of parameters. |
| `return_description` | `str` | Returns description from the docstring. |
| `source_module` | `str` | Dotted module path of the source file (e.g. `mypackage.commands`). |
| `source_function` | `str` | Name of the source function (used in the direct-import comment). |
| `cli_command` | `str` | Entry point command (first token of the subprocess call). |
| `cli_subcommand` | `str \| None` | Subcommand name (second token), or `None` for top-level commands. |
| `framework` | `str` | `"click"` or `"argparse"`. |
