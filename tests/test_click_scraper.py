"""Tests for the Click AST scraper."""
import pytest
from pathlib import Path
from cli2mcp.scrapers.click_scraper import ClickScraper

FIXTURE = Path(__file__).parent / "fixtures" / "sample_click_cli.py"


@pytest.fixture
def scraper():
    return ClickScraper(source_module="sample_click_cli", cli_command="mycli")


def test_detect(scraper):
    import ast
    tree = ast.parse(FIXTURE.read_text())
    assert scraper.detect(tree) is True


def test_scrape_returns_tools(scraper):
    tools = scraper.scrape_file(FIXTURE)
    assert len(tools) >= 2
    names = [t.name for t in tools]
    assert "greet" in names
    assert "process" in names


def test_greet_tool_params(scraper):
    tools = scraper.scrape_file(FIXTURE)
    greet = next(t for t in tools if t.name == "greet")

    param_names = [p.name for p in greet.parameters]
    assert "name" in param_names
    assert "count" in param_names
    assert "loud" in param_names


def test_greet_tool_types(scraper):
    tools = scraper.scrape_file(FIXTURE)
    greet = next(t for t in tools if t.name == "greet")
    params = {p.name: p for p in greet.parameters}

    assert params["count"].type_annotation == "int"
    assert params["loud"].type_annotation == "bool"
    assert params["loud"].is_flag is True


def test_greet_docstring_description(scraper):
    tools = scraper.scrape_file(FIXTURE)
    greet = next(t for t in tools if t.name == "greet")
    assert "Greet" in greet.description


def test_greet_param_description_from_docstring(scraper):
    tools = scraper.scrape_file(FIXTURE)
    greet = next(t for t in tools if t.name == "greet")
    params = {p.name: p for p in greet.parameters}
    assert "name of the person" in params["name"].description.lower()


def test_process_required_param(scraper):
    tools = scraper.scrape_file(FIXTURE)
    process = next(t for t in tools if t.name == "process")
    params = {p.name: p for p in process.parameters}
    assert params["input_file"].required is True


def test_process_optional_param(scraper):
    tools = scraper.scrape_file(FIXTURE)
    process = next(t for t in tools if t.name == "process")
    params = {p.name: p for p in process.parameters}
    assert params["output_file"].required is False
    assert params["output_file"].default == "out.txt"


def test_fetch_standalone_command(scraper):
    tools = scraper.scrape_file(FIXTURE)
    fetch = next((t for t in tools if t.name == "fetch"), None)
    assert fetch is not None
    assert fetch.framework == "click"


def test_framework_label(scraper):
    tools = scraper.scrape_file(FIXTURE)
    for tool in tools:
        assert tool.framework == "click"


def test_no_click_file():
    scraper = ClickScraper()
    import ast
    tree = ast.parse("x = 1")
    assert scraper.detect(tree) is False


def test_nonexistent_file_returns_empty(scraper):
    tools = scraper.scrape_file(Path("/nonexistent/file.py"))
    assert tools == []


# ---------------------------------------------------------------------------
# Advanced features (issue #1 dash names, #7 Choice / multiple / nargs)
# ---------------------------------------------------------------------------

ADVANCED_FIXTURE = Path(__file__).parent / "fixtures" / "sample_click_advanced.py"


def test_dash_command_name_sanitized():
    """@cli.command(name='run-job') → tool.name == 'run_job' (no dashes)."""
    adv_scraper = ClickScraper(source_module="sample_click_advanced", cli_command="mycli")
    tools = adv_scraper.scrape_file(ADVANCED_FIXTURE)
    for t in tools:
        assert "-" not in t.name


def test_dash_command_cli_subcommand_preserved():
    """cli_subcommand keeps original dashes for correct subprocess invocation."""
    adv_scraper = ClickScraper(source_module="sample_click_advanced", cli_command="mycli")
    tools = adv_scraper.scrape_file(ADVANCED_FIXTURE)
    run_job = next(t for t in tools if t.name == "run_job")
    assert run_job.cli_subcommand == "run-job"


def test_choice_type_captures_choices():
    adv_scraper = ClickScraper(source_module="sample_click_advanced", cli_command="mycli")
    tools = adv_scraper.scrape_file(ADVANCED_FIXTURE)
    run_job = next(t for t in tools if t.name == "run_job")
    params = {p.name: p for p in run_job.parameters}
    assert params["format"].choices == ["json", "csv", "xml"]


def test_multiple_option_is_multiple():
    adv_scraper = ClickScraper(source_module="sample_click_advanced", cli_command="mycli")
    tools = adv_scraper.scrape_file(ADVANCED_FIXTURE)
    run_job = next(t for t in tools if t.name == "run_job")
    params = {p.name: p for p in run_job.parameters}
    assert params["tags"].is_multiple is True
    assert params["tags"].type_annotation.startswith("list[")


def test_nargs_variadic_argument():
    adv_scraper = ClickScraper(source_module="sample_click_advanced", cli_command="mycli")
    tools = adv_scraper.scrape_file(ADVANCED_FIXTURE)
    merge = next(t for t in tools if t.name == "merge")
    params = {p.name: p for p in merge.parameters}
    assert params["files"].is_multiple is True
    assert params["files"].type_annotation.startswith("list[")
