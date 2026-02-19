"""Maps Click/argparse type strings to Python annotation strings."""
from __future__ import annotations

import ast

_CLICK_TYPE_MAP: dict[str, str] = {
    "STRING": "str",
    "INT": "int",
    "FLOAT": "float",
    "BOOL": "bool",
    "Path": "str",
    "File": "str",
    "UUID": "str",
    "str": "str",
    "int": "int",
    "float": "float",
    "bool": "bool",
}


def map_type(raw_type: str | None) -> str:
    """Map a raw type string (from AST or click/argparse metadata) to a Python annotation string."""
    if raw_type is None:
        return "str"
    return _CLICK_TYPE_MAP.get(raw_type, "str")


def ast_node_to_type_str(node: ast.expr | None) -> str:
    """Convert an AST expression node representing a type to a string annotation."""
    if node is None:
        return "str"
    if isinstance(node, ast.Constant) and node.value is None:
        return "str"
    if isinstance(node, ast.Name):
        return map_type(node.id)
    if isinstance(node, ast.Attribute):
        # e.g. click.STRING, click.Path
        return map_type(node.attr)
    if isinstance(node, ast.Call):
        # e.g. click.Path(exists=True) → treat as Path → str
        if isinstance(node.func, ast.Attribute):
            return map_type(node.func.attr)
        if isinstance(node.func, ast.Name):
            return map_type(node.func.id)
    return "str"
