# Parsers

Utilities for extracting structured information from docstrings and AST type nodes.

## Docstring parser

### `ParsedDocstring`

::: cli2mcp.parsers.docstring.ParsedDocstring
    options:
      show_source: true

---

Container for the structured output of `parse_numpy_docstring()`.

| Field | Type | Description |
|-------|------|-------------|
| `summary` | `str` | First non-blank line of the docstring. Used as the tool description. |
| `extended` | `str` | Body text between the summary and the first section header. |
| `params` | `dict[str, str]` | Mapping of parameter name → description from the `Parameters` section. |
| `returns` | `str` | Description from the `Returns` section. |

---

### `parse_numpy_docstring`

::: cli2mcp.parsers.docstring.parse_numpy_docstring
    options:
      show_source: true

---

Parses a NumPy-style docstring into a `ParsedDocstring`. Returns an empty `ParsedDocstring` if `docstring` is `None` or blank.

**Example:**

```python
from cli2mcp.parsers.docstring import parse_numpy_docstring

doc = parse_numpy_docstring("""
Convert files between formats.

Parameters
----------
input : str
    Input file path.
output : str
    Output file path.

Returns
-------
str
    Conversion result summary.
""")

assert doc.summary == "Convert files between formats."
assert doc.params["input"] == "Input file path."
assert doc.returns == "Conversion result summary."
```

---

## Type mapper

### `ast_node_to_type_str`

::: cli2mcp.parsers.type_mapper.ast_node_to_type_str
    options:
      show_source: true

---

Converts an AST expression node (as found in Click `type=` or argparse `type=` arguments) to a Python type annotation string.

| AST node | Returns |
|----------|---------|
| `ast.Name(id="int")` | `"int"` |
| `ast.Name(id="float")` | `"float"` |
| `ast.Name(id="bool")` | `"bool"` |
| `ast.Name(id="str")` | `"str"` |
| `ast.Attribute(attr="Path")` | `"str"` |
| `ast.Call` for `click.Choice(...)` | `"str"` |
| anything else / `None` | `"str"` |

---

### `map_type`

::: cli2mcp.parsers.type_mapper.map_type
    options:
      show_source: true

---

Maps a raw type string (as scraped from source) to a normalised Python annotation string. Returns `"str"` for any unrecognised input.
