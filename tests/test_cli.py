"""Tests for the CLI commands (generate, list, validate, init)."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli2mcp.cli import main

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _make_config(tmp_path: Path, source_dir: Path | None = None) -> Path:
    """Write a minimal pyproject.toml with [tool.cli2mcp] pointing at the Click fixture."""
    if source_dir is None:
        source_dir = FIXTURE_DIR
    config = tmp_path / "pyproject.toml"
    config.write_text(
        f"""\
[tool.cli2mcp]
server_name = "Test Server"
entry_point = "mycli"
source_dirs = ["{source_dir}"]
output_file = "mcp_tools_generated.py"
server_file = "mcp_server.py"
include_patterns = ["sample_click_cli.py"]
exclude_patterns = []
""",
        encoding="utf-8",
    )
    return config


# ---------------------------------------------------------------------------
# generate --dry-run
# ---------------------------------------------------------------------------


def test_generate_dry_run_prints_both_sections(tmp_path):
    config = _make_config(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["generate", "--config", str(config), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "Generated module" in result.output
    assert "Server scaffold" in result.output
    assert "_register_tools" in result.output
    assert "FastMCP" in result.output


def test_generate_dry_run_no_files_written(tmp_path):
    config = _make_config(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["generate", "--config", str(config), "--dry-run"])
    assert not (tmp_path / "mcp_tools_generated.py").exists()
    assert not (tmp_path / "mcp_server.py").exists()


# ---------------------------------------------------------------------------
# generate (writes files)
# ---------------------------------------------------------------------------


def test_generate_writes_module_file(tmp_path):
    config = _make_config(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["generate", "--config", str(config), "--output", str(tmp_path / "mcp_tools_generated.py")],
    )
    assert result.exit_code == 0, result.output
    module_file = tmp_path / "mcp_tools_generated.py"
    assert module_file.exists()
    # Must be valid Python
    ast.parse(module_file.read_text())


def test_generate_writes_scaffold_first_run(tmp_path):
    config = _make_config(tmp_path)
    runner = CliRunner()
    runner.invoke(
        main,
        ["generate", "--config", str(config), "--output", str(tmp_path / "mcp_tools_generated.py")],
    )
    scaffold = tmp_path / "mcp_server.py"
    assert scaffold.exists()
    assert "FastMCP" in scaffold.read_text()


def test_generate_skips_scaffold_on_second_run(tmp_path):
    config = _make_config(tmp_path)
    runner = CliRunner()
    args = ["generate", "--config", str(config), "--output", str(tmp_path / "mcp_tools_generated.py")]

    runner.invoke(main, args)
    scaffold = tmp_path / "mcp_server.py"
    scaffold.write_text("# custom content", encoding="utf-8")

    runner.invoke(main, args)
    assert scaffold.read_text() == "# custom content"


def test_generate_force_overwrites_scaffold(tmp_path):
    config = _make_config(tmp_path)
    runner = CliRunner()
    args = ["generate", "--config", str(config), "--output", str(tmp_path / "mcp_tools_generated.py")]

    runner.invoke(main, args)
    scaffold = tmp_path / "mcp_server.py"
    scaffold.write_text("# custom content", encoding="utf-8")

    runner.invoke(main, args + ["--force"])
    assert scaffold.read_text() != "# custom content"
    assert "FastMCP" in scaffold.read_text()


def test_generate_bad_config_exits_nonzero(tmp_path):
    missing = tmp_path / "nonexistent.toml"
    runner = CliRunner()
    result = runner.invoke(main, ["generate", "--config", str(missing)])
    assert result.exit_code != 0


def test_generate_missing_section_exits_nonzero(tmp_path):
    config = tmp_path / "pyproject.toml"
    config.write_text("[tool]\nfoo = 1\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["generate", "--config", str(config)])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_text_output(tmp_path):
    config = _make_config(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--config", str(config)])
    assert result.exit_code == 0, result.output
    assert "tool(s)" in result.output
    assert "greet" in result.output


def test_list_json_output(tmp_path):
    config = _make_config(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--config", str(config), "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) >= 1
    names = [t["name"] for t in data]
    assert "greet" in names


def test_list_json_has_required_fields(tmp_path):
    config = _make_config(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--config", str(config), "--format", "json"])
    data = json.loads(result.output)
    for tool in data:
        assert "name" in tool
        assert "framework" in tool
        assert "command" in tool
        assert "description" in tool
        assert "params" in tool


def test_list_bad_config_exits_nonzero(tmp_path):
    missing = tmp_path / "nope.toml"
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--config", str(missing)])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_good_file(tmp_path):
    good = tmp_path / "good.py"
    good.write_text("x = 1\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(good)])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_validate_bad_file(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(bad)])
    assert result.exit_code != 0


def test_validate_generated_module_is_valid(tmp_path):
    """End-to-end: generate then validate."""
    config = _make_config(tmp_path)
    output = tmp_path / "mcp_tools_generated.py"
    runner = CliRunner()
    runner.invoke(main, ["generate", "--config", str(config), "--output", str(output)])
    result = runner.invoke(main, ["validate", str(output)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def test_init_creates_new_file(tmp_path):
    config = tmp_path / "pyproject.toml"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["init", "--server-name", "My Server", "--entry-point", "mycli",
         "--source-dir", "src", "--config", str(config)],
    )
    assert result.exit_code == 0, result.output
    assert config.exists()
    content = config.read_text()
    assert "[tool.cli2mcp]" in content
    assert "My Server" in content


def test_init_appends_to_existing_file(tmp_path):
    config = tmp_path / "pyproject.toml"
    config.write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8")
    runner = CliRunner()
    runner.invoke(
        main,
        ["init", "--server-name", "My Server", "--entry-point", "mycli",
         "--source-dir", "src", "--config", str(config)],
    )
    content = config.read_text()
    assert "[tool.pytest.ini_options]" in content
    assert "[tool.cli2mcp]" in content


def test_init_refuses_if_section_exists(tmp_path):
    config = tmp_path / "pyproject.toml"
    config.write_text("[tool.cli2mcp]\nserver_name = 'x'\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["init", "--server-name", "My Server", "--entry-point", "mycli",
         "--source-dir", "src", "--config", str(config)],
    )
    assert result.exit_code != 0
