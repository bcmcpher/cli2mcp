"""Tests for generator enhancements: 1b/1d/1e/3a/3b/3c/3d."""
from __future__ import annotations

import ast
import pytest
from pathlib import Path

from cli2mcp.models import ParamDef, ToolDef
from cli2mcp.config import Config
from cli2mcp.generators.mcp_server import generate_module


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
# 1b: @click.pass_context — ctx param omitted from generated signature
# ---------------------------------------------------------------------------

class TestPassContext:
    def test_ctx_param_not_in_signature(self, base_config):
        tool = _make_tool(
            has_context=True,
            parameters=[
                ParamDef("ctx", ["ctx"], "object", None, True, "Context."),
                ParamDef("name", ["--name"], "str", None, True, "Name."),
            ],
        )
        result = generate_module([tool], base_config)
        # ctx should NOT appear in the function signature
        assert "ctx" not in result.split("def greet(")[1].split(")")[0]

    def test_real_param_still_in_signature(self, base_config):
        tool = _make_tool(
            has_context=True,
            parameters=[
                ParamDef("ctx", ["ctx"], "object", None, True, "Context."),
                ParamDef("name", ["--name"], "str", None, True, "Name."),
            ],
        )
        result = generate_module([tool], base_config)
        assert "name: str" in result


# ---------------------------------------------------------------------------
# 1d: subcommand_path — nested groups use full path
# ---------------------------------------------------------------------------

class TestSubcommandPath:
    def test_nested_path_in_subprocess_args(self, base_config):
        tool = _make_tool(
            name="migrate",
            cli_subcommand="migrate",
            subcommand_path=["db", "migrate"],
        )
        result = generate_module([tool], base_config)
        assert "'db'" in result
        assert "'migrate'" in result

    def test_nested_path_order(self, base_config):
        """The path elements must appear in order in the subprocess call."""
        tool = _make_tool(
            name="migrate",
            cli_subcommand="migrate",
            subcommand_path=["db", "migrate"],
        )
        result = generate_module([tool], base_config)
        db_idx = result.find("'db'")
        migrate_idx = result.find("'migrate'")
        assert db_idx < migrate_idx, "db must appear before migrate in subprocess args"

    def test_single_level_path_backward_compat(self, base_config):
        """Single-element subcommand_path still works."""
        tool = _make_tool(subcommand_path=["greet"])
        result = generate_module([tool], base_config)
        assert "'greet'" in result


# ---------------------------------------------------------------------------
# 1e: Hidden params excluded from generated signature and subprocess call
# ---------------------------------------------------------------------------

class TestHiddenParams:
    def test_hidden_param_not_in_signature(self, base_config):
        tool = _make_tool(
            parameters=[
                ParamDef("name", ["--name"], "str", None, True, "Name."),
                ParamDef("token", ["--token"], "str", None, False, "Debug token.", hidden=True),
            ],
        )
        result = generate_module([tool], base_config)
        sig_line = result.split("def greet(")[1].split(")")[0]
        assert "token" not in sig_line

    def test_hidden_param_not_in_subprocess_call(self, base_config):
        tool = _make_tool(
            parameters=[
                ParamDef("name", ["--name"], "str", None, True, "Name."),
                ParamDef("token", ["--token"], "str", None, False, "Debug token.", hidden=True),
            ],
        )
        result = generate_module([tool], base_config)
        assert "'--token'" not in result

    def test_visible_param_still_present(self, base_config):
        tool = _make_tool(
            parameters=[
                ParamDef("name", ["--name"], "str", None, True, "Name."),
                ParamDef("token", ["--token"], "str", None, False, "Debug token.", hidden=True),
            ],
        )
        result = generate_module([tool], base_config)
        assert "name: str" in result
        assert "'--name'" in result


# ---------------------------------------------------------------------------
# 3a: prefer_direct_import — use return_type in signature
# ---------------------------------------------------------------------------

class TestPreferDirectImport:
    def test_default_returns_str(self, base_config):
        tool = _make_tool(return_type="dict")
        result = generate_module([tool], base_config)
        assert "def greet() -> str:" in result

    def test_prefer_direct_import_uses_return_type(self):
        config = Config(
            server_name="Test",
            entry_point="mytool",
            source_dirs=[Path("src")],
            output_file=Path("out.py"),
            server_file=Path("server.py"),
            prefer_direct_import=True,
        )
        tool = _make_tool(return_type="dict")
        result = generate_module([tool], config)
        assert "def greet() -> dict:" in result

    def test_syntax_valid_with_prefer_direct_import(self):
        config = Config(
            server_name="Test",
            entry_point="mytool",
            source_dirs=[Path("src")],
            output_file=Path("out.py"),
            server_file=Path("server.py"),
            prefer_direct_import=True,
        )
        tool = _make_tool(return_type="list[str]")
        result = generate_module([tool], config)
        ast.parse(result)


# ---------------------------------------------------------------------------
# 3b: stderr capture — error includes stdout; capture_stderr config
# ---------------------------------------------------------------------------

class TestStderrHandling:
    def test_error_message_includes_stdout(self, base_config):
        result = generate_module([_make_tool()], base_config)
        assert "result.stdout" in result
        assert "result.stderr" in result

    def test_error_includes_exit_code(self, base_config):
        result = generate_module([_make_tool()], base_config)
        assert "returncode" in result

    def test_capture_stderr_false_no_stderr_in_return(self, base_config):
        """Default: stderr not appended to successful stdout."""
        result = generate_module([_make_tool()], base_config)
        # Should NOT have the stderr-append logic on success path
        assert "--- stderr ---" not in result

    def test_capture_stderr_true_appends_stderr(self):
        config = Config(
            server_name="Test",
            entry_point="mytool",
            source_dirs=[Path("src")],
            output_file=Path("out.py"),
            server_file=Path("server.py"),
            capture_stderr=True,
        )
        result = generate_module([_make_tool()], config)
        assert "--- stderr ---" in result
        ast.parse(result)


# ---------------------------------------------------------------------------
# 3c: Per-tool timeout overrides global
# ---------------------------------------------------------------------------

class TestPerToolTimeout:
    def test_tool_timeout_used_when_set(self, base_config):
        tool = _make_tool(timeout=60)
        result = generate_module([tool], base_config)
        assert "timeout=60" in result

    def test_global_timeout_used_when_tool_timeout_none(self):
        config = Config(
            server_name="Test",
            entry_point="mytool",
            source_dirs=[Path("src")],
            output_file=Path("out.py"),
            server_file=Path("server.py"),
            subprocess_timeout=30,
        )
        tool = _make_tool()  # timeout=None by default
        result = generate_module([tool], config)
        assert "timeout=30" in result

    def test_tool_timeout_overrides_global(self):
        config = Config(
            server_name="Test",
            entry_point="mytool",
            source_dirs=[Path("src")],
            output_file=Path("out.py"),
            server_file=Path("server.py"),
            subprocess_timeout=30,
        )
        tool = _make_tool(timeout=120)
        result = generate_module([tool], config)
        assert "timeout=120" in result
        assert "timeout=30" not in result

    def test_no_timeout_when_both_none(self, base_config):
        tool = _make_tool()
        result = generate_module([tool], base_config)
        assert "timeout=" not in result


# ---------------------------------------------------------------------------
# 3d: Stdin support
# ---------------------------------------------------------------------------

class TestStdinSupport:
    def test_stdin_param_in_signature(self, base_config):
        tool = _make_tool(stdin_param="data")
        result = generate_module([tool], base_config)
        assert "data: str" in result

    def test_stdin_passed_to_subprocess(self, base_config):
        tool = _make_tool(stdin_param="data")
        result = generate_module([tool], base_config)
        assert "input=data" in result

    def test_stdin_syntax_valid(self, base_config):
        tool = _make_tool(stdin_param="payload")
        result = generate_module([tool], base_config)
        ast.parse(result)

    def test_no_stdin_param_no_input_arg(self, base_config):
        tool = _make_tool()  # stdin_param=None
        result = generate_module([tool], base_config)
        assert "input=" not in result


# ---------------------------------------------------------------------------
# Generated file always produces valid Python syntax
# ---------------------------------------------------------------------------

def test_all_features_combined_valid_syntax(base_config):
    config = Config(
        server_name="Test",
        entry_point="mytool",
        source_dirs=[Path("src")],
        output_file=Path("out.py"),
        server_file=Path("server.py"),
        subprocess_timeout=30,
        capture_stderr=True,
        prefer_direct_import=True,
    )
    tool = ToolDef(
        name="complex_tool",
        description="A tool with all features.",
        parameters=[
            ParamDef("name", ["--name"], "str", None, True, "Name."),
            ParamDef("count", ["--count"], "int", 1, False, "Count."),
            ParamDef("secret", ["--secret"], "str", None, False, "Hidden.", hidden=True),
        ],
        return_description="Output.",
        source_module="pkg.cli",
        source_function="complex_tool",
        cli_command="mytool",
        cli_subcommand="complex",
        framework="click",
        has_context=True,
        subcommand_path=["db", "complex"],
        return_type="dict",
        timeout=120,
        stdin_param="data",
    )
    result = generate_module([tool], config)
    ast.parse(result)
