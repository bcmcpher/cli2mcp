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
