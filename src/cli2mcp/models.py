"""Shared data models for cli2mcp."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParamDef:
    name: str
    cli_flags: list[str]
    type_annotation: str
    default: Any
    required: bool
    description: str
    is_flag: bool = False
    is_multiple: bool = False
    choices: list[str] | None = None
    hidden: bool = False  # 1e: hidden/suppressed options
    mutually_exclusive_group: str | None = None  # 2a: argparse mutually exclusive groups


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: list[ParamDef]
    return_description: str
    source_module: str
    source_function: str
    cli_command: str
    cli_subcommand: str | None
    framework: str
    has_context: bool = False  # 1b: @click.pass_context — skip first ctx arg
    subcommand_path: list[str] | None = None  # 1d: nested groups full CLI path
    return_type: str = "str"  # 3a: source function return type annotation
    timeout: int | None = None  # 3c: per-tool subprocess timeout override
    stdin_param: str | None = None  # 3d: name of param to pipe as stdin
