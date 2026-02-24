"""AST-based scraper for argparse CLI tools."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from cli2mcp.models import ParamDef, ToolDef
from cli2mcp.parsers.docstring import parse_numpy_docstring
from cli2mcp.parsers.type_mapper import ast_node_to_type_str
from cli2mcp.scrapers.base import BaseScraper

# 2c: extended action lookup including all stdlib actions
_ACTION_MAP: dict[str, tuple[str, bool, bool]] = {
    # action_string → (type_annotation, is_flag, is_multiple)
    "store_true": ("bool", True, False),
    "store_false": ("bool", True, False),
    "store_const": ("str", False, False),
    "append": ("str", False, True),
    "append_const": ("str", False, True),
    "count": ("int", False, False),  # each --verbose increments an int
    "extend": ("str", False, True),
}


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
        if stmt.targets and isinstance(stmt.targets[0], ast.Name):
            var_name = stmt.targets[0].id
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


def _find_mutually_exclusive_groups(
    func_body: list[ast.stmt], parser_var: str
) -> dict[str, str]:
    """2a: Find add_mutually_exclusive_group() calls and map var names to group IDs.

    Returns {group_var_name: group_id_string}.
    """
    groups: dict[str, str] = {}
    group_counter = 0
    for stmt in func_body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Assign):
                continue
            if not isinstance(node.value, ast.Call):
                continue
            call = node.value
            if not (
                isinstance(call.func, ast.Attribute)
                and call.func.attr == "add_mutually_exclusive_group"
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == parser_var
            ):
                continue
            if node.targets and isinstance(node.targets[0], ast.Name):
                group_var = node.targets[0].id
                group_counter += 1
                groups[group_var] = f"mutex_group_{group_counter}"
    return groups


def _find_add_argument_calls_with_groups(
    func_body: list[ast.stmt],
    parser_var: str,
    mutex_groups: dict[str, str],
) -> list[tuple[ast.Call, str | None]]:
    """Find add_argument calls, annotating each with its mutex group ID (or None)."""
    results: list[tuple[ast.Call, str | None]] = []
    all_vars = {parser_var: None} | mutex_groups  # var → group_id or None for main parser
    for stmt in func_body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "add_argument"
                and isinstance(func.value, ast.Name)
            ):
                continue
            obj_name = func.value.id
            if obj_name in all_vars:
                results.append((node, all_vars[obj_name]))
    return results


def _parse_add_argument(call: ast.Call, mutex_group: str | None = None) -> ParamDef | None:
    """Parse an add_argument(...) call into a ParamDef."""
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
        raw_dest = str(_ast_to_python(dest_node) or "")
        param_name = raw_dest.replace("-", "_")
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
            # 2d: handle argparse.FileType, lambda, and other callables
            type_node = kw.value
            if isinstance(type_node, ast.Lambda):
                # 2d: lambda type callable → str (CLI always passes strings)
                type_annotation = "str"
            else:
                type_annotation = ast_node_to_type_str(type_node)
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
        required = is_positional

    # action= handling
    is_flag = False
    is_multiple = False
    for kw in call.keywords:
        if kw.arg == "action":
            action_val = _ast_to_python(kw.value)
            if isinstance(action_val, str) and action_val in _ACTION_MAP:
                mapped_type, mapped_is_flag, mapped_is_multiple = _ACTION_MAP[action_val]
                type_annotation = mapped_type
                is_flag = mapped_is_flag
                is_multiple = mapped_is_multiple
                if is_flag:
                    default = False if default is None else default
                    required = False
            elif action_val is not None:
                # 2c: unknown custom action → fall back gracefully
                pass  # keep existing type_annotation; generator will emit a TODO comment
            break

    # nargs='+' or nargs='*' or nargs=N>1 → is_multiple
    for kw in call.keywords:
        if kw.arg == "nargs":
            nargs_val = _ast_to_python(kw.value)
            if nargs_val in ("+", "*") or (isinstance(nargs_val, int) and nargs_val > 1):
                is_multiple = True
            break

    # choices=
    choices: list[str] | None = None
    for kw in call.keywords:
        if kw.arg == "choices":
            if isinstance(kw.value, (ast.List, ast.Tuple)):
                extracted = [
                    _ast_to_python(elt)
                    for elt in kw.value.elts
                    if isinstance(elt, ast.Constant)
                ]
                if extracted:
                    choices = [str(c) for c in extracted]
            break

    if is_multiple:
        type_annotation = f"list[{type_annotation}]"

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
        is_multiple=is_multiple,
        choices=choices,
        mutually_exclusive_group=mutex_group,  # 2a
    )


def _find_subparser_var(func_body: list[ast.stmt], parser_var: str) -> str | None:
    """Find the variable assigned from <parser_var>.add_subparsers()."""
    for stmt in func_body:
        if not isinstance(stmt, ast.Assign):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        call = stmt.value
        if not (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "add_subparsers"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == parser_var
        ):
            continue
        if stmt.targets and isinstance(stmt.targets[0], ast.Name):
            return stmt.targets[0].id
    return None


def _find_subparser_add_parser_calls(
    func_body: list[ast.stmt], subparser_var: str
) -> list[tuple[str, ast.Call]]:
    """Find <subparser_var>.add_parser(name, ...) calls.

    Returns list of (subcommand_name, add_parser_call).
    """
    results: list[tuple[str, ast.Call]] = []
    for stmt in func_body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "add_parser"
                and isinstance(func.value, ast.Name)
                and func.value.id == subparser_var
            ):
                continue
            if node.args and isinstance(node.args[0], ast.Constant):
                name = str(node.args[0].value)
                results.append((name, node))
    return results


def _find_subparser_assignments(
    func_body: list[ast.stmt], subparser_var: str
) -> dict[str, str]:
    """Find variable names assigned from add_parser() calls.

    Returns {var_name: subcommand_name}.
    """
    assignments: dict[str, str] = {}
    for stmt in func_body:
        if not isinstance(stmt, ast.Assign):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        call = stmt.value
        if not (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "add_parser"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == subparser_var
        ):
            continue
        if (
            stmt.targets
            and isinstance(stmt.targets[0], ast.Name)
            and call.args
            and isinstance(call.args[0], ast.Constant)
        ):
            var_name = stmt.targets[0].id
            subcommand_name = str(call.args[0].value)
            assignments[var_name] = subcommand_name
    return assignments


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
            # 1c: also handle async def functions
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            parser_var, prog = _find_parser_var(node.body)
            if parser_var is None:
                continue

            func_name = node.name
            cli_command = prog or self.cli_command or func_name
            raw_docstring = ast.get_docstring(node)
            parsed_doc = parse_numpy_docstring(raw_docstring)

            # 3a: capture return type annotation
            return_type = "str"
            if node.returns is not None:
                ann = ast_node_to_type_str(node.returns)
                if ann not in ("None", "str"):
                    return_type = ann

            # 2a: find mutually exclusive groups
            mutex_groups = _find_mutually_exclusive_groups(node.body, parser_var)

            # Check for subparsers
            subparser_var = _find_subparser_var(node.body, parser_var)
            if subparser_var is not None:
                # Multi-subcommand pattern: one ToolDef per add_parser() call
                sub_assignments = _find_subparser_assignments(node.body, subparser_var)
                for sub_var, sub_name in sub_assignments.items():
                    # 2a: include mutex groups for sub-parser args too
                    sub_mutex = _find_mutually_exclusive_groups(node.body, sub_var)
                    annotated = _find_add_argument_calls_with_groups(
                        node.body, sub_var, sub_mutex
                    )
                    params: list[ParamDef] = []
                    for call, group_id in annotated:
                        param = _parse_add_argument(call, group_id)
                        if param is not None:
                            params.append(param)

                    for param in params:
                        if param.name in parsed_doc.params and not param.description:
                            param.description = parsed_doc.params[param.name]
                        if (
                            param.type_annotation in ("str", "Any")
                            and param.name in parsed_doc.param_types
                        ):
                            param.type_annotation = parsed_doc.param_types[param.name]

                    tool_name = sub_name.replace("-", "_")
                    tool = ToolDef(
                        name=tool_name,
                        description=parsed_doc.summary or f"Run {sub_name}",
                        parameters=params,
                        return_description=parsed_doc.returns or "Command output",
                        source_module=source_module,
                        source_function=func_name,
                        cli_command=cli_command,
                        cli_subcommand=sub_name,
                        framework="argparse",
                        return_type=return_type,
                    )
                    tools.append(tool)
                continue

            # Single-parser pattern — 2a: use annotated calls
            annotated_calls = _find_add_argument_calls_with_groups(
                node.body, parser_var, mutex_groups
            )
            if not annotated_calls:
                continue

            params = []
            for call, group_id in annotated_calls:
                param = _parse_add_argument(call, group_id)
                if param is not None:
                    params.append(param)

            for param in params:
                if param.name in parsed_doc.params and not param.description:
                    param.description = parsed_doc.params[param.name]
                if (
                    param.type_annotation in ("str", "Any")
                    and param.name in parsed_doc.param_types
                ):
                    param.type_annotation = parsed_doc.param_types[param.name]

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
                return_type=return_type,
            )
            tools.append(tool)

        return tools
