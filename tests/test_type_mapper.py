"""Tests for 5a (subscript types) and 5b (Any fallback) in type_mapper."""
from __future__ import annotations

import ast
import pytest

from cli2mcp.parsers.type_mapper import ast_node_to_type_str, map_type


# ---------------------------------------------------------------------------
# 5a: Subscript / generic types
# ---------------------------------------------------------------------------

class TestSubscriptTypes:
    def _parse_expr(self, source: str) -> ast.expr:
        return ast.parse(source, mode="eval").body

    def test_list_str(self):
        node = self._parse_expr("List[str]")
        assert ast_node_to_type_str(node) == "list[str]"

    def test_optional_int(self):
        node = self._parse_expr("Optional[int]")
        assert ast_node_to_type_str(node) == "Optional[int]"

    def test_dict_str_any(self):
        node = self._parse_expr("Dict[str, Any]")
        result = ast_node_to_type_str(node)
        assert result == "dict[str, Any]"

    def test_tuple_int_str(self):
        node = self._parse_expr("Tuple[int, str]")
        result = ast_node_to_type_str(node)
        assert "int" in result and "str" in result

    def test_nested_list(self):
        node = self._parse_expr("List[List[str]]")
        result = ast_node_to_type_str(node)
        assert "list" in result.lower()

    def test_pep604_union(self):
        """X | Y union syntax (Python 3.10+)."""
        node = self._parse_expr("str | None")
        result = ast_node_to_type_str(node)
        assert "str" in result
        assert "None" in result

    def test_simple_name_unchanged(self):
        node = self._parse_expr("int")
        assert ast_node_to_type_str(node) == "int"

    def test_click_attribute_type(self):
        """click.INT → 'int' via attribute lookup."""
        node = self._parse_expr("click.INT")
        assert ast_node_to_type_str(node) == "int"

    def test_click_path_call(self):
        """click.Path(exists=True) → 'str'."""
        node = self._parse_expr("click.Path(exists=True)")
        assert ast_node_to_type_str(node) == "str"


# ---------------------------------------------------------------------------
# 5b: Unknown types → Any (not silent str)
# ---------------------------------------------------------------------------

class TestUnknownTypesFallback:
    def test_unknown_ast_node_returns_any(self):
        """Unrecognisable AST nodes (like ast.Lambda) should return 'Any'."""
        node = ast.parse("lambda x: x", mode="eval").body
        result = ast_node_to_type_str(node)
        assert result == "Any"

    def test_none_node_returns_str(self):
        """None node (no type annotation) still returns 'str' as a safe default."""
        assert ast_node_to_type_str(None) == "str"

    def test_constant_none_returns_none_type(self):
        """ast.Constant(None) represents the None type (e.g. `-> None` or `str | None`)."""
        node = ast.Constant(value=None)
        assert ast_node_to_type_str(node) == "None"


# ---------------------------------------------------------------------------
# map_type
# ---------------------------------------------------------------------------

class TestMapType:
    def test_known_click_type(self):
        assert map_type("STRING") == "str"
        assert map_type("INT") == "int"
        assert map_type("FLOAT") == "float"
        assert map_type("BOOL") == "bool"

    def test_known_python_type(self):
        assert map_type("str") == "str"
        assert map_type("int") == "int"

    def test_none_returns_str(self):
        assert map_type(None) == "str"

    def test_unknown_returns_raw_name(self):
        """5b: unknown type names return the raw name (not 'str') for honesty."""
        result = map_type("MyCustomType")
        assert result == "MyCustomType"  # returned as-is, not silently str

    def test_filetype_maps_to_str(self):
        """2d: argparse.FileType should map to str."""
        assert map_type("FileType") == "str"
