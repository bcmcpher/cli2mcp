"""Tests for Phase 3 improvements: G (agent guidance), H (Typer scraper), I (validate), J (inspect)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli2mcp.cli import main
from cli2mcp.config import Config
from cli2mcp.generators.mcp_server import generate_module, _agent_guidance
from cli2mcp.models import ParamDef, ToolDef
from cli2mcp.scrapers.typer_scraper import TyperScraper

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TYPER_FIXTURE = FIXTURE_DIR / "sample_typer_cli.py"


@pytest.fixture
def base_config():
    return Config(
        server_name="Test Server",
        entry_point="mytool",
        source_dirs=[Path("src")],
        output_file=Path("mcp_tools_generated.py"),
        server_file=Path("mcp_server.py"),
    )


def _make_tool(**kwargs) -> ToolDef:
    defaults = dict(
        name="greet",
        description="Greet someone.",
        parameters=[],
        return_description="Output.",
        source_module="pkg.cli",
        source_function="greet",
        cli_command="mytool",
        cli_subcommand="greet",
        framework="click",
    )
    defaults.update(kwargs)
    return ToolDef(**defaults)


# ---------------------------------------------------------------------------
# G: Agent-guidance docstrings
# ---------------------------------------------------------------------------


class TestAgentGuidance:
    def test_read_prefix_returns_guidance(self):
        for prefix in ("list", "get", "show", "describe", "read", "fetch", "search", "find"):
            guidance = _agent_guidance(f"{prefix}_items")
            assert "retrieve" in guidance or "query" in guidance

    def test_destructive_prefix_returns_guidance(self):
        for prefix in ("delete", "remove", "drop", "destroy", "purge", "clear", "reset", "wipe"):
            guidance = _agent_guidance(f"{prefix}_thing")
            assert "irreversible" in guidance or "remove" in guidance or "destroy" in guidance or "permanently" in guidance

    def test_neutral_name_returns_empty(self):
        assert _agent_guidance("process_data") == ""
        assert _agent_guidance("run_job") == ""

    def test_read_tool_includes_notes_in_docstring(self, base_config):
        tool = _make_tool(name="list_users")
        output = generate_module([tool], base_config)
        assert "Notes" in output
        assert "retrieve" in output or "query" in output

    def test_destructive_tool_includes_notes_in_docstring(self, base_config):
        tool = _make_tool(name="delete_user")
        output = generate_module([tool], base_config)
        assert "Notes" in output
        assert "irreversible" in output

    def test_neutral_tool_has_no_notes_section(self, base_config):
        tool = _make_tool(name="process_data")
        output = generate_module([tool], base_config)
        # "Notes" section should not appear for neutral tools
        # (it may appear in comments though — check specifically in docstring region)
        # The docstring ends before the body, so just check no Notes header
        assert "    Notes\n    -----" not in output


# ---------------------------------------------------------------------------
# H: Typer scraper
# ---------------------------------------------------------------------------


class TestTyperScraperDetect:
    def test_detects_typer_import(self):
        import ast
        tree = ast.parse("import typer\napp = typer.Typer()")
        scraper = TyperScraper()
        assert scraper.detect(tree) is True

    def test_does_not_detect_non_typer(self):
        import ast
        tree = ast.parse("import click\n@click.command()\ndef foo(): pass")
        scraper = TyperScraper()
        assert scraper.detect(tree) is False


class TestTyperScraperScrapeFile:
    def test_scrapes_commands_from_fixture(self):
        scraper = TyperScraper(source_module="sample_typer_cli", cli_command="mytool")
        tools = scraper.scrape_file(TYPER_FIXTURE)
        assert len(tools) >= 3

    def test_tool_framework_is_typer(self):
        scraper = TyperScraper(source_module="sample_typer_cli", cli_command="mytool")
        tools = scraper.scrape_file(TYPER_FIXTURE)
        for tool in tools:
            assert tool.framework == "typer"

    def test_greet_tool_has_name_and_description(self):
        scraper = TyperScraper(source_module="sample_typer_cli", cli_command="mytool")
        tools = {t.name: t for t in scraper.scrape_file(TYPER_FIXTURE)}
        assert "greet" in tools
        greet = tools["greet"]
        assert "Greet" in greet.description

    def test_greet_tool_params(self):
        scraper = TyperScraper(source_module="sample_typer_cli", cli_command="mytool")
        tools = {t.name: t for t in scraper.scrape_file(TYPER_FIXTURE)}
        greet = tools["greet"]
        param_names = [p.name for p in greet.parameters]
        assert "name" in param_names
        assert "count" in param_names
        assert "loud" in param_names

    def test_greet_name_is_required_positional(self):
        scraper = TyperScraper(source_module="sample_typer_cli", cli_command="mytool")
        tools = {t.name: t for t in scraper.scrape_file(TYPER_FIXTURE)}
        name_param = next(p for p in tools["greet"].parameters if p.name == "name")
        assert name_param.required is True
        assert name_param.type_annotation == "str"

    def test_greet_count_is_optional_option(self):
        scraper = TyperScraper(source_module="sample_typer_cli", cli_command="mytool")
        tools = {t.name: t for t in scraper.scrape_file(TYPER_FIXTURE)}
        count_param = next(p for p in tools["greet"].parameters if p.name == "count")
        assert count_param.required is False
        assert count_param.default == 1
        assert count_param.type_annotation == "int"

    def test_loud_is_bool_flag(self):
        scraper = TyperScraper(source_module="sample_typer_cli", cli_command="mytool")
        tools = {t.name: t for t in scraper.scrape_file(TYPER_FIXTURE)}
        loud_param = next(p for p in tools["greet"].parameters if p.name == "loud")
        assert loud_param.is_flag is True
        assert loud_param.type_annotation == "bool"

    def test_command_name_override(self):
        scraper = TyperScraper(source_module="sample_typer_cli", cli_command="mytool")
        tools = {t.name: t for t in scraper.scrape_file(TYPER_FIXTURE)}
        # @app.command(name="get-config") should be scraped as "get_config"
        assert "get_config" in tools

    def test_list_users_tool(self):
        scraper = TyperScraper(source_module="sample_typer_cli", cli_command="mytool")
        tools = {t.name: t for t in scraper.scrape_file(TYPER_FIXTURE)}
        assert "list_users" in tools

    def test_option_help_becomes_description(self):
        scraper = TyperScraper(source_module="sample_typer_cli", cli_command="mytool")
        tools = {t.name: t for t in scraper.scrape_file(TYPER_FIXTURE)}
        count_param = next(p for p in tools["greet"].parameters if p.name == "count")
        assert "Number of greetings" in count_param.description


class TestTyperScraperViaCliGenerate:
    """Integration: generate --dry-run with a Typer fixture."""

    def _typer_config(self, tmp_path):
        config = tmp_path / "pyproject.toml"
        config.write_text(
            f"""\
[tool.cli2mcp]
server_name = "Test Server"
entry_point = "mytool"
source_dirs = ["{FIXTURE_DIR}"]
output_file = "mcp/mcp_tools_generated.py"
server_file = "mcp/mcp_server.py"
include_patterns = ["sample_typer_cli.py"]
exclude_patterns = []
""",
            encoding="utf-8",
        )
        return config

    def test_generate_dry_run_includes_typer_tools(self, tmp_path):
        config = self._typer_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["generate", "--config", str(config), "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "greet" in result.output

    def test_list_shows_typer_framework(self, tmp_path):
        config = self._typer_config(tmp_path)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["list", "--config", str(config), "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        typer_tools = [t for t in data["tools"] if t["framework"] == "typer"]
        assert len(typer_tools) >= 3


# ---------------------------------------------------------------------------
# I: validate --import-check
# ---------------------------------------------------------------------------


class TestValidateImportCheck:
    def _write_valid_module(self, tmp_path: Path) -> Path:
        """Write a minimal valid generated module."""
        f = tmp_path / "mcp_tools_generated.py"
        f.write_text(
            """\
from __future__ import annotations
import asyncio
from typing import Any, Literal
from pydantic import BaseModel, Field


def _register_tools(mcp) -> None:
    pass
""",
            encoding="utf-8",
        )
        return f

    def _write_invalid_syntax(self, tmp_path: Path) -> Path:
        f = tmp_path / "bad.py"
        f.write_text("def foo(\n", encoding="utf-8")
        return f

    def test_valid_file_passes_syntax_check(self, tmp_path):
        f = self._write_valid_module(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["validate", str(f)])
        assert result.exit_code == 0
        assert "syntax valid" in result.output

    def test_invalid_syntax_fails(self, tmp_path):
        f = self._write_invalid_syntax(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["validate", str(f)])
        assert result.exit_code == 1

    def test_import_check_passes_for_valid_module(self, tmp_path):
        f = self._write_valid_module(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["validate", "--import-check", str(f)])
        assert result.exit_code == 0
        assert "import valid" in result.output

    def test_import_check_fails_for_missing_import(self, tmp_path):
        f = tmp_path / "bad_import.py"
        f.write_text("from nonexistent_pkg_xyz import something\n", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(main, ["validate", "--import-check", str(f)])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# J: inspect command
# ---------------------------------------------------------------------------


class TestInspectCommand:
    def test_inspect_fails_when_npx_not_found(self, tmp_path, monkeypatch):
        """When npx is not on PATH, inspect should exit with error."""
        import shutil
        monkeypatch.setattr(shutil, "which", lambda x: None)
        f = tmp_path / "mcp_server.py"
        f.write_text("# dummy\n", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(main, ["inspect", str(f)])
        assert result.exit_code == 1
        assert "npx" in result.output or "npx" in (result.output + str(result.exception))
