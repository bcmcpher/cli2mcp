"""Maps Click/argparse type strings to Python annotation strings."""
from __future__ import annotations

import ast

_CLICK_TYPE_MAP: dict[str, str] = {
    # Click built-in type names
    "STRING": "str",
    "INT": "int",
    "FLOAT": "float",
    "BOOL": "bool",
    "Path": "str",
    "File": "str",
    "FileType": "str",  # 2d: argparse.FileType → still a path string at the CLI boundary
    "UUID": "str",  # str (UUID format)
    "DateTime": "str",  # str (datetime ISO 8601)
    "Tuple": "tuple",
    "List": "list",
    # Python built-in names
    "str": "str",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "list": "list",
    "tuple": "tuple",
    "dict": "dict",
    "bytes": "bytes",
    # typing module
    "Optional": "Optional",
    "Union": "Union",
    "Any": "Any",
    "List": "list",
    "Dict": "dict",
    "Tuple": "tuple",
    "Set": "set",
    "Sequence": "list",
}


def map_type(raw_type: str | None) -> str:
    """Map a raw type string (from AST or click/argparse metadata) to a Python annotation string."""
    if raw_type is None:
        return "str"
    # Return mapped value if known; otherwise return the raw name as-is
    # (it may be a user-defined type, which is fine as a string annotation)
    return _CLICK_TYPE_MAP.get(raw_type, raw_type)


def ast_node_to_type_str(node: ast.expr | None) -> str:
    """Convert an AST expression node representing a type to a string annotation."""
    if node is None:
        # No annotation present → str is the CLI default
        return "str"
    if isinstance(node, ast.Constant) and node.value is None:
        # The annotation is literally `None` (e.g., `-> None` or `str | None`)
        return "None"
    if isinstance(node, ast.Name):
        return map_type(node.id)
    if isinstance(node, ast.Attribute):
        # e.g. click.STRING, click.Path, argparse.FileType
        return map_type(node.attr)
    if isinstance(node, ast.Call):
        # e.g. click.Path(exists=True) → treat as Path → str
        # e.g. argparse.FileType("r") → str
        if isinstance(node.func, ast.Attribute):
            return map_type(node.func.attr)
        if isinstance(node.func, ast.Name):
            return map_type(node.func.id)
    if isinstance(node, ast.Subscript):  # 5a: List[str], Optional[int], Dict[str, Any]
        outer = ast_node_to_type_str(node.value)
        inner = ast_node_to_type_str(node.slice)
        return f"{outer}[{inner}]"
    if isinstance(node, ast.Tuple):  # 5a: slice of Dict[str, Any] → "str, Any"
        parts = [ast_node_to_type_str(elt) for elt in node.elts]
        return ", ".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        # PEP 604: X | Y union syntax (Python 3.10+)
        left = ast_node_to_type_str(node.left)
        right = ast_node_to_type_str(node.right)
        return f"{left} | {right}"
    # 5b: Completely unrecognisable AST node → Any (more honest than silent str)
    return "Any"
