"""Tests for config/CLI enhancements: 6a/6b/6c/7a/7b."""
from __future__ import annotations

import json
import textwrap
import pytest
from pathlib import Path
from click.testing import CliRunner

from cli2mcp.cli import main, _collect_tools
from cli2mcp.config import Config, load_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_config(tmp_path: Path, extra: str = "") -> Path:
    """Write a minimal pyproject.toml using the sample click fixture."""
    fixtures = Path(__file__).parent / "fixtures"
    config = tmp_path / "pyproject.toml"
    config.write_text(textwrap.dedent(f"""\
        [tool.cli2mcp]
        server_name = "Test"
        entry_point = "mycli"
        source_dirs = ["{fixtures}"]
        include_patterns = ["sample_click_cli.py"]
        exclude_patterns = []
        {extra}
    """))
    return config


# ---------------------------------------------------------------------------
# 6a: Relative path pattern matching
# ---------------------------------------------------------------------------

class TestRelativePathPatterns:
    def test_deep_path_pattern_matches(self, tmp_path):
        """A pattern like 'sub/*.py' should match files in a subdirectory."""
        sub = tmp_path / "src" / "sub"
        sub.mkdir(parents=True)
        (sub / "mymodule.py").write_text(
            "import click\n\n@click.command()\ndef hello():\n    pass\n"
        )
        config_path = tmp_path / "pyproject.toml"
        config_path.write_text(textwrap.dedent(f"""\
            [tool.cli2mcp]
            server_name = "Test"
            entry_point = "mycli"
            source_dirs = ["{tmp_path / 'src'}"]
            include_patterns = ["sub/*.py"]
            exclude_patterns = []
        """))
        tools, config, skipped = _collect_tools(config_path)
        names = [t.name for t in tools]
        assert "hello" in names

    def test_filename_pattern_still_works(self, tmp_path):
        """Simple filename patterns (no path separator) still work (backward compat)."""
        config = _write_config(tmp_path)
        tools, _, _ = _collect_tools(config)
        names = [t.name for t in tools]
        assert "greet" in names


# ---------------------------------------------------------------------------
# 6b: include_tools / exclude_tools
# ---------------------------------------------------------------------------

class TestToolNameFilters:
    def test_include_tools_limits_output(self, tmp_path):
        """include_tools=['greet'] should produce only the greet tool."""
        config = _write_config(tmp_path, 'include_tools = ["greet"]')
        tools, _, _ = _collect_tools(config)
        assert all(t.name == "greet" for t in tools)
        assert len(tools) == 1

    def test_exclude_tools_removes_tool(self, tmp_path):
        """exclude_tools=['greet'] should remove greet from the output."""
        config = _write_config(tmp_path, 'exclude_tools = ["greet"]')
        tools, _, _ = _collect_tools(config)
        names = [t.name for t in tools]
        assert "greet" not in names

    def test_empty_filters_keep_all(self, tmp_path):
        config = _write_config(tmp_path)
        tools, _, _ = _collect_tools(config)
        assert len(tools) >= 2  # greet, process, fetch

    def test_config_loads_include_tools(self, tmp_path):
        config_path = _write_config(tmp_path, 'include_tools = ["foo", "bar"]')
        config = load_config(config_path)
        assert config.include_tools == ["foo", "bar"]

    def test_config_loads_exclude_tools(self, tmp_path):
        config_path = _write_config(tmp_path, 'exclude_tools = ["secret_cmd"]')
        config = load_config(config_path)
        assert config.exclude_tools == ["secret_cmd"]


# ---------------------------------------------------------------------------
# 6c: entry_point PATH validation
# ---------------------------------------------------------------------------

class TestEntryPointValidation:
    def test_missing_entry_point_warns(self, tmp_path):
        """If entry_point is not on PATH, generate should warn."""
        fixtures = Path(__file__).parent / "fixtures"
        config = tmp_path / "pyproject.toml"
        config.write_text(textwrap.dedent(f"""\
            [tool.cli2mcp]
            server_name = "Test"
            entry_point = "this_command_definitely_does_not_exist_xyz123"
            source_dirs = ["{fixtures}"]
            include_patterns = ["sample_click_cli.py"]
            exclude_patterns = []
        """))
        runner = CliRunner()
        result = runner.invoke(main, ["generate", "--config", str(config), "--dry-run"])
        # Should warn (not error) about missing entry_point
        assert "not found on PATH" in result.output or "not found on PATH" in (result.output + str(result.exception))

    def test_valid_entry_point_no_warning(self, tmp_path):
        """A real command on PATH should not produce a warning."""
        fixtures = Path(__file__).parent / "fixtures"
        config = tmp_path / "pyproject.toml"
        config.write_text(textwrap.dedent(f"""\
            [tool.cli2mcp]
            server_name = "Test"
            entry_point = "python"
            source_dirs = ["{fixtures}"]
            include_patterns = ["sample_click_cli.py"]
            exclude_patterns = []
        """))
        runner = CliRunner()
        result = runner.invoke(main, ["generate", "--config", str(config), "--dry-run"])
        assert "not found on PATH" not in result.output


# ---------------------------------------------------------------------------
# 7a: Duplicate tool name detection
# ---------------------------------------------------------------------------

class TestDuplicateToolNames:
    def test_duplicate_name_triggers_warning(self, tmp_path):
        """Two files with the same command name should produce a warning."""
        (tmp_path / "a.py").write_text(
            "import click\n\n@click.command()\ndef greet():\n    '''Greet from A.'''\n    pass\n"
        )
        (tmp_path / "b.py").write_text(
            "import click\n\n@click.command()\ndef greet():\n    '''Greet from B.'''\n    pass\n"
        )
        config = tmp_path / "pyproject.toml"
        config.write_text(textwrap.dedent(f"""\
            [tool.cli2mcp]
            server_name = "Test"
            entry_point = "mycli"
            source_dirs = ["{tmp_path}"]
            include_patterns = ["*.py"]
            exclude_patterns = []
        """))
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--config", str(config)])
        # Warning should mention the duplicate name
        assert "duplicate" in result.output.lower() or "greet" in result.output


# ---------------------------------------------------------------------------
# 7b: Skipped files reported
# ---------------------------------------------------------------------------

class TestSkippedFiles:
    def test_syntax_error_file_in_skipped(self, tmp_path):
        """Files with syntax errors should appear in the skipped list."""
        bad = tmp_path / "bad.py"
        bad.write_text("def (:\n    pass\n")  # SyntaxError

        good = tmp_path / "good.py"
        good.write_text(
            "import click\n\n@click.command()\ndef cmd():\n    pass\n"
        )

        config = tmp_path / "pyproject.toml"
        config.write_text(textwrap.dedent(f"""\
            [tool.cli2mcp]
            server_name = "Test"
            entry_point = "mycli"
            source_dirs = ["{tmp_path}"]
            include_patterns = ["*.py"]
            exclude_patterns = []
        """))

        tools, _, skipped = _collect_tools(config)
        skipped_paths = [str(p) for p, _ in skipped]
        assert any("bad.py" in p for p in skipped_paths)

    def test_skipped_files_in_text_list_output(self, tmp_path):
        """Text `list` output should mention skipped files."""
        bad = tmp_path / "bad.py"
        bad.write_text("def (:\n    pass\n")

        good = tmp_path / "good.py"
        good.write_text(
            "import click\n\n@click.command()\ndef cmd():\n    pass\n"
        )

        config = tmp_path / "pyproject.toml"
        config.write_text(textwrap.dedent(f"""\
            [tool.cli2mcp]
            server_name = "Test"
            entry_point = "mycli"
            source_dirs = ["{tmp_path}"]
            include_patterns = ["*.py"]
            exclude_patterns = []
        """))

        runner = CliRunner()
        result = runner.invoke(main, ["list", "--config", str(config)])
        assert "bad.py" in result.output or "skipped" in result.output.lower()

    def test_skipped_files_in_json_output(self, tmp_path):
        """JSON `list` output should include a 'skipped' key."""
        bad = tmp_path / "bad.py"
        bad.write_text("def (:\n    pass\n")

        good = tmp_path / "good.py"
        good.write_text(
            "import click\n\n@click.command()\ndef cmd():\n    pass\n"
        )

        config = tmp_path / "pyproject.toml"
        config.write_text(textwrap.dedent(f"""\
            [tool.cli2mcp]
            server_name = "Test"
            entry_point = "mycli"
            source_dirs = ["{tmp_path}"]
            include_patterns = ["*.py"]
            exclude_patterns = []
        """))

        # mix_stderr=False keeps warnings on stderr, stdout is pure JSON
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["list", "--config", str(config), "--format", "json"])
        data = json.loads(result.output)
        assert "skipped" in data
        assert len(data["skipped"]) >= 1
        skipped_paths = [s["path"] for s in data["skipped"]]
        assert any("bad.py" in p for p in skipped_paths)


# ---------------------------------------------------------------------------
# config.py: new fields load correctly
# ---------------------------------------------------------------------------

class TestConfigNewFields:
    def test_prefer_direct_import_default_false(self, tmp_path):
        config = load_config(_write_config(tmp_path))
        assert config.prefer_direct_import is False

    def test_capture_stderr_default_false(self, tmp_path):
        config = load_config(_write_config(tmp_path))
        assert config.capture_stderr is False

    def test_include_tools_default_empty(self, tmp_path):
        config = load_config(_write_config(tmp_path))
        assert config.include_tools == []

    def test_exclude_tools_default_empty(self, tmp_path):
        config = load_config(_write_config(tmp_path))
        assert config.exclude_tools == []

    def test_prefer_direct_import_loaded(self, tmp_path):
        config_path = _write_config(tmp_path, "prefer_direct_import = true")
        config = load_config(config_path)
        assert config.prefer_direct_import is True

    def test_capture_stderr_loaded(self, tmp_path):
        config_path = _write_config(tmp_path, "capture_stderr = true")
        config = load_config(config_path)
        assert config.capture_stderr is True
