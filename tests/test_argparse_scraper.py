"""Tests for the argparse AST scraper."""
import pytest
from pathlib import Path
from cli2mcp.scrapers.argparse_scraper import ArgparseScraper

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
