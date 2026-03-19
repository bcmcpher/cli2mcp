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
        assert "ctx" not in result.split("def mytool_greet(")[1].split(")")[0]

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
        sig_line = result.split("def mytool_greet(")[1].split(")")[0]
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
        assert "def mytool_greet() -> str:" in result

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
        assert "def mytool_greet() -> dict:" in result

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
        assert "_stdout" in result
        assert "_stderr" in result

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
        assert "input=params.data" in result

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


# ---------------------------------------------------------------------------
# B: Tool annotations in @mcp.tool() decorator
# ---------------------------------------------------------------------------

class TestToolAnnotations:
    def test_annotations_block_present(self, base_config):
        result = generate_module([_make_tool(name="greet")], base_config)
        assert "annotations=" in result

    def test_open_world_hint_always_true(self, base_config):
        result = generate_module([_make_tool(name="greet")], base_config)
        assert '"openWorldHint": True' in result

    def test_read_prefix_sets_readonly(self, base_config):
        for prefix in ("list_users", "get_config", "show_status", "fetch_data", "search_items", "find_thing", "describe_all", "read_file"):
            result = generate_module([_make_tool(name=prefix)], base_config)
            assert '"readOnlyHint": True' in result, f"expected readOnlyHint for {prefix}"
            assert '"idempotentHint": True' in result, f"expected idempotentHint for {prefix}"

    def test_non_read_prefix_not_readonly(self, base_config):
        result = generate_module([_make_tool(name="greet")], base_config)
        assert '"readOnlyHint": False' in result
        assert '"idempotentHint": False' in result

    def test_destructive_prefix_sets_destructive(self, base_config):
        for prefix in ("delete_user", "remove_item", "drop_table", "purge_cache", "wipe_data"):
            result = generate_module([_make_tool(name=prefix)], base_config)
            assert '"destructiveHint": True' in result, f"expected destructiveHint for {prefix}"

    def test_non_destructive_not_flagged(self, base_config):
        result = generate_module([_make_tool(name="greet")], base_config)
        assert '"destructiveHint": False' in result

    def test_generated_source_is_valid_python(self, base_config):
        for name in ("list_users", "delete_record", "process_data", "greet"):
            result = generate_module([_make_tool(name=name)], base_config)
            ast.parse(result)  # raises SyntaxError if broken


# ---------------------------------------------------------------------------
# B2: Per-tool annotation overrides via config
# ---------------------------------------------------------------------------

class TestAnnotationOverrides:
    def _config_with_overrides(self, overrides: dict) -> Config:
        return Config(
            server_name="Test Server",
            entry_point="mytool",
            source_dirs=[Path("src")],
            output_file=Path("mcp_tools_generated.py"),
            server_file=Path("mcp_server.py"),
            tool_annotations=overrides,
        )

    def test_override_replaces_inferred_value(self):
        # "process_data" infers readOnlyHint=False; override to True
        config = self._config_with_overrides({"process_data": {"readOnlyHint": True}})
        result = generate_module([_make_tool(name="process_data")], config)
        assert '"readOnlyHint": True' in result

    def test_partial_override_merges_with_inferred(self):
        # Override only destructiveHint; other inferred values should remain
        config = self._config_with_overrides({"process_data": {"destructiveHint": True}})
        result = generate_module([_make_tool(name="process_data")], config)
        assert '"destructiveHint": True' in result
        assert '"openWorldHint": True' in result  # inferred value preserved

    def test_override_does_not_affect_other_tools(self):
        config = self._config_with_overrides({"process_data": {"readOnlyHint": True}})
        result = generate_module([_make_tool(name="greet")], config)
        assert '"readOnlyHint": False' in result  # greet unaffected

    def test_no_overrides_uses_inferred(self, base_config):
        result = generate_module([_make_tool(name="list_users")], base_config)
        assert '"readOnlyHint": True' in result


# ---------------------------------------------------------------------------
# E: Async subprocess
# ---------------------------------------------------------------------------

class TestAsyncSubprocess:
    def test_import_asyncio_not_subprocess(self, base_config):
        result = generate_module([_make_tool()], base_config)
        assert "import asyncio" in result
        assert "import subprocess" not in result

    def test_async_def(self, base_config):
        result = generate_module([_make_tool()], base_config)
        assert "async def mytool_greet(" in result

    def test_create_subprocess_exec(self, base_config):
        result = generate_module([_make_tool()], base_config)
        assert "asyncio.create_subprocess_exec(" in result
        assert "subprocess.run(" not in result

    def test_cmd_list_unpacked(self, base_config):
        result = generate_module([_make_tool()], base_config)
        assert "_cmd = [" in result
        assert "*_cmd," in result

    def test_stdout_stderr_pipes(self, base_config):
        result = generate_module([_make_tool()], base_config)
        assert "stdout=asyncio.subprocess.PIPE" in result
        assert "stderr=asyncio.subprocess.PIPE" in result

    def test_communicate_awaited(self, base_config):
        result = generate_module([_make_tool()], base_config)
        assert "await _proc.communicate()" in result

    def test_bytes_decoded(self, base_config):
        result = generate_module([_make_tool()], base_config)
        assert "_stdout = _stdout_b.decode()" in result
        assert "_stderr = _stderr_b.decode()" in result

    def test_timeout_uses_wait_for(self):
        config = Config(
            server_name="Test", entry_point="mytool",
            source_dirs=[Path("src")], output_file=Path("out.py"),
            server_file=Path("s.py"), subprocess_timeout=45,
        )
        result = generate_module([_make_tool()], config)
        assert "asyncio.wait_for(_proc.communicate(), timeout=45)" in result
        assert "asyncio.TimeoutError" in result
        assert "timed out after 45s" in result

    def test_no_timeout_no_wait_for(self, base_config):
        result = generate_module([_make_tool()], base_config)
        assert "asyncio.wait_for(" not in result
        assert "asyncio.TimeoutError" not in result

    def test_stdin_pipe_opened(self, base_config):
        tool = _make_tool(stdin_param="data")
        result = generate_module([tool], base_config)
        assert "stdin=asyncio.subprocess.PIPE" in result
        assert "_proc.communicate(input=params.data.encode())" in result

    def test_no_stdin_no_pipe(self, base_config):
        result = generate_module([_make_tool()], base_config)
        assert "stdin=asyncio.subprocess.PIPE" not in result

    def test_generated_source_valid_python(self, base_config):
        for kwargs in (
            {},
            {"stdin_param": "data"},
            {"timeout": 30},
            {"stdin_param": "payload", "timeout": 10},
        ):
            result = generate_module([_make_tool(**kwargs)], base_config)
            ast.parse(result)


# ---------------------------------------------------------------------------
# C: Service-prefix tool names
# ---------------------------------------------------------------------------

class TestServicePrefixToolNames:
    def _config(self, entry_point: str, prefix: bool = True) -> Config:
        return Config(
            server_name="Test",
            entry_point=entry_point,
            source_dirs=[Path("src")],
            output_file=Path("out.py"),
            server_file=Path("server.py"),
            prefix_tool_names=prefix,
        )

    def test_prefix_on_by_default(self):
        config = Config(
            server_name="Test", entry_point="myapp",
            source_dirs=[Path("src")], output_file=Path("out.py"), server_file=Path("s.py"),
        )
        assert config.prefix_tool_names is True

    def test_prefixed_name_in_def(self):
        result = generate_module([_make_tool(name="greet")], self._config("myapp"))
        assert "def myapp_greet(" in result

    def test_prefixed_name_in_decorator(self):
        result = generate_module([_make_tool(name="greet")], self._config("myapp"))
        assert 'name="myapp_greet"' in result

    def test_hyphen_normalized_to_underscore(self):
        result = generate_module([_make_tool(name="greet")], self._config("my-app"))
        assert "def my_app_greet(" in result
        assert 'name="my_app_greet"' in result

    def test_mixed_separators_normalized(self):
        result = generate_module([_make_tool(name="run")], self._config("my.cli-tool"))
        assert "def my_cli_tool_run(" in result

    def test_prefix_off_uses_raw_name(self):
        result = generate_module([_make_tool(name="greet")], self._config("myapp", prefix=False))
        assert "def greet(" in result
        assert 'name="greet"' in result
        assert "def myapp_greet(" not in result

    def test_annotation_inference_uses_raw_name(self):
        # Prefix shouldn't confuse annotation inference — "list_users" should still be readOnly
        # even though with prefix it becomes "myapp_list_users"
        result = generate_module([_make_tool(name="list_users")], self._config("myapp"))
        assert '"readOnlyHint": True' in result

    def test_annotation_override_keyed_on_raw_name(self):
        # tool_annotations uses raw tool.name, not the prefixed name
        config = Config(
            server_name="Test", entry_point="myapp",
            source_dirs=[Path("src")], output_file=Path("out.py"), server_file=Path("s.py"),
            tool_annotations={"process_data": {"readOnlyHint": True}},
        )
        result = generate_module([_make_tool(name="process_data")], config)
        assert '"readOnlyHint": True' in result

    def test_generated_source_valid_python(self):
        for ep in ("myapp", "my-app", "my.cli"):
            result = generate_module([_make_tool(name="greet")], self._config(ep))
            ast.parse(result)


# ---------------------------------------------------------------------------
# D: Pydantic input models
# ---------------------------------------------------------------------------

class TestPydanticInputModels:
    def test_pydantic_import_in_header(self, base_config):
        result = generate_module([_make_tool()], base_config)
        assert "from pydantic import BaseModel, Field" in result

    def test_literal_import_in_header(self, base_config):
        result = generate_module([_make_tool()], base_config)
        assert "Literal" in result

    def test_model_class_generated_for_tool_with_params(self, base_config):
        tool = _make_tool(parameters=[
            ParamDef("name", ["--name"], "str", None, True, "Name."),
        ])
        result = generate_module([tool], base_config)
        assert "class MytoolGreetInput(BaseModel):" in result

    def test_no_model_for_no_param_tool(self, base_config):
        tool = _make_tool()  # parameters=[]
        result = generate_module([tool], base_config)
        # No class definition — BaseModel is still imported in the header but not subclassed
        assert "class MytoolGreetInput" not in result
        assert "(BaseModel)" not in result

    def test_required_param_uses_ellipsis_field(self, base_config):
        tool = _make_tool(parameters=[
            ParamDef("name", ["--name"], "str", None, True, "Name."),
        ])
        result = generate_module([tool], base_config)
        assert "name: str = Field(...," in result

    def test_optional_param_uses_default_field(self, base_config):
        tool = _make_tool(parameters=[
            ParamDef("count", ["--count"], "int", 1, False, "Count."),
        ])
        result = generate_module([tool], base_config)
        assert "count: int = Field(1," in result

    def test_choices_produce_literal_type(self, base_config):
        tool = ToolDef(
            name="export", description="Export.",
            parameters=[
                ParamDef("fmt", ["--fmt"], "str", "json", False, "Format.", choices=["json", "csv", "xml"]),
            ],
            return_description="Result.", source_module="pkg.cli", source_function="export",
            cli_command="mytool", cli_subcommand="export", framework="click",
        )
        result = generate_module([tool], base_config)
        assert "Literal['json', 'csv', 'xml']" in result

    def test_stdin_param_becomes_model_field(self, base_config):
        tool = _make_tool(stdin_param="data")
        result = generate_module([tool], base_config)
        assert "class MytoolGreetInput(BaseModel):" in result
        assert "data: str = Field(" in result

    def test_function_sig_uses_model_param(self, base_config):
        tool = _make_tool(parameters=[
            ParamDef("name", ["--name"], "str", None, True, "Name."),
        ])
        result = generate_module([tool], base_config)
        assert "def mytool_greet(params: MytoolGreetInput)" in result

    def test_body_uses_params_prefix(self, base_config):
        tool = _make_tool(parameters=[
            ParamDef("name", ["--name"], "str", None, True, "Name."),
        ])
        result = generate_module([tool], base_config)
        assert "params.name" in result

    def test_no_params_tool_keeps_empty_sig(self, base_config):
        tool = _make_tool()  # parameters=[]
        result = generate_module([tool], base_config)
        assert "def mytool_greet()" in result

    def test_model_before_register_tools(self, base_config):
        tool = _make_tool(parameters=[
            ParamDef("name", ["--name"], "str", None, True, "Name."),
        ])
        result = generate_module([tool], base_config)
        model_idx = result.find("class MytoolGreetInput")
        register_idx = result.find("def _register_tools")
        assert model_idx < register_idx

    def test_valid_python(self, base_config):
        tool = _make_tool(parameters=[
            ParamDef("name", ["--name"], "str", None, True, "Name."),
            ParamDef("count", ["--count"], "int", 1, False, "Count."),
        ])
        result = generate_module([tool], base_config)
        ast.parse(result)


# ---------------------------------------------------------------------------
# F: Structured output mode (prefer_direct_import=True)
# ---------------------------------------------------------------------------

class TestDirectImport:
    def _direct_config(self, **kwargs) -> Config:
        return Config(
            server_name="Test",
            entry_point="mytool",
            source_dirs=[Path("src")],
            output_file=Path("out.py"),
            server_file=Path("s.py"),
            prefer_direct_import=True,
            **kwargs,
        )

    def test_direct_import_uses_asyncio_to_thread(self):
        tool = _make_tool(parameters=[
            ParamDef("name", ["--name"], "str", None, True, "Name."),
        ])
        result = generate_module([tool], self._direct_config())
        assert "asyncio.to_thread" in result

    def test_direct_import_from_statement(self):
        tool = _make_tool(parameters=[
            ParamDef("name", ["--name"], "str", None, True, "Name."),
        ])
        result = generate_module([tool], self._direct_config())
        assert "from pkg.cli import greet" in result

    def test_direct_import_no_subprocess(self):
        tool = _make_tool(parameters=[
            ParamDef("name", ["--name"], "str", None, True, "Name."),
        ])
        result = generate_module([tool], self._direct_config())
        assert "create_subprocess_exec" not in result

    def test_direct_import_kwargs_use_params_prefix(self):
        tool = _make_tool(parameters=[
            ParamDef("name", ["--name"], "str", None, True, "Name."),
        ])
        result = generate_module([tool], self._direct_config())
        assert "name=params.name" in result

    def test_direct_import_no_params_no_kwargs(self):
        tool = _make_tool()  # parameters=[]
        result = generate_module([tool], self._direct_config())
        assert "asyncio.to_thread(greet)" in result

    def test_direct_import_richer_return_type(self):
        tool = _make_tool(return_type="dict")
        result = generate_module([tool], self._direct_config())
        assert "-> dict:" in result

    def test_direct_import_valid_python(self):
        tool = _make_tool(parameters=[
            ParamDef("name", ["--name"], "str", None, True, "Name."),
            ParamDef("count", ["--count"], "int", 1, False, "Count."),
        ])
        result = generate_module([tool], self._direct_config())
        ast.parse(result)

    def test_direct_import_combined_with_prefix(self):
        config = Config(
            server_name="Test", entry_point="myapp",
            source_dirs=[Path("src")], output_file=Path("out.py"),
            server_file=Path("s.py"), prefer_direct_import=True,
        )
        tool = _make_tool(parameters=[
            ParamDef("name", ["--name"], "str", None, True, "Name."),
        ])
        result = generate_module([tool], config)
        assert "def myapp_greet(" in result
        assert "asyncio.to_thread" in result
        ast.parse(result)
