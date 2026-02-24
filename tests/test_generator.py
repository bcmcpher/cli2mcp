"""Tests for the MCP server code generator."""
import ast
import pytest
from pathlib import Path
from cli2mcp.models import ParamDef, ToolDef
from cli2mcp.config import Config
from cli2mcp.generators.mcp_server import generate_module, generate_server_scaffold


@pytest.fixture
def sample_config():
    return Config(
        server_name="Test Server",
        entry_point="mytool",
        source_dirs=[Path("src")],
        output_file=Path("mcp_tools_generated.py"),
        server_file=Path("mcp_server.py"),
    )


@pytest.fixture
def simple_tool():
    return ToolDef(
        name="greet",
        description="Greet a user.",
        parameters=[
            ParamDef(
                name="name",
                cli_flags=["name"],
                type_annotation="str",
                default=None,
                required=True,
                description="The name of the person.",
            ),
            ParamDef(
                name="count",
                cli_flags=["--count", "-c"],
                type_annotation="int",
                default=1,
                required=False,
                description="Number of greetings.",
            ),
            ParamDef(
                name="loud",
                cli_flags=["--loud"],
                type_annotation="bool",
                default=False,
                required=False,
                description="Print in uppercase.",
                is_flag=True,
            ),
        ],
        return_description="The greeting message.",
        source_module="mypackage.cli",
        source_function="greet",
        cli_command="mytool",
        cli_subcommand="greet",
        framework="click",
    )


# --- generate_module tests ---

def test_generate_produces_string(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert isinstance(result, str)


def test_generate_module_no_fastmcp_import(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "from mcp.server.fastmcp import FastMCP" not in result


def test_generate_module_no_mcp_instantiation(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert 'FastMCP(' not in result


def test_generate_module_no_main_block(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert 'if __name__ == "__main__"' not in result


def test_generate_module_contains_register_tools(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "def _register_tools(mcp)" in result


def test_generate_module_tool_is_indented(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "    @mcp.tool()" in result


def test_generate_contains_tool_decorator(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "@mcp.tool()" in result


def test_generate_contains_function_name(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "def greet(" in result


def test_generate_contains_required_param(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "name: str" in result


def test_generate_contains_optional_param_default(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "count: int = 1" in result


def test_generate_contains_flag_param(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "loud: bool = False" in result


def test_generate_contains_subprocess(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "subprocess.run(" in result


def test_generate_contains_cli_command(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "'mytool'" in result


def test_generate_contains_subcommand(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "'greet'" in result


def test_generate_contains_flag_conditional(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "if loud" in result


def test_generate_contains_option_flag(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "'--count'" in result


def test_generate_no_params_tool(sample_config):
    tool = ToolDef(
        name="ping",
        description="Ping the service.",
        parameters=[],
        return_description="Pong.",
        source_module="mypackage.cli",
        source_function="ping",
        cli_command="mytool",
        cli_subcommand="ping",
        framework="click",
    )
    result = generate_module([tool], sample_config)
    assert "def ping()" in result


def test_generate_direct_import_comment(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "# from mypackage.cli import greet" in result


def test_generate_multiple_tools(sample_config, simple_tool):
    tool2 = ToolDef(
        name="farewell",
        description="Say goodbye.",
        parameters=[],
        return_description="Goodbye message.",
        source_module="mypackage.cli",
        source_function="farewell",
        cli_command="mytool",
        cli_subcommand="farewell",
        framework="click",
    )
    result = generate_module([simple_tool, tool2], sample_config)
    assert "def greet(" in result
    assert "def farewell(" in result


def test_generate_returns_section(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "Returns" in result
    assert "The greeting message." in result


def test_generate_valid_python_syntax(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    # Should not raise SyntaxError
    ast.parse(result)


def test_generate_module_do_not_edit_comment(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "DO NOT EDIT" in result


# --- generate_server_scaffold tests ---

def test_scaffold_produces_string(sample_config):
    result = generate_server_scaffold(sample_config, "mcp_tools_generated")
    assert isinstance(result, str)


def test_scaffold_contains_fastmcp_import(sample_config):
    result = generate_server_scaffold(sample_config, "mcp_tools_generated")
    assert "from mcp.server.fastmcp import FastMCP" in result


def test_scaffold_contains_server_name(sample_config):
    result = generate_server_scaffold(sample_config, "mcp_tools_generated")
    assert 'FastMCP("Test Server")' in result


def test_scaffold_contains_module_import(sample_config):
    result = generate_server_scaffold(sample_config, "mcp_tools_generated")
    assert "from mcp_tools_generated import _register_tools" in result


def test_scaffold_contains_register_tools_call(sample_config):
    result = generate_server_scaffold(sample_config, "mcp_tools_generated")
    assert "_register_tools(mcp)" in result


def test_scaffold_contains_main_block(sample_config):
    result = generate_server_scaffold(sample_config, "mcp_tools_generated")
    assert 'if __name__ == "__main__"' in result
    assert "mcp.run()" in result


def test_scaffold_valid_python_syntax(sample_config):
    result = generate_server_scaffold(sample_config, "mcp_tools_generated")
    ast.parse(result)


def test_scaffold_uses_custom_module_stem(sample_config):
    result = generate_server_scaffold(sample_config, "my_custom_tools")
    assert "from my_custom_tools import _register_tools" in result


# --- subprocess timeout (issue #3) ---

def test_generate_no_timeout_by_default(sample_config, simple_tool):
    result = generate_module([simple_tool], sample_config)
    assert "timeout=" not in result


def test_generate_with_timeout(simple_tool):
    config = Config(
        server_name="Test",
        entry_point="mytool",
        source_dirs=[Path("src")],
        output_file=Path("mcp_tools_generated.py"),
        server_file=Path("mcp_server.py"),
        subprocess_timeout=30,
    )
    result = generate_module([simple_tool], config)
    assert "timeout=30" in result


# --- choices in docstring (issue #7) ---

def test_generate_choices_in_docstring(sample_config):
    tool = ToolDef(
        name="export",
        description="Export data.",
        parameters=[
            ParamDef(
                name="fmt",
                cli_flags=["--fmt"],
                type_annotation="str",
                default="json",
                required=False,
                description="Output format.",
                choices=["json", "csv", "xml"],
            ),
        ],
        return_description="Result.",
        source_module="mypackage.cli",
        source_function="export",
        cli_command="mytool",
        cli_subcommand="export",
        framework="click",
    )
    result = generate_module([tool], sample_config)
    assert "json" in result
    assert "csv" in result
    assert "xml" in result


# --- is_multiple generates list args (issue #7) ---

def test_generate_multiple_param_repeats_flag(sample_config):
    tool = ToolDef(
        name="tag",
        description="Tag something.",
        parameters=[
            ParamDef(
                name="tags",
                cli_flags=["--tags"],
                type_annotation="list[str]",
                default=None,
                required=True,
                description="Tags to apply.",
                is_multiple=True,
            ),
        ],
        return_description="Result.",
        source_module="mypackage.cli",
        source_function="tag",
        cli_command="mytool",
        cli_subcommand="tag",
        framework="click",
    )
    result = generate_module([tool], sample_config)
    # Multi-value flag should repeat the flag for each value
    assert "for v in tags" in result
    # Must be valid Python
    ast.parse(result)
