"""AST-based scraper for Click CLI tools."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from cli2mcp.models import ParamDef, ToolDef
from cli2mcp.parsers.docstring import parse_numpy_docstring
from cli2mcp.parsers.type_mapper import ast_node_to_type_str
from cli2mcp.scrapers.base import BaseScraper


def _build_alias_map(tree: ast.AST) -> dict[str, str]:
    """Build a map from local names to their fully-qualified click names.

    Returns e.g. {'click': 'click', 'command': 'click.command', 'option': 'click.option'}
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "click":
                    local = alias.asname or alias.name
                    aliases[local] = "click"
        elif isinstance(node, ast.ImportFrom):
            if node.module == "click":
                for alias in node.names:
                    local = alias.asname or alias.name
                    aliases[local] = f"click.{alias.name}"
    return aliases


def _resolve_decorator(node: ast.expr, aliases: dict[str, str]) -> str | None:
    """Resolve a decorator node to a fully-qualified click name, or None."""
    if isinstance(node, ast.Name):
        return aliases.get(node.id)
    if isinstance(node, ast.Attribute):
        # e.g. click.command or group.command
        if isinstance(node.value, ast.Name):
            prefix = aliases.get(node.value.id, node.value.id)
            return f"{prefix}.{node.attr}"
        return None
    if isinstance(node, ast.Call):
        return _resolve_decorator(node.func, aliases)
    return None


def _is_click_command(resolved: str | None) -> bool:
    return resolved in ("click.command", "click.group") or (
        resolved is not None and resolved.endswith(".command")
    )


def _is_click_option(resolved: str | None) -> bool:
    return resolved == "click.option"


def _is_click_argument(resolved: str | None) -> bool:
    return resolved == "click.argument"


def _get_keyword_value(call: ast.Call, key: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == key:
            return kw.value
    return None


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


def _extract_choices(type_node: ast.expr | None) -> list[str] | None:
    """Extract choices list from click.Choice([...]) type node, or None."""
    if type_node is None:
        return None
    if not isinstance(type_node, ast.Call):
        return None
    func = type_node.func
    # click.Choice or Choice
    is_choice = (
        (isinstance(func, ast.Attribute) and func.attr == "Choice")
        or (isinstance(func, ast.Name) and func.id == "Choice")
    )
    if not is_choice:
        return None
    # First positional arg should be a list/tuple of string constants
    if not type_node.args:
        return None
    arg = type_node.args[0]
    if not isinstance(arg, (ast.List, ast.Tuple)):
        return None
    extracted = [_ast_to_python(elt) for elt in arg.elts if isinstance(elt, ast.Constant)]
    return [str(c) for c in extracted] if extracted else None


def _parse_option_decorator(call: ast.Call) -> ParamDef:
    """Parse a @click.option(...) call into a ParamDef."""
    # Positional string args are the option names/flags
    cli_flags: list[str] = []
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            cli_flags.append(arg.value)

    # Derive param name from longest --flag, stripping dashes
    long_flags = [f for f in cli_flags if f.startswith("--")]
    if long_flags:
        param_name = long_flags[0].lstrip("-").replace("-", "_")
    elif cli_flags:
        param_name = cli_flags[0].lstrip("-").replace("-", "_")
    else:
        param_name = "unknown"

    type_node = _get_keyword_value(call, "type")

    # Check for click.Choice (issue #7)
    choices = _extract_choices(type_node)
    type_annotation = ast_node_to_type_str(type_node)

    default_node = _get_keyword_value(call, "default")
    default = _ast_to_python(default_node)

    required_node = _get_keyword_value(call, "required")
    required_val = _ast_to_python(required_node)
    # If required= not specified, required if no default
    required = bool(required_val) if required_val is not None else (default is None and default_node is None)

    help_node = _get_keyword_value(call, "help")
    description = _ast_to_python(help_node) or ""

    is_flag_node = _get_keyword_value(call, "is_flag")
    is_flag = bool(_ast_to_python(is_flag_node))
    if is_flag:
        type_annotation = "bool"
        default = default if default is not None else False
        required = False

    # Handle flag pairs like '--verbose/--no-verbose'
    if cli_flags and "/" in cli_flags[0]:
        is_flag = True
        type_annotation = "bool"
        default = default if default is not None else False
        required = False
        cli_flags = [cli_flags[0].split("/")[0]]

    # multiple=True (issue #7)
    multiple_node = _get_keyword_value(call, "multiple")
    is_multiple = bool(_ast_to_python(multiple_node))

    # nargs=-1 or nargs>1 → is_multiple (issue #7)
    nargs_node = _get_keyword_value(call, "nargs")
    nargs_val = _ast_to_python(nargs_node)
    if nargs_val is not None and nargs_val != 1:
        is_multiple = True

    if is_multiple:
        type_annotation = f"list[{type_annotation}]"

    return ParamDef(
        name=param_name,
        cli_flags=cli_flags,
        type_annotation=type_annotation,
        default=default,
        required=required,
        description=str(description),
        is_flag=is_flag,
        is_multiple=is_multiple,
        choices=choices,
    )


def _parse_argument_decorator(call: ast.Call) -> ParamDef:
    """Parse a @click.argument(...) call into a ParamDef."""
    cli_flags: list[str] = []
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            cli_flags.append(arg.value)

    param_name = cli_flags[0].lower().replace("-", "_") if cli_flags else "arg"

    type_node = _get_keyword_value(call, "type")
    choices = _extract_choices(type_node)
    type_annotation = ast_node_to_type_str(type_node)

    required_node = _get_keyword_value(call, "required")
    required_val = _ast_to_python(required_node)
    required = required_val if required_val is not None else True

    default_node = _get_keyword_value(call, "default")
    default = _ast_to_python(default_node)

    # nargs=-1 or nargs>1 → is_multiple (issue #7)
    nargs_node = _get_keyword_value(call, "nargs")
    nargs_val = _ast_to_python(nargs_node)
    is_multiple = nargs_val is not None and nargs_val != 1
    if is_multiple:
        type_annotation = f"list[{type_annotation}]"

    return ParamDef(
        name=param_name,
        cli_flags=cli_flags,
        type_annotation=type_annotation,
        default=default,
        required=bool(required),
        description="",
        is_flag=False,
        is_multiple=is_multiple,
        choices=choices,
    )


class ClickScraper(BaseScraper):
    """Scrapes Click-based CLI tools from Python source files using AST analysis."""

    def __init__(self, source_module: str = "", cli_command: str = "") -> None:
        self.source_module = source_module
        self.cli_command = cli_command

    def detect(self, tree: ast.AST) -> bool:
        """Return True if this file imports click."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "click":
                        return True
            elif isinstance(node, ast.ImportFrom):
                if node.module == "click":
                    return True
        return False

    def scrape_file(self, path: Path) -> list[ToolDef]:
        """Parse a Python source file and return Click ToolDef objects."""
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

        aliases = _build_alias_map(tree)
        tools: list[ToolDef] = []

        # Derive module name from path if not provided
        source_module = self.source_module or path.stem

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            decorators = node.decorator_list
            is_command = False
            params: list[ParamDef] = []

            for dec in decorators:
                resolved = _resolve_decorator(dec, aliases)
                if _is_click_command(resolved):
                    is_command = True
                elif _is_click_option(resolved) and isinstance(dec, ast.Call):
                    params.append(_parse_option_decorator(dec))
                elif _is_click_argument(resolved) and isinstance(dec, ast.Call):
                    params.append(_parse_argument_decorator(dec))

            if not is_command:
                continue

            # Decorators are applied bottom-up, so reverse to get natural order
            params.reverse()

            raw_docstring = ast.get_docstring(node)
            parsed_doc = parse_numpy_docstring(raw_docstring)

            # Merge docstring param descriptions into ParamDef
            for param in params:
                if param.name in parsed_doc.params and not param.description:
                    param.description = parsed_doc.params[param.name]

            # Determine CLI subcommand name from decorator name= kwarg if present
            func_name = node.name
            cli_subcommand: str | None = func_name
            tool_name: str = func_name
            for dec in decorators:
                resolved = _resolve_decorator(dec, aliases)
                if _is_click_command(resolved) and isinstance(dec, ast.Call):
                    name_node = _get_keyword_value(dec, "name")
                    if name_node is not None:
                        raw_name = _ast_to_python(name_node)
                        if raw_name:
                            cli_subcommand = raw_name  # keep original for CLI invocation
                            tool_name = raw_name.replace("-", "_")  # sanitize for Python identifier
                    break

            tool = ToolDef(
                name=tool_name,
                description=parsed_doc.summary or f"Run {tool_name}",
                parameters=params,
                return_description=parsed_doc.returns or "Command output",
                source_module=source_module,
                source_function=func_name,
                cli_command=self.cli_command,
                cli_subcommand=cli_subcommand,
                framework="click",
            )
            tools.append(tool)

        return tools
