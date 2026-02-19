"""Pure-Python NumPy-style docstring parser (no external deps)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParsedDocstring:
    summary: str = ""
    extended: str = ""
    params: dict[str, str] = field(default_factory=dict)
    returns: str = ""


_SECTION_HEADER = re.compile(r"^([A-Za-z][A-Za-z ]*)\s*$")
_UNDERLINE = re.compile(r"^-{3,}\s*$")


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Split lines into named sections based on NumPy-style underline headers."""
    sections: dict[str, list[str]] = {"__preamble__": []}
    current = "__preamble__"
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if next line is an underline (section header detection)
        if i + 1 < len(lines) and _UNDERLINE.match(lines[i + 1]):
            header = line.strip()
            current = header
            sections[current] = []
            i += 2  # skip header and underline
            continue
        sections[current].append(line)
        i += 1
    return sections


def _parse_params_section(lines: list[str]) -> dict[str, str]:
    """Parse a NumPy Parameters section into a dict of name→description."""
    params: dict[str, str] = {}
    current_name: str | None = None
    current_desc: list[str] = []

    for line in lines:
        # param_name : type  or  param_name
        stripped = line.strip()
        if stripped and not line.startswith(" ") and not line.startswith("\t"):
            # Save previous param
            if current_name is not None:
                params[current_name] = " ".join(current_desc).strip()
            # Parse new param header: "name" or "name : type"
            parts = stripped.split(":", 1)
            current_name = parts[0].strip()
            current_desc = []
        elif current_name is not None and stripped:
            current_desc.append(stripped)

    if current_name is not None:
        params[current_name] = " ".join(current_desc).strip()

    return params


def _parse_returns_section(lines: list[str]) -> str:
    """Extract the description from a NumPy Returns section."""
    desc_lines: list[str] = []
    # Skip the first line (the type), collect indented description
    past_type = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not past_type and not line.startswith(" ") and not line.startswith("\t"):
            # This is the type line — skip it
            past_type = True
            continue
        if stripped:
            desc_lines.append(stripped)
    return " ".join(desc_lines).strip()


def parse_numpy_docstring(docstring: str | None) -> ParsedDocstring:
    """Parse a NumPy-style docstring into a ParsedDocstring."""
    if not docstring:
        return ParsedDocstring()

    raw_lines = docstring.expandtabs().splitlines()
    # Determine base indentation from the first non-empty line after the summary
    lines = [line.rstrip() for line in raw_lines]

    # De-indent: find minimum indent of non-empty lines beyond line 0
    non_empty = [l for l in lines[1:] if l.strip()]
    if non_empty:
        min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
        lines = [lines[0]] + [l[min_indent:] if len(l) >= min_indent else l for l in lines[1:]]

    sections = _split_sections(lines)
    preamble = sections.get("__preamble__", [])

    # Summary: first non-empty line of preamble
    summary = ""
    extended_lines: list[str] = []
    past_summary = False
    for line in preamble:
        if not past_summary:
            if line.strip():
                summary = line.strip()
                past_summary = True
        else:
            extended_lines.append(line)

    extended = "\n".join(extended_lines).strip()

    # Parameters section
    params_lines = sections.get("Parameters", [])
    params = _parse_params_section(params_lines)

    # Returns section
    returns_lines = sections.get("Returns", [])
    returns = _parse_returns_section(returns_lines)

    return ParsedDocstring(
        summary=summary,
        extended=extended,
        params=params,
        returns=returns,
    )
