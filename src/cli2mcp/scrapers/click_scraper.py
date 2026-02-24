"""AST-based scraper for Click CLI tools."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from cli2mcp.models import ParamDef, ToolDef
from cli2mcp.parsers.docstring import parse_numpy_docstring
from cli2mcp.parsers.type_mapper import ast_node_to_type_str
from cli2mcp.scrapers.base import BaseScraper

# Modules that are API-compatible with click (drop-in replacements)
_CLICK_MODULES = frozenset({"click", "rich_click"})


def _build_alias_map(tree: ast.AST) -> dict[str, str]:
    """Build a map from local names to their fully-qualified click names.

    Returns e.g. {'click': 'click', 'command': 'click.command', 'option': 'click.option'}
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _CLICK_MODULES:
                    local = alias.asname or alias.name
                    aliases[local] = "click"
        elif isinstance(node, ast.ImportFrom):
            if node.module in _CLICK_MODULES:
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


def _is_click_group(resolved: str | None) -> bool:
    return resolved == "click.group" or (
        resolved is not None and resolved.endswith(".group")
    )


def _is_click_option(resolved: str | None) -> bool:
    return resolved == "click.option"


def _is_click_argument(resolved: str | None) -> bool:
    return resolved == "click.argument"


def _is_pass_context(resolved: str | None) -> bool:
    """Return True for @click.pass_context or @click.pass_obj."""
    return resolved in ("click.pass_context", "click.pass_obj")


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
    is_choice = (
        (isinstance(func, ast.Attribute) and func.attr == "Choice")
        or (isinstance(func, ast.Name) and func.id == "Choice")
    )
    if not is_choice:
        return None
    if not type_node.args:
        return None
    arg = type_node.args[0]
    if not isinstance(arg, (ast.List, ast.Tuple)):
        return None
    extracted = [_ast_to_python(elt) for elt in arg.elts if isinstance(elt, ast.Constant)]
    return [str(c) for c in extracted] if extracted else None


def _parse_option_decorator(call: ast.Call) -> ParamDef:
    """Parse a @click.option(...) call into a ParamDef."""
    cli_flags: list[str] = []
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            cli_flags.append(arg.value)

    long_flags = [f for f in cli_flags if f.startswith("--")]
    if long_flags:
        param_name = long_flags[0].lstrip("-").replace("-", "_")
    elif cli_flags:
        param_name = cli_flags[0].lstrip("-").replace("-", "_")
    else:
        param_name = "unknown"

    type_node = _get_keyword_value(call, "type")

    # 1e: check hidden= keyword
    hidden_node = _get_keyword_value(call, "hidden")
    hidden = bool(_ast_to_python(hidden_node))

    # 1e: check help=click.SUPPRESS
    help_node = _get_keyword_value(call, "help")
    help_val = _ast_to_python(help_node)
    if not hidden and isinstance(help_node, ast.Attribute) and help_node.attr == "SUPPRESS":
        hidden = True

    choices = _extract_choices(type_node)
    type_annotation = ast_node_to_type_str(type_node)

    default_node = _get_keyword_value(call, "default")
    default = _ast_to_python(default_node)

    required_node = _get_keyword_value(call, "required")
    required_val = _ast_to_python(required_node)
    required = bool(required_val) if required_val is not None else (default is None and default_node is None)

    description = str(help_val) if help_val and not hidden else ""

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

    multiple_node = _get_keyword_value(call, "multiple")
    is_multiple = bool(_ast_to_python(multiple_node))

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
        description=description,
        is_flag=is_flag,
        is_multiple=is_multiple,
        choices=choices,
        hidden=hidden,
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


def _build_wrapper_map(
    tree: ast.AST, aliases: dict[str, str], command_names: set[str]
) -> dict[str, list[ParamDef]]:
    """1a: Find decorator-factory functions and map their names to the params they add.

    A wrapper function is one that:
    - Is not itself a Click command
    - Has at least one parameter (the wrapped function)
    - Contains click.option/click.argument calls in its body
    """
    wrapper_map: dict[str, list[ParamDef]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name in command_names:
            continue  # skip command functions themselves
        if not node.args.args and not node.args.posonlyargs:
            continue  # must accept at least one argument

        params: list[ParamDef] = []
        for stmt in node.body:
            for child in ast.walk(stmt):
                if not isinstance(child, ast.Call):
                    continue
                resolved = _resolve_decorator(child, aliases)
                if _is_click_option(resolved):
                    # Must have at least one string positional arg (the flag name)
                    if any(
                        isinstance(a, ast.Constant) and isinstance(a.value, str)
                        for a in child.args
                    ):
                        try:
                            param = _parse_option_decorator(child)
                            if not param.hidden:
                                params.append(param)
                        except Exception:
                            pass
                elif _is_click_argument(resolved):
                    if any(
                        isinstance(a, ast.Constant) and isinstance(a.value, str)
                        for a in child.args
                    ):
                        try:
                            params.append(_parse_argument_decorator(child))
                        except Exception:
                            pass

        if params:
            wrapper_map[node.name] = params

    return wrapper_map


def _build_subcommand_tree(
    tree: ast.AST, aliases: dict[str, str]
) -> dict[str, list[str]]:
    """1d: Build the full CLI subcommand path for each command/group function.

    Returns {func_name: [sub1, sub2, ..., leaf]} where the list is the path
    after the root entry point (e.g. {"migrate": ["db", "migrate"]}).
    """
    # Maps func_name → (registered_cli_name, parent_object_name | None)
    cmd_info: dict[str, tuple[str, str | None]] = {}
    is_group_fn: dict[str, bool] = {}

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        func_name = node.name
        for dec in node.decorator_list:
            resolved = _resolve_decorator(dec, aliases)
            if not _is_click_command(resolved):
                continue

            # Get registered CLI name
            reg_name = func_name
            if isinstance(dec, ast.Call):
                name_node = _get_keyword_value(dec, "name")
                if name_node:
                    n = _ast_to_python(name_node)
                    if n:
                        reg_name = str(n)

            # Determine parent: the object the decorator is called on
            dec_node = dec.func if isinstance(dec, ast.Call) else dec
            parent_obj: str | None = None
            if isinstance(dec_node, ast.Attribute) and isinstance(dec_node.value, ast.Name):
                obj_name = dec_node.value.id
                # If obj_name resolves to "click" in aliases, it's the root
                if aliases.get(obj_name) != "click":
                    parent_obj = obj_name  # reference to a group function

            cmd_info[func_name] = (reg_name, parent_obj)
            is_group_fn[func_name] = _is_click_group(resolved)
            break

    def get_path(func_name: str, visited: set[str]) -> list[str]:
        if func_name in visited or func_name not in cmd_info:
            return [func_name]  # standalone command
        visited.add(func_name)
        reg_name, parent_obj = cmd_info[func_name]
        if parent_obj is None:
            # Root element
            if is_group_fn.get(func_name, False):
                return []  # root group → not part of subcommand path
            return [reg_name]  # standalone command
        parent_path = get_path(parent_obj, visited)
        return parent_path + [reg_name]

    return {fn: get_path(fn, set()) for fn in cmd_info}


class ClickScraper(BaseScraper):
    """Scrapes Click-based CLI tools from Python source files using AST analysis."""

    def __init__(self, source_module: str = "", cli_command: str = "") -> None:
        self.source_module = source_module
        self.cli_command = cli_command

    def detect(self, tree: ast.AST) -> bool:
        """Return True if this file imports click or a click-compatible module."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in _CLICK_MODULES:
                        return True
            elif isinstance(node, ast.ImportFrom):
                if node.module in _CLICK_MODULES:
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
        source_module = self.source_module or path.stem

        # 1a: First pass — collect command function names for wrapper-map filtering
        command_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if _is_click_command(_resolve_decorator(dec, aliases)):
                        command_names.add(node.name)
                        break

        # 1a: Build decorator-wrapper map
        wrapper_map = _build_wrapper_map(tree, aliases, command_names)

        # 1d: Build subcommand path tree
        subcommand_paths = _build_subcommand_tree(tree, aliases)

        tools: list[ToolDef] = []

        for node in ast.walk(tree):
            # 1c: also handle async def commands
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            decorators = node.decorator_list
            is_command = False
            params: list[ParamDef] = []
            has_context = False  # 1b

            for dec in decorators:
                resolved = _resolve_decorator(dec, aliases)
                if _is_click_command(resolved):
                    is_command = True
                elif _is_pass_context(resolved):
                    has_context = True  # 1b
                elif _is_click_option(resolved) and isinstance(dec, ast.Call):
                    param = _parse_option_decorator(dec)
                    if not param.hidden:  # 1e: skip hidden options
                        params.append(param)
                elif _is_click_argument(resolved) and isinstance(dec, ast.Call):
                    params.append(_parse_argument_decorator(dec))
                else:
                    # 1a: check if this is a known decorator wrapper
                    dec_name: str | None = None
                    if isinstance(dec, ast.Name):
                        dec_name = dec.id
                    elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                        dec_name = dec.func.id
                    if dec_name and dec_name in wrapper_map:
                        params.extend(wrapper_map[dec_name])

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
                # 4b: use docstring type if annotation is a fallback
                if (
                    param.type_annotation in ("str", "Any")
                    and param.name in parsed_doc.param_types
                ):
                    param.type_annotation = parsed_doc.param_types[param.name]

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
                            cli_subcommand = raw_name
                            tool_name = raw_name.replace("-", "_")
                    break

            # 3a: capture return type annotation from function signature
            return_type = "str"
            if node.returns is not None:
                from cli2mcp.parsers.type_mapper import ast_node_to_type_str as _t
                ann = _t(node.returns)
                if ann not in ("None", "str"):
                    return_type = ann

            # 1d: full subcommand path
            subcommand_path = subcommand_paths.get(func_name)

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
                has_context=has_context,
                subcommand_path=subcommand_path,
                return_type=return_type,
            )
            tools.append(tool)

        return tools
