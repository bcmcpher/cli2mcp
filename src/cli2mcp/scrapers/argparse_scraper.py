"""AST-based scraper for argparse CLI tools."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from cli2mcp.models import ParamDef, ToolDef
from cli2mcp.parsers.docstring import parse_numpy_docstring
from cli2mcp.parsers.type_mapper import ast_node_to_type_str
from cli2mcp.scrapers.base import BaseScraper


def _ast_to_python(node: ast.expr | None) -> Any:
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
    return None


def _is_argumentparser_call(node: ast.expr) -> bool:
    """Check if an expression is a call to ArgumentParser."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id == "ArgumentParser":
        return True
    if isinstance(func, ast.Attribute) and func.attr == "ArgumentParser":
        return True
    return False


def _find_parser_var(func_body: list[ast.stmt]) -> tuple[str | None, str | None]:
    """Find the variable name assigned from ArgumentParser() and the prog name.

    Returns (var_name, prog_name).
    """
    for stmt in func_body:
        if not isinstance(stmt, ast.Assign):
            continue
        if not _is_argumentparser_call(stmt.value):
            continue
        # Get the variable name
        if stmt.targets and isinstance(stmt.targets[0], ast.Name):
            var_name = stmt.targets[0].id
            # Try to extract prog=
            prog: str | None = None
            prog_node = None
            call = stmt.value
            if isinstance(call, ast.Call):
                for kw in call.keywords:
                    if kw.arg == "prog":
                        prog_node = kw.value
                        break
            if prog_node is not None:
                prog = _ast_to_python(prog_node)
            return var_name, prog
    return None, None


def _find_add_argument_calls(func_body: list[ast.stmt], parser_var: str) -> list[ast.Call]:
    """Find all <parser_var>.add_argument(...) calls in a function body."""
    calls: list[ast.Call] = []
    for stmt in func_body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "add_argument"
                and isinstance(func.value, ast.Name)
                and func.value.id == parser_var
            ):
                calls.append(node)
    return calls


def _parse_add_argument(call: ast.Call) -> ParamDef | None:
    """Parse an add_argument(...) call into a ParamDef."""
    # Positional string args are the flags/names
    cli_flags: list[str] = []
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            cli_flags.append(arg.value)

    if not cli_flags:
        return None

    # Determine param name
    dest_node = None
    for kw in call.keywords:
        if kw.arg == "dest":
            dest_node = kw.value
            break
    if dest_node is not None:
        param_name = str(_ast_to_python(dest_node) or "")
    else:
        long_flags = [f for f in cli_flags if f.startswith("--")]
        if long_flags:
            param_name = long_flags[0].lstrip("-").replace("-", "_")
        else:
            param_name = cli_flags[0].lstrip("-").replace("-", "_")

    # type=
    type_annotation = "str"
    for kw in call.keywords:
        if kw.arg == "type":
            type_annotation = ast_node_to_type_str(kw.value)
            break

    # default=
    default = None
    for kw in call.keywords:
        if kw.arg == "default":
            default = _ast_to_python(kw.value)
            break

    # required=
    required = None
    for kw in call.keywords:
        if kw.arg == "required":
            required = _ast_to_python(kw.value)
            break

    is_positional = not cli_flags[0].startswith("-")
    if required is None:
        required = is_positional  # positional args are required by default

    # action= store_true / store_false → bool flag
    is_flag = False
    for kw in call.keywords:
        if kw.arg == "action":
            action_val = _ast_to_python(kw.value)
            if action_val in ("store_true", "store_false"):
                is_flag = True
                type_annotation = "bool"
                default = False if default is None else default
                required = False
            break

    # help=
    description = ""
    for kw in call.keywords:
        if kw.arg == "help":
            description = str(_ast_to_python(kw.value) or "")
            break

    return ParamDef(
        name=param_name,
        cli_flags=cli_flags,
        type_annotation=type_annotation,
        default=default,
        required=bool(required),
        description=description,
        is_flag=is_flag,
    )


class ArgparseScraper(BaseScraper):
    """Scrapes argparse-based CLI tools from Python source files using AST analysis."""

    def __init__(self, source_module: str = "", cli_command: str = "") -> None:
        self.source_module = source_module
        self.cli_command = cli_command

    def detect(self, tree: ast.AST) -> bool:
        """Return True if this file imports argparse."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "argparse":
                        return True
            elif isinstance(node, ast.ImportFrom):
                if node.module == "argparse":
                    return True
        return False

    def scrape_file(self, path: Path) -> list[ToolDef]:
        """Parse a Python source file and return argparse ToolDef objects."""
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []

        if not self.detect(tree):
            return []

        source_module = self.source_module or path.stem
        tools: list[ToolDef] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            parser_var, prog = _find_parser_var(node.body)
            if parser_var is None:
                continue

            add_arg_calls = _find_add_argument_calls(node.body, parser_var)
            if not add_arg_calls:
                continue

            params: list[ParamDef] = []
            for call in add_arg_calls:
                param = _parse_add_argument(call)
                if param is not None:
                    params.append(param)

            raw_docstring = ast.get_docstring(node)
            parsed_doc = parse_numpy_docstring(raw_docstring)

            # Merge docstring descriptions
            for param in params:
                if param.name in parsed_doc.params and not param.description:
                    param.description = parsed_doc.params[param.name]

            func_name = node.name
            cli_command = prog or self.cli_command or func_name

            tool = ToolDef(
                name=func_name,
                description=parsed_doc.summary or f"Run {func_name}",
                parameters=params,
                return_description=parsed_doc.returns or "Command output",
                source_module=source_module,
                source_function=func_name,
                cli_command=cli_command,
                cli_subcommand=None,
                framework="argparse",
            )
            tools.append(tool)

        return tools
