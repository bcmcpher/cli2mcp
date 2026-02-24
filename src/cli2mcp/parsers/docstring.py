"""Pure-Python docstring parser supporting NumPy, Google, and Sphinx styles."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParsedDocstring:
    summary: str = ""
    extended: str = ""
    params: dict[str, str] = field(default_factory=dict)
    param_types: dict[str, str] = field(default_factory=dict)  # 4b: captured type hints
    returns: str = ""


_SECTION_HEADER = re.compile(r"^([A-Za-z][A-Za-z ]*)\s*$")
_UNDERLINE = re.compile(r"^-{3,}\s*$")

# 4a: Google section headers at column-0 (after de-indent)
_GOOGLE_SECTION = re.compile(
    r"^(Args|Arguments|Parameters|Returns?|Raises?|Note|Notes|Todo|Example|Examples|Attributes):\s*$"
)
# 4a: Sphinx directives
_SPHINX_PARAM = re.compile(r"^:param\s+(\w+):\s*(.*)")
_SPHINX_TYPE = re.compile(r"^:type\s+(\w+):\s*(.*)")
_SPHINX_RETURNS = re.compile(r"^:returns?:\s*(.*)")
_SPHINX_RTYPE = re.compile(r"^:rtype:\s*(.*)")


def _deindent(lines: list[str]) -> list[str]:
    """Remove common leading whitespace from lines[1:] (summary is exempt)."""
    non_empty = [l for l in lines[1:] if l.strip()]
    if not non_empty:
        return lines
    min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
    return [lines[0]] + [l[min_indent:] if len(l) >= min_indent else l for l in lines[1:]]


def _detect_style(docstring: str) -> str:
    """Detect docstring style: 'numpy', 'google', or 'sphinx'."""
    # Sphinx: explicit :param: / :returns: directives
    if re.search(r"^\s*:(param|type|returns?|rtype)\s", docstring, re.MULTILINE):
        return "sphinx"
    # NumPy: underline pattern (--- under section name)
    if re.search(r"^-{3,}\s*$", docstring, re.MULTILINE):
        return "numpy"
    # Google: section headers like "Args:", "Returns:", etc. at column-0
    if re.search(
        r"^\s*(Args|Arguments|Parameters|Returns?|Raises?):\s*$",
        docstring,
        re.MULTILINE,
    ):
        return "google"
    return "numpy"  # default — preserves existing NumPy-first behaviour


# ---------------------------------------------------------------------------
# NumPy style
# ---------------------------------------------------------------------------

def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Split lines into named sections based on NumPy-style underline headers."""
    sections: dict[str, list[str]] = {"__preamble__": []}
    current = "__preamble__"
    i = 0
    while i < len(lines):
        line = lines[i]
        if i + 1 < len(lines) and _UNDERLINE.match(lines[i + 1]):
            header = line.strip()
            current = header
            sections[current] = []
            i += 2
            continue
        sections[current].append(line)
        i += 1
    return sections


def _parse_params_section(lines: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Parse a NumPy Parameters section.

    Returns (params, param_types) where param_types captures the `name : type` hint.
    """
    params: dict[str, str] = {}
    param_types: dict[str, str] = {}
    current_name: str | None = None
    current_desc: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not line.startswith(" ") and not line.startswith("\t"):
            if current_name is not None:
                params[current_name] = " ".join(current_desc).strip()
            # Parse "name" or "name : type"
            parts = stripped.split(":", 1)
            current_name = parts[0].strip()
            if len(parts) > 1:
                type_hint = parts[1].strip()
                if type_hint:
                    param_types[current_name] = type_hint  # 4b
            current_desc = []
        elif current_name is not None and stripped:
            current_desc.append(stripped)

    if current_name is not None:
        params[current_name] = " ".join(current_desc).strip()

    return params, param_types


def _parse_returns_section(lines: list[str]) -> str:
    """Extract the description from a NumPy Returns section."""
    desc_lines: list[str] = []
    past_type = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not past_type and not line.startswith(" ") and not line.startswith("\t"):
            past_type = True
            continue
        if stripped:
            desc_lines.append(stripped)
    return " ".join(desc_lines).strip()


def _parse_numpy_style(docstring: str) -> ParsedDocstring:
    """Parse a NumPy-style docstring."""
    raw_lines = docstring.expandtabs().splitlines()
    lines = [line.rstrip() for line in raw_lines]
    lines = _deindent(lines)

    sections = _split_sections(lines)
    preamble = sections.get("__preamble__", [])

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
    params_lines = sections.get("Parameters", [])
    params, param_types = _parse_params_section(params_lines)
    returns_lines = sections.get("Returns", [])
    returns = _parse_returns_section(returns_lines)

    return ParsedDocstring(
        summary=summary,
        extended=extended,
        params=params,
        param_types=param_types,
        returns=returns,
    )


# ---------------------------------------------------------------------------
# 4a: Google style
# ---------------------------------------------------------------------------

def _parse_google_style(docstring: str) -> ParsedDocstring:
    """Parse a Google-style docstring."""
    raw_lines = docstring.expandtabs().splitlines()
    lines = [line.rstrip() for line in raw_lines]
    lines = _deindent(lines)

    summary = lines[0].strip() if lines else ""
    params: dict[str, str] = {}
    param_types: dict[str, str] = {}
    returns = ""
    extended_lines: list[str] = []

    current_section = "__preamble__"
    # Track current param for multi-line description continuation
    current_param: str | None = None
    current_param_desc: list[str] = []

    def _flush_param() -> None:
        nonlocal current_param, current_param_desc
        if current_param is not None:
            params[current_param] = " ".join(current_param_desc).strip()
        current_param = None
        current_param_desc = []

    i = 1
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Section header detection (at column-0 after de-indent)
        m = _GOOGLE_SECTION.match(line)
        if m:
            _flush_param()
            current_section = m.group(1).lower()
            i += 1
            continue

        if current_section in ("args", "arguments", "parameters"):
            if stripped and (line.startswith("    ") or line.startswith("\t")):
                # Try to parse "name (type): description" or "name: description"
                m2 = re.match(r"^(\w+)\s*(?:\(([^)]*)\))?\s*:\s*(.*)", stripped)
                if m2:
                    _flush_param()
                    current_param = m2.group(1)
                    ptype = m2.group(2)
                    pdesc = m2.group(3).strip()
                    if ptype:
                        param_types[current_param] = ptype.strip()
                    current_param_desc = [pdesc] if pdesc else []
                elif current_param is not None and stripped:
                    # Continuation of previous param description
                    current_param_desc.append(stripped)
            else:
                _flush_param()

        elif current_section in ("returns", "return"):
            if stripped:
                returns = stripped if not returns else returns + " " + stripped

        elif current_section == "__preamble__":
            extended_lines.append(line)

        i += 1

    _flush_param()
    extended = "\n".join(extended_lines).strip()

    return ParsedDocstring(
        summary=summary,
        extended=extended,
        params=params,
        param_types=param_types,
        returns=returns,
    )


# ---------------------------------------------------------------------------
# 4a: Sphinx style
# ---------------------------------------------------------------------------

def _parse_sphinx_style(docstring: str) -> ParsedDocstring:
    """Parse a Sphinx-style docstring."""
    raw_lines = docstring.expandtabs().splitlines()
    lines = [line.rstrip() for line in raw_lines]
    lines = _deindent(lines)

    summary = lines[0].strip() if lines else ""
    params: dict[str, str] = {}
    param_types: dict[str, str] = {}
    returns = ""
    extended_lines: list[str] = []

    for line in lines[1:]:
        stripped = line.strip()
        m = _SPHINX_PARAM.match(stripped)
        if m:
            params[m.group(1)] = m.group(2).strip()
            continue
        m = _SPHINX_TYPE.match(stripped)
        if m:
            param_types[m.group(1)] = m.group(2).strip()  # 4b
            continue
        m = _SPHINX_RETURNS.match(stripped)
        if m:
            returns = m.group(1).strip()
            continue
        if _SPHINX_RTYPE.match(stripped):
            continue  # skip :rtype: lines
        if stripped and not stripped.startswith(":"):
            extended_lines.append(stripped)

    extended = "\n".join(l for l in extended_lines if l).strip()

    return ParsedDocstring(
        summary=summary,
        extended=extended,
        params=params,
        param_types=param_types,
        returns=returns,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_numpy_docstring(docstring: str | None) -> ParsedDocstring:
    """Parse a docstring (NumPy, Google, or Sphinx style) into a ParsedDocstring.

    Style is auto-detected:
    - NumPy: section names underlined with dashes (``---``)
    - Google: section names followed by a colon (``Args:``)
    - Sphinx: ``:param name:`` directives
    """
    if not docstring:
        return ParsedDocstring()
    style = _detect_style(docstring)
    if style == "google":
        return _parse_google_style(docstring)
    if style == "sphinx":
        return _parse_sphinx_style(docstring)
    return _parse_numpy_style(docstring)
