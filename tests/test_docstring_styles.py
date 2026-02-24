"""Tests for 4a (Google/Sphinx docstring styles) and 4b (param type capture)."""
from __future__ import annotations

import pytest
from pathlib import Path

from cli2mcp.parsers.docstring import parse_numpy_docstring, ParsedDocstring
from cli2mcp.scrapers.click_scraper import ClickScraper

FIXTURE = Path(__file__).parent / "fixtures" / "sample_docstrings.py"


# ---------------------------------------------------------------------------
# 4a: Style detection and Google parsing
# ---------------------------------------------------------------------------

class TestGoogleStyle:
    DOCSTRING = """\
Process an input file.

Args:
    input_file: Path to the input file to process.
    output_file (str): Path to write processed output.
    count (int): Number of times to process.

Returns:
    Processing result summary.
"""

    def test_summary_captured(self):
        result = parse_numpy_docstring(self.DOCSTRING)
        assert result.summary == "Process an input file."

    def test_params_captured(self):
        result = parse_numpy_docstring(self.DOCSTRING)
        assert "input_file" in result.params
        assert "output_file" in result.params
        assert "count" in result.params

    def test_param_descriptions(self):
        result = parse_numpy_docstring(self.DOCSTRING)
        assert "Path to the input file" in result.params["input_file"]
        assert "processed output" in result.params["output_file"]

    def test_param_types_captured(self):
        """4b: Type hints in Google `name (type):` are captured in param_types."""
        result = parse_numpy_docstring(self.DOCSTRING)
        assert result.param_types.get("output_file") == "str"
        assert result.param_types.get("count") == "int"

    def test_param_without_type_has_no_type_entry(self):
        result = parse_numpy_docstring(self.DOCSTRING)
        assert "input_file" not in result.param_types

    def test_returns_captured(self):
        result = parse_numpy_docstring(self.DOCSTRING)
        assert "Processing result summary" in result.returns


class TestGoogleStyleFromFixture:
    """End-to-end: Google docstring in fixture → ClickScraper captures descriptions."""

    def test_google_cmd_description(self):
        scraper = ClickScraper(source_module="sample_docstrings", cli_command="mycli")
        tools = {t.name: t for t in scraper.scrape_file(FIXTURE)}
        assert "google_cmd" in tools
        assert "Process" in tools["google_cmd"].description

    def test_google_cmd_param_descriptions(self):
        scraper = ClickScraper(source_module="sample_docstrings", cli_command="mycli")
        tools = {t.name: t for t in scraper.scrape_file(FIXTURE)}
        params = {p.name: p for p in tools["google_cmd"].parameters}
        assert "input_file" in params
        # Description comes from @click.option help= (scraper merges docstring into empty descs)


# ---------------------------------------------------------------------------
# 4a: Sphinx parsing
# ---------------------------------------------------------------------------

class TestSphinxStyle:
    DOCSTRING = """\
Search the index.

:param query: The search query string.
:type query: str
:param limit: Maximum number of results to return.
:type limit: int
:returns: Matching records.
:rtype: str
"""

    def test_summary_captured(self):
        result = parse_numpy_docstring(self.DOCSTRING)
        assert result.summary == "Search the index."

    def test_params_captured(self):
        result = parse_numpy_docstring(self.DOCSTRING)
        assert "query" in result.params
        assert "limit" in result.params

    def test_param_descriptions(self):
        result = parse_numpy_docstring(self.DOCSTRING)
        assert "search query" in result.params["query"]
        assert "Maximum number" in result.params["limit"]

    def test_param_types_captured(self):
        """4b: :type name: captures type in param_types."""
        result = parse_numpy_docstring(self.DOCSTRING)
        assert result.param_types.get("query") == "str"
        assert result.param_types.get("limit") == "int"

    def test_returns_captured(self):
        result = parse_numpy_docstring(self.DOCSTRING)
        assert "Matching records" in result.returns


# ---------------------------------------------------------------------------
# 4b: NumPy param type capture
# ---------------------------------------------------------------------------

class TestNumpyParamTypes:
    DOCSTRING = """\
Compute something.

Parameters
----------
x : int
    The input integer.
y : float
    The scaling factor.
label : str
    Optional label.
"""

    def test_param_types_from_numpy(self):
        result = parse_numpy_docstring(self.DOCSTRING)
        assert result.param_types.get("x") == "int"
        assert result.param_types.get("y") == "float"
        assert result.param_types.get("label") == "str"

    def test_param_descriptions_still_work(self):
        result = parse_numpy_docstring(self.DOCSTRING)
        assert "input integer" in result.params["x"]
        assert "scaling factor" in result.params["y"]


# ---------------------------------------------------------------------------
# Style detection edge cases
# ---------------------------------------------------------------------------

def test_empty_docstring():
    result = parse_numpy_docstring(None)
    assert result.summary == ""
    assert result.params == {}


def test_plain_summary_only():
    result = parse_numpy_docstring("Just a summary.")
    assert result.summary == "Just a summary."
    assert result.params == {}


def test_numpy_style_not_misdetected_as_google():
    """Docstrings with --- underlines must use NumPy parser."""
    doc = """\
Compute something.

Parameters
----------
x : int
    The input.
"""
    result = parse_numpy_docstring(doc)
    assert "x" in result.params


def test_sphinx_detected_by_param_directive():
    doc = ":param foo: A foo parameter.\n:returns: The result."
    result = parse_numpy_docstring(doc)
    assert "foo" in result.params
    assert "A foo parameter." in result.params["foo"]
