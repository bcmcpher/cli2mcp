"""AST-based scraper for Typer CLI tools."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from cli2mcp.models import ParamDef, ToolDef
from cli2mcp.parsers.docstring import parse_numpy_docstring
from cli2mcp.parsers.type_mapper import ast_node_to_type_str
from cli2mcp.scrapers.base import BaseScraper


def _ast_to_python(node: ast.expr | None) -> Any:
    """Convert a simple AST constant/name node to a Python value."""
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id == "True":
            return True
        if node.id == "False":
            return False
        if node.id == "None":
            return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        val = _ast_to_python(node.operand)
        if isinstance(val, (int, float)):
            return -val
    return None


def _get_keyword_value(call: ast.Call, key: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == key:
            return kw.value
    return None


def _find_typer_app_names(tree: ast.AST) -> set[str]:
    """Find variable names assigned to typer.Typer() instances."""
    app_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        is_typer_ctor = (
            (
                isinstance(func, ast.Attribute)
                and func.attr == "Typer"
                and isinstance(func.value, ast.Name)
                and func.value.id == "typer"
            )
            or (isinstance(func, ast.Name) and func.id == "Typer")
        )
        if is_typer_ctor:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    app_names.add(target.id)
    return app_names


def _is_typer_command_decorator(dec: ast.expr, app_names: set[str]) -> bool:
    """Return True if the decorator is @<app>.command() for a known Typer app."""
    node = dec.func if isinstance(dec, ast.Call) else dec
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "command"
        and isinstance(node.value, ast.Name)
        and node.value.id in app_names
    )


def _parse_typer_param(
    arg: ast.arg,
    default_node: ast.expr | None,
) -> ParamDef:
    """Parse one function parameter into a ParamDef."""
    name = arg.arg
    type_annotation = ast_node_to_type_str(arg.annotation) if arg.annotation else "str"

    required = True
    default = None
    description = ""
    is_option = False  # True → --flag style; False → positional argument
    is_flag = False

    if isinstance(default_node, ast.Call):
        func = default_node.func
        func_name: str | None = None
        if isinstance(func, ast.Attribute):
            func_name = func.attr  # "Option" or "Argument"
        elif isinstance(func, ast.Name):
            func_name = func.id

        if func_name == "Option":
            is_option = True
            # First positional arg is the default value (or ... for required)
            if default_node.args:
                raw = _ast_to_python(default_node.args[0])
                if raw is ...:
                    required = True
                    default = None
                else:
                    default = raw
                    required = False
            else:
                required = True
            help_node = _get_keyword_value(default_node, "help")
            description = str(_ast_to_python(help_node) or "")
        elif func_name == "Argument":
            is_option = False
            if default_node.args:
                raw = _ast_to_python(default_node.args[0])
                if raw is ...:
                    required = True
                    default = None
                else:
                    default = raw
                    required = False
            else:
                required = True
            help_node = _get_keyword_value(default_node, "help")
            description = str(_ast_to_python(help_node) or "")
        else:
            # Unknown call used as default — treat as plain default
            default = None
            required = False
            is_option = True
    elif default_node is not None:
        # Plain Python literal default
        default = _ast_to_python(default_node)
        required = False
        is_option = True
    else:
        # No default → required positional argument
        required = True
        is_option = False

    # bool type → boolean flag
    if type_annotation == "bool":
        is_flag = True
        if default is None:
            default = False
        required = False

    cli_flags = [f"--{name.replace('_', '-')}"] if is_option else [name]

    return ParamDef(
        name=name,
        cli_flags=cli_flags,
        type_annotation=type_annotation,
        default=default,
        required=required,
        description=description,
        is_flag=is_flag,
        is_multiple=False,
        choices=None,
    )


class TyperScraper(BaseScraper):
    """Scrapes Typer CLI tools from Python source files using AST analysis."""

    def __init__(self, source_module: str = "", cli_command: str = "") -> None:
        self.source_module = source_module
        self.cli_command = cli_command

    def detect(self, tree: ast.AST) -> bool:
        """Return True if this file imports typer."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "typer":
                        return True
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod == "typer" or mod.startswith("typer."):
                    return True
        return False

    def scrape_file(self, path: Path) -> list[ToolDef]:
        """Parse a Python source file and return Typer ToolDef objects."""
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            return []
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []

        if not self.detect(tree):
            return []

        app_names = _find_typer_app_names(tree)
        source_module = self.source_module or path.stem
        tools: list[ToolDef] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            is_command = False
            for dec in node.decorator_list:
                if _is_typer_command_decorator(dec, app_names):
                    is_command = True
                    break

            if not is_command:
                continue

            func_name = node.name
            tool_name = func_name

            # Check for name= override in @app.command(name="...")
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                if not _is_typer_command_decorator(dec, app_names):
                    continue
                name_node = _get_keyword_value(dec, "name")
                if name_node:
                    n = _ast_to_python(name_node)
                    if n:
                        tool_name = str(n).replace("-", "_")
                break

            raw_docstring = ast.get_docstring(node)
            parsed_doc = parse_numpy_docstring(raw_docstring)

            # Build defaults map for all args
            func_args = node.args
            all_args = func_args.posonlyargs + func_args.args
            n_no_default = len(all_args) - len(func_args.defaults)
            defaults_map: dict[str, ast.expr | None] = {}
            for i, arg in enumerate(all_args):
                idx = i - n_no_default
                defaults_map[arg.arg] = func_args.defaults[idx] if idx >= 0 else None
            for arg, def_node in zip(func_args.kwonlyargs, func_args.kw_defaults):
                defaults_map[arg.arg] = def_node

            params: list[ParamDef] = []
            for arg in all_args + func_args.kwonlyargs:
                if arg.arg in ("self", "cls"):
                    continue
                param = _parse_typer_param(arg, defaults_map.get(arg.arg))
                # Merge docstring descriptions
                if arg.arg in parsed_doc.params and not param.description:
                    param.description = parsed_doc.params[arg.arg]
                # Use docstring type if annotation was missing
                if (
                    param.type_annotation in ("str", "Any")
                    and arg.arg in parsed_doc.param_types
                ):
                    param.type_annotation = parsed_doc.param_types[arg.arg]
                params.append(param)

            return_type = "str"
            if node.returns is not None:
                from cli2mcp.parsers.type_mapper import ast_node_to_type_str as _t

                ann = _t(node.returns)
                if ann not in ("None", "str"):
                    return_type = ann

            tool = ToolDef(
                name=tool_name,
                description=parsed_doc.summary or f"Run {tool_name}",
                parameters=params,
                return_description=parsed_doc.returns or "Command output",
                source_module=source_module,
                source_function=func_name,
                cli_command=self.cli_command,
                cli_subcommand=tool_name,
                framework="typer",
                return_type=return_type,
            )
            tools.append(tool)

        return tools
