"""Click CLI for cli2mcp: generate, list, validate commands."""
from __future__ import annotations

import ast
import fnmatch
import json
import shutil
import subprocess
import sys
from pathlib import Path

import click

from cli2mcp.config import load_config
from cli2mcp.generators.mcp_server import generate_module, generate_server_scaffold
from cli2mcp.models import ToolDef
from cli2mcp.scrapers.argparse_scraper import ArgparseScraper
from cli2mcp.scrapers.click_scraper import ClickScraper


def _collect_tools(
    config_path: Path,
) -> tuple[list[ToolDef], object, list[tuple[Path, str]]]:
    """Load config and scrape all tools from source_dirs.

    Returns (tools, config, skipped_files) where skipped_files is a list of
    (path, reason) pairs for files that were not processed (7b).
    """
    config = load_config(config_path)

    tools: list[ToolDef] = []
    skipped: list[tuple[Path, str]] = []  # 7b

    for source_dir in config.source_dirs:
        if not source_dir.exists():
            click.echo(f"Warning: source_dir does not exist: {source_dir}", err=True)
            continue

        py_files = list(source_dir.rglob("*.py"))

        for py_file in py_files:
            # 6a: match against relative path from source_dir, not just filename
            try:
                rel_path = py_file.relative_to(source_dir)
            except ValueError:
                rel_path = Path(py_file.name)
            rel_str = str(rel_path)
            rel_name = py_file.name  # backward-compat for simple name patterns

            # Apply include/exclude patterns against both rel_str and rel_name
            included = any(
                fnmatch.fnmatch(rel_str, pat) or fnmatch.fnmatch(rel_name, pat)
                for pat in config.include_patterns
            )
            excluded = any(
                fnmatch.fnmatch(rel_str, pat) or fnmatch.fnmatch(rel_name, pat)
                for pat in config.exclude_patterns
            )
            if not included or excluded:
                continue

            # Derive dotted module path
            try:
                rel_parts = py_file.relative_to(source_dir.parent).with_suffix("").parts
                source_module = ".".join(rel_parts)
            except ValueError:
                source_module = py_file.stem

            # Read and parse
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError as exc:
                click.echo(f"Warning: skipping {py_file}: {exc}", err=True)
                skipped.append((py_file, f"SyntaxError: {exc}"))  # 7b
                continue
            except OSError:
                continue

            # Try Click first, then argparse
            click_scraper = ClickScraper(source_module=source_module, cli_command=config.entry_point)
            if click_scraper.detect(tree):
                file_tools = click_scraper.scrape_file(py_file)
                tools.extend(file_tools)
            else:
                ap_scraper = ArgparseScraper(source_module=source_module, cli_command=config.entry_point)
                if ap_scraper.detect(tree):
                    file_tools = ap_scraper.scrape_file(py_file)
                    tools.extend(file_tools)

    # 7a: warn on duplicate tool names
    seen_names: dict[str, str] = {}
    for tool in tools:
        if tool.name in seen_names:
            click.echo(
                f"Warning: duplicate tool name '{tool.name}' found in "
                f"'{tool.source_module}' and '{seen_names[tool.name]}'. "
                "The second definition will overwrite the first in FastMCP registration.",
                err=True,
            )
        else:
            seen_names[tool.name] = tool.source_module

    # 6b: apply tool-name include/exclude filters
    if config.include_tools:
        tools = [t for t in tools if t.name in config.include_tools]
    if config.exclude_tools:
        tools = [t for t in tools if t.name not in config.exclude_tools]

    return tools, config, skipped


@click.group()
def main() -> None:
    """cli2mcp — Generate MCP server functions from CLI tools."""


@main.command()
@click.option(
    "--config",
    "config_path",
    default="pyproject.toml",
    show_default=True,
    type=click.Path(exists=False, path_type=Path),
    help="Path to pyproject.toml with [tool.cli2mcp] config.",
)
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(path_type=Path),
    help="Override output file path from config.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print the generated file to stdout instead of writing it.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite the server scaffold even if it already exists.",
)
def generate(config_path: Path, output_path: Path | None, dry_run: bool, force: bool) -> None:
    """Generate an MCP tools module and (once) a server scaffold from CLI tools."""
    try:
        tools, config, skipped = _collect_tools(config_path)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # 6c: validate that the entry_point is on PATH (warn regardless of --dry-run)
    if shutil.which(config.entry_point) is None:
        click.echo(
            f"Warning: entry_point '{config.entry_point}' not found on PATH. "
            "The generated server may fail at runtime.",
            err=True,
        )

    if not tools:
        click.echo("No CLI tools discovered. Check your source_dirs and patterns.", err=True)
        sys.exit(1)

    dest = output_path or config.output_file
    module_stem = dest.stem
    module_content = generate_module(tools, config)
    scaffold_content = generate_server_scaffold(config, module_stem)

    if dry_run:
        click.echo(f"# ===== Generated module: {dest.name} =====")
        click.echo(module_content)
        click.echo(f"# ===== Server scaffold: {config.server_file.name} (only written if not present) =====")
        click.echo(scaffold_content)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(module_content, encoding="utf-8")
        click.echo(f"Generated {dest} with {len(tools)} tool(s).")
        config.server_file.parent.mkdir(parents=True, exist_ok=True)
        if force and config.server_file.exists():
            click.echo(f"Warning: overwriting existing {config.server_file} (--force).", err=True)
            config.server_file.write_text(scaffold_content, encoding="utf-8")
            click.echo(f"Regenerated server scaffold: {config.server_file}")
        elif not config.server_file.exists():
            config.server_file.write_text(scaffold_content, encoding="utf-8")
            click.echo(f"Created server scaffold: {config.server_file}")
        else:
            click.echo(f"Skipped {config.server_file} (already exists).")


@main.command(name="list")
@click.option(
    "--config",
    "config_path",
    default="pyproject.toml",
    show_default=True,
    type=click.Path(exists=False, path_type=Path),
    help="Path to pyproject.toml with [tool.cli2mcp] config.",
)
@click.option(
    "--format",
    "output_format",
    default="text",
    show_default=True,
    type=click.Choice(["text", "json"]),
    help="Output format.",
)
def list_tools(config_path: Path, output_format: str) -> None:
    """List discovered CLI tools without generating the server file."""
    try:
        tools, _, skipped = _collect_tools(config_path)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if not tools and not skipped:
        click.echo("No CLI tools discovered.")
        return

    if output_format == "json":
        data: dict = {"tools": [], "skipped": []}
        for tool in tools:
            # 1d: prefer subcommand_path for accurate command representation
            if tool.subcommand_path:
                cmd = f"{tool.cli_command} {' '.join(tool.subcommand_path)}"
            elif tool.cli_subcommand:
                cmd = f"{tool.cli_command} {tool.cli_subcommand}"
            else:
                cmd = tool.cli_command
            data["tools"].append({
                "name": tool.name,
                "framework": tool.framework,
                "command": cmd,
                "description": tool.description,
                "param_count": len([p for p in tool.parameters if not p.hidden]),
                "params": [
                    {
                        "name": p.name,
                        "type": p.type_annotation,
                        "required": p.required,
                        "default": p.default,
                        "choices": p.choices,
                        "hidden": p.hidden,
                        "mutex_group": p.mutually_exclusive_group,
                    }
                    for p in tool.parameters
                ],
            })
        # 7b: include skipped files in json output
        for path, reason in skipped:
            data["skipped"].append({"path": str(path), "reason": reason})
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"Discovered {len(tools)} tool(s):\n")
        for tool in tools:
            if tool.subcommand_path:
                cmd = f"{tool.cli_command} {' '.join(tool.subcommand_path)}"
            elif tool.cli_subcommand:
                cmd = f"{tool.cli_command} {tool.cli_subcommand}"
            else:
                cmd = tool.cli_command
            visible_params = [p for p in tool.parameters if not p.hidden]
            click.echo(f"  {tool.name} ({tool.framework})")
            click.echo(f"    command : {cmd}")
            click.echo(f"    summary : {tool.description}")
            click.echo(f"    params  : {len(visible_params)}")
            click.echo()

        # 7b: report skipped files
        if skipped:
            click.echo(f"Skipped {len(skipped)} file(s) due to syntax errors:\n")
            for path, reason in skipped:
                click.echo(f"  {path}")
                click.echo(f"    reason: {reason}")
                click.echo()


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
def validate(file: Path) -> None:
    """Import-check a generated MCP server file for syntax errors."""
    result = subprocess.run(
        [sys.executable, "-c", f"import ast; ast.parse(open({repr(str(file))}).read())"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        click.echo(f"{file}: OK (syntax valid)")
    else:
        click.echo(f"{file}: FAILED\n{result.stderr}", err=True)
        sys.exit(1)


_INIT_TEMPLATE = """\
[tool.cli2mcp]
server_name = "{server_name}"
entry_point = "{entry_point}"
source_dirs = ["{source_dir}"]
output_file = "mcp/mcp_tools_generated.py"
server_file = "mcp/mcp_server.py"
include_patterns = ["*.py"]
exclude_patterns = ["test_*", "_*"]
# subprocess_timeout = 30
# capture_stderr = false
# prefer_direct_import = false
# include_tools = []
# exclude_tools = []
"""


@main.command()
@click.option("--server-name", prompt="MCP server name", help="Name of the MCP server.")
@click.option("--entry-point", prompt="CLI entry point (e.g. mycli)", help="The CLI command name.")
@click.option(
    "--source-dir",
    prompt="Source directory containing CLI code",
    default="src",
    show_default=True,
    help="Directory containing CLI source files.",
)
@click.option(
    "--config",
    "config_path",
    default="pyproject.toml",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Path to pyproject.toml to update.",
)
def init(server_name: str, entry_point: str, source_dir: str, config_path: Path) -> None:
    """Scaffold a [tool.cli2mcp] section in pyproject.toml."""
    section = _INIT_TEMPLATE.format(
        server_name=server_name,
        entry_point=entry_point,
        source_dir=source_dir,
    )

    if config_path.exists():
        existing = config_path.read_text(encoding="utf-8")
        if "[tool.cli2mcp]" in existing:
            click.echo(
                f"Error: [tool.cli2mcp] section already exists in {config_path}.", err=True
            )
            sys.exit(1)
        config_path.write_text(existing.rstrip() + "\n\n" + section, encoding="utf-8")
        click.echo(f"Appended [tool.cli2mcp] section to {config_path}.")
    else:
        config_path.write_text(section, encoding="utf-8")
        click.echo(f"Created {config_path} with [tool.cli2mcp] section.")
