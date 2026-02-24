"""Tests for the argparse AST scraper."""
import ast
import pytest
from pathlib import Path
from cli2mcp.scrapers.argparse_scraper import (
    ArgparseScraper,
    _ast_to_python,
    _is_argumentparser_call,
    _find_parser_var,
    _find_subparser_var,
    _find_subparser_add_parser_calls,
    _find_subparser_assignments,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_argparse_cli.py"


@pytest.fixture
def scraper():
    return ArgparseScraper(source_module="sample_argparse_cli", cli_command="myapp")


def test_detect(scraper):
    import ast
    tree = ast.parse(FIXTURE.read_text())
    assert scraper.detect(tree) is True


def test_scrape_returns_tools(scraper):
    tools = scraper.scrape_file(FIXTURE)
    assert len(tools) >= 2
    names = [t.name for t in tools]
    assert "run_convert" in names
    assert "run_search" in names


def test_convert_params(scraper):
    tools = scraper.scrape_file(FIXTURE)
    convert = next(t for t in tools if t.name == "run_convert")
    param_names = [p.name for p in convert.parameters]
    assert "input" in param_names
    assert "output" in param_names
    assert "format" in param_names
    assert "verbose" in param_names
    assert "workers" in param_names


def test_convert_types(scraper):
    tools = scraper.scrape_file(FIXTURE)
    convert = next(t for t in tools if t.name == "run_convert")
    params = {p.name: p for p in convert.parameters}
    assert params["workers"].type_annotation == "int"
    assert params["verbose"].type_annotation == "bool"
    assert params["verbose"].is_flag is True


def test_convert_positional_required(scraper):
    tools = scraper.scrape_file(FIXTURE)
    convert = next(t for t in tools if t.name == "run_convert")
    params = {p.name: p for p in convert.parameters}
    assert params["input"].required is True
    assert params["output"].required is True


def test_convert_optional_default(scraper):
    tools = scraper.scrape_file(FIXTURE)
    convert = next(t for t in tools if t.name == "run_convert")
    params = {p.name: p for p in convert.parameters}
    assert params["format"].default == "json"
    assert params["workers"].default == 4


def test_convert_description(scraper):
    tools = scraper.scrape_file(FIXTURE)
    convert = next(t for t in tools if t.name == "run_convert")
    assert "Convert" in convert.description


def test_search_params(scraper):
    tools = scraper.scrape_file(FIXTURE)
    search = next(t for t in tools if t.name == "run_search")
    param_names = [p.name for p in search.parameters]
    assert "pattern" in param_names
    assert "path" in param_names
    assert "recursive" in param_names
    assert "max_results" in param_names


def test_framework_label(scraper):
    tools = scraper.scrape_file(FIXTURE)
    for tool in tools:
        assert tool.framework == "argparse"


def test_no_argparse_file():
    scraper = ArgparseScraper()
    import ast
    tree = ast.parse("x = 1")
    assert scraper.detect(tree) is False


# ---------------------------------------------------------------------------
# Subparsers (issue #6)
# ---------------------------------------------------------------------------

SUBPARSER_FIXTURE = Path(__file__).parent / "fixtures" / "sample_argparse_subparsers.py"


def test_subparsers_produces_two_tools():
    scraper = ArgparseScraper(cli_command="myapp")
    tools = scraper.scrape_file(SUBPARSER_FIXTURE)
    names = [t.name for t in tools]
    assert "start" in names
    assert "run_job" in names  # dash sanitized to underscore


def test_subparser_dash_name_sanitized():
    scraper = ArgparseScraper(cli_command="myapp")
    tools = scraper.scrape_file(SUBPARSER_FIXTURE)
    # tool.name must be valid Python (no dashes)
    for t in tools:
        assert "-" not in t.name


def test_subparser_cli_subcommand_preserved():
    scraper = ArgparseScraper(cli_command="myapp")
    tools = scraper.scrape_file(SUBPARSER_FIXTURE)
    run_job = next(t for t in tools if t.name == "run_job")
    assert run_job.cli_subcommand == "run-job"  # original name kept for CLI invocation


def test_subparser_start_params():
    scraper = ArgparseScraper(cli_command="myapp")
    tools = scraper.scrape_file(SUBPARSER_FIXTURE)
    start = next(t for t in tools if t.name == "start")
    param_names = [p.name for p in start.parameters]
    assert "port" in param_names
    assert "host" in param_names


def test_subparser_run_job_params():
    scraper = ArgparseScraper(cli_command="myapp")
    tools = scraper.scrape_file(SUBPARSER_FIXTURE)
    run_job = next(t for t in tools if t.name == "run_job")
    param_names = [p.name for p in run_job.parameters]
    assert "name" in param_names
    assert "workers" in param_names


# ---------------------------------------------------------------------------
# dest= dash sanitization (issue #1)
# ---------------------------------------------------------------------------

def test_dest_dash_sanitized():
    import ast
    source = """\
import argparse

def my_func():
    parser = argparse.ArgumentParser()
    parser.add_argument("--my-opt", dest="my-dest", help="test")
    parser.parse_args()
"""
    scraper = ArgparseScraper()
    tmp = __import__("tempfile").NamedTemporaryFile(suffix=".py", delete=False, mode="w")
    tmp.write(source)
    tmp.close()
    tools = scraper.scrape_file(Path(tmp.name))
    import os; os.unlink(tmp.name)
    if tools:
        for t in tools:
            for p in t.parameters:
                assert "-" not in p.name


# ---------------------------------------------------------------------------
# Helper: write a temp .py file and return its Path
# ---------------------------------------------------------------------------

def _write_tmp(tmp_path, source: str) -> Path:
    p = tmp_path / "cli.py"
    p.write_text(source)
    return p


# ---------------------------------------------------------------------------
# _ast_to_python — lines 16, 19-26
# ---------------------------------------------------------------------------

def test_ast_to_python_none_node():
    # line 16: node is None → return None
    assert _ast_to_python(None) is None


def test_ast_to_python_name_true():
    # lines 19-21: ast.Name(id='True') → True  (legacy pre-3.8 path)
    node = ast.Name(id="True")
    assert _ast_to_python(node) is True


def test_ast_to_python_name_false():
    # lines 22-23
    node = ast.Name(id="False")
    assert _ast_to_python(node) is False


def test_ast_to_python_name_none():
    # lines 24-25
    node = ast.Name(id="None")
    assert _ast_to_python(node) is None


def test_ast_to_python_unknown_name():
    # line 26: unrecognised Name → None
    node = ast.Name(id="SomeOtherName")
    assert _ast_to_python(node) is None


# ---------------------------------------------------------------------------
# _is_argumentparser_call — lines 32, 35, 38
# ---------------------------------------------------------------------------

def test_is_argumentparser_call_non_call_node():
    # line 32: not an ast.Call → False
    node = ast.Name(id="x")
    assert _is_argumentparser_call(node) is False


def test_is_argumentparser_call_bare_name():
    # line 35: ArgumentParser() with ast.Name func (unqualified import)
    call = ast.parse("ArgumentParser()").body[0].value
    assert _is_argumentparser_call(call) is True


def test_is_argumentparser_call_wrong_attr():
    # line 38: attribute call that is not ArgumentParser → False
    call = ast.parse("foo.bar()").body[0].value
    assert _is_argumentparser_call(call) is False


# ---------------------------------------------------------------------------
# _find_parser_var — lines 50, 66
# ---------------------------------------------------------------------------

def test_find_parser_var_no_match():
    # line 66: function body with no ArgumentParser() → (None, None)
    body = ast.parse("x = 1\ny = 2").body
    assert _find_parser_var(body) == (None, None)


def test_find_parser_var_skips_non_argumentparser_assign():
    # line 50: Assign present but not an ArgumentParser call
    body = ast.parse("x = foo.bar()\ny = argparse.ArgumentParser()").body
    var, prog = _find_parser_var(body)
    assert var == "y"


# ---------------------------------------------------------------------------
# detect() — lines 295-296 (from argparse import ...)
# ---------------------------------------------------------------------------

def test_detect_from_import():
    # lines 295-296
    scraper = ArgparseScraper()
    tree = ast.parse("from argparse import ArgumentParser\nx = 1")
    assert scraper.detect(tree) is True


# ---------------------------------------------------------------------------
# scrape_file edge cases — lines 304-305, 308, 319, 361
# ---------------------------------------------------------------------------

def test_scrape_file_syntax_error(tmp_path):
    # lines 304-305: SyntaxError → return []
    bad = tmp_path / "bad.py"
    bad.write_text("def (:\n    pass\n")
    scraper = ArgparseScraper()
    assert scraper.scrape_file(bad) == []


def test_scrape_file_no_argparse(tmp_path):
    # line 308: detect() False → return []
    p = _write_tmp(tmp_path, "import os\ndef foo():\n    pass\n")
    scraper = ArgparseScraper()
    assert scraper.scrape_file(p) == []


def test_scrape_file_skips_functions_without_parser(tmp_path):
    # line 319: function in argparse file with no ArgumentParser → skipped
    source = """\
import argparse

def helper():
    x = 1

def real_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="Name.")
    parser.parse_args()
"""
    tools = ArgparseScraper().scrape_file(_write_tmp(tmp_path, source))
    names = [t.name for t in tools]
    assert "helper" not in names
    assert "real_tool" in names


def test_scrape_file_parser_no_arguments(tmp_path):
    # line 361: ArgumentParser created but no add_argument calls → skipped
    source = """\
import argparse

def empty_tool():
    parser = argparse.ArgumentParser()
    parser.parse_args()
"""
    tools = ArgparseScraper().scrape_file(_write_tmp(tmp_path, source))
    assert tools == []


# ---------------------------------------------------------------------------
# _parse_add_argument edge cases — lines 96, 132-133, 151-152, 158-161, 167-175, 178
# ---------------------------------------------------------------------------

def test_required_kwarg(tmp_path):
    # lines 132-133: explicit required=True
    source = """\
import argparse

def my_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="Auth token.")
    parser.parse_args()
"""
    tools = ArgparseScraper().scrape_file(_write_tmp(tmp_path, source))
    assert tools
    params = {p.name: p for p in tools[0].parameters}
    assert params["token"].required is True


def test_action_append(tmp_path):
    # lines 151-152: action="append" → is_multiple=True
    source = """\
import argparse

def my_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", action="append", help="Tags.")
    parser.parse_args()
"""
    tools = ArgparseScraper().scrape_file(_write_tmp(tmp_path, source))
    assert tools
    params = {p.name: p for p in tools[0].parameters}
    assert params["tag"].is_multiple is True
    assert params["tag"].type_annotation == "list[str]"  # line 178


def test_nargs_plus(tmp_path):
    # lines 158-161: nargs='+' → is_multiple=True
    source = """\
import argparse

def my_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", nargs="+", help="Input files.")
    parser.parse_args()
"""
    tools = ArgparseScraper().scrape_file(_write_tmp(tmp_path, source))
    params = {p.name: p for p in tools[0].parameters}
    assert params["files"].is_multiple is True


def test_nargs_star(tmp_path):
    # lines 158-161: nargs='*'
    source = """\
import argparse

def my_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--extras", nargs="*", help="Extra args.")
    parser.parse_args()
"""
    tools = ArgparseScraper().scrape_file(_write_tmp(tmp_path, source))
    params = {p.name: p for p in tools[0].parameters}
    assert params["extras"].is_multiple is True


def test_nargs_integer(tmp_path):
    # lines 159-160: nargs=2 (int > 1) → is_multiple=True
    source = """\
import argparse

def my_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", nargs=2, help="Two values.")
    parser.parse_args()
"""
    tools = ArgparseScraper().scrape_file(_write_tmp(tmp_path, source))
    params = {p.name: p for p in tools[0].parameters}
    assert params["pair"].is_multiple is True


def test_choices(tmp_path):
    # lines 167-175: choices=["json", "csv"]
    source = """\
import argparse

def my_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fmt", choices=["json", "csv", "xml"], help="Format.")
    parser.parse_args()
"""
    tools = ArgparseScraper().scrape_file(_write_tmp(tmp_path, source))
    params = {p.name: p for p in tools[0].parameters}
    assert params["fmt"].choices == ["json", "csv", "xml"]


# ---------------------------------------------------------------------------
# _find_subparser_var — line 206
# ---------------------------------------------------------------------------

def test_find_subparser_var_not_found():
    # line 206: no add_subparsers() call → None
    body = ast.parse("parser = argparse.ArgumentParser()").body
    assert _find_subparser_var(body, "parser") is None


# ---------------------------------------------------------------------------
# _find_subparser_add_parser_calls — lines 227-244 (dead code in scrape_file)
# ---------------------------------------------------------------------------

def test_find_subparser_add_parser_calls_direct():
    # lines 227-244: test the function directly
    source = """\
subparsers = parser.add_subparsers()
p1 = subparsers.add_parser("start")
p2 = subparsers.add_parser("stop")
x = other.add_parser("ignored")
"""
    body = ast.parse(source).body
    results = _find_subparser_add_parser_calls(body, "subparsers")
    names = [name for name, _ in results]
    assert "start" in names
    assert "stop" in names
    assert "ignored" not in names


# ---------------------------------------------------------------------------
# _find_subparser_assignments — line 259
# ---------------------------------------------------------------------------

def test_find_subparser_assignments_skips_non_calls():
    # line 259: assignment where value is not a Call
    source = """\
x = 5
p1 = subparsers.add_parser("cmd")
"""
    body = ast.parse(source).body
    result = _find_subparser_assignments(body, "subparsers")
    assert result == {"p1": "cmd"}


# ---------------------------------------------------------------------------
# Docstring param merging — lines 341, 371
# ---------------------------------------------------------------------------

def test_docstring_param_merge_single_parser(tmp_path):
    # line 371: param description from docstring merged into single-parser tool
    source = '''\
import argparse

def my_tool():
    """Do a thing.

    Parameters
    ----------
    name : str
        The name to use.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="")
    parser.parse_args()
'''
    tools = ArgparseScraper().scrape_file(_write_tmp(tmp_path, source))
    assert tools
    params = {p.name: p for p in tools[0].parameters}
    assert params["name"].description == "The name to use."


def test_docstring_param_merge_subparser(tmp_path):
    # line 341: param description from docstring merged into subparser tool
    source = '''\
import argparse

def run_app():
    """Multi-command app.

    Parameters
    ----------
    port : int
        Port to listen on.
    """
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--port", type=int, help="")
    parser.parse_args()
'''
    tools = ArgparseScraper().scrape_file(_write_tmp(tmp_path, source))
    assert tools
    params = {p.name: p for p in tools[0].parameters}
    assert params["port"].description == "Port to listen on."
