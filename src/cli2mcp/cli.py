"""Click CLI for cli2mcp: generate, list, validate commands."""
from __future__ import annotations

import ast
import fnmatch
import subprocess
import sys
from pathlib import Path

import click

from cli2mcp.config import load_config
from cli2mcp.generators.mcp_server import generate_server
from cli2mcp.models import ToolDef
from cli2mcp.scrapers.argparse_scraper import ArgparseScraper
from cli2mcp.scrapers.click_scraper import ClickScraper


def _collect_tools(config_path: Path) -> tuple[list[ToolDef], object]:
    """Load config and scrape all tools from source_dirs."""
    config = load_config(config_path)

    tools: list[ToolDef] = []

    for source_dir in config.source_dirs:
        if not source_dir.exists():
            click.echo(f"Warning: source_dir does not exist: {source_dir}", err=True)
            continue

        py_files = list(source_dir.rglob("*.py"))

        for py_file in py_files:
            rel_name = py_file.name

            # Apply include/exclude patterns
            included = any(fnmatch.fnmatch(rel_name, pat) for pat in config.include_patterns)
            excluded = any(fnmatch.fnmatch(rel_name, pat) for pat in config.exclude_patterns)
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
            except (SyntaxError, OSError):
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

    return tools, config


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
def generate(config_path: Path, output_path: Path | None, dry_run: bool) -> None:
    """Generate an MCP server file from CLI tools."""
    try:
        tools, config = _collect_tools(config_path)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if not tools:
        click.echo("No CLI tools discovered. Check your source_dirs and patterns.", err=True)
        sys.exit(1)

    content = generate_server(tools, config)

    dest = output_path or config.output_file
    if dry_run:
        click.echo(content)
    else:
        dest.write_text(content, encoding="utf-8")
        click.echo(f"Generated {dest} with {len(tools)} tool(s).")


@main.command(name="list")
@click.option(
    "--config",
    "config_path",
    default="pyproject.toml",
    show_default=True,
    type=click.Path(exists=False, path_type=Path),
    help="Path to pyproject.toml with [tool.cli2mcp] config.",
)
def list_tools(config_path: Path) -> None:
    """List discovered CLI tools without generating the server file."""
    try:
        tools, _ = _collect_tools(config_path)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if not tools:
        click.echo("No CLI tools discovered.")
        return

    click.echo(f"Discovered {len(tools)} tool(s):\n")
    for tool in tools:
        cmd = tool.cli_command
        if tool.cli_subcommand:
            cmd = f"{cmd} {tool.cli_subcommand}"
        click.echo(f"  {tool.name} ({tool.framework})")
        click.echo(f"    command : {cmd}")
        click.echo(f"    summary : {tool.description}")
        click.echo(f"    params  : {len(tool.parameters)}")
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
