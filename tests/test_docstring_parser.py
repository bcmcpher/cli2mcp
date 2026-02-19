"""Tests for the NumPy docstring parser."""
import pytest
from cli2mcp.parsers.docstring import parse_numpy_docstring, ParsedDocstring


def test_empty_docstring():
    result = parse_numpy_docstring(None)
    assert result.summary == ""
    assert result.params == {}
    assert result.returns == ""


def test_summary_only():
    doc = "Just a summary."
    result = parse_numpy_docstring(doc)
    assert result.summary == "Just a summary."
    assert result.params == {}


def test_full_numpy_docstring():
    doc = """Greet a user by name.

    Parameters
    ----------
    name : str
        The name of the person.
    count : int
        How many times to greet.

    Returns
    -------
    str
        The greeting message.
    """
    result = parse_numpy_docstring(doc)
    assert result.summary == "Greet a user by name."
    assert "name" in result.params
    assert result.params["name"] == "The name of the person."
    assert "count" in result.params
    assert result.params["count"] == "How many times to greet."
    assert result.returns == "The greeting message."


def test_no_parameters_section():
    doc = """Do something.

    Returns
    -------
    str
        The result.
    """
    result = parse_numpy_docstring(doc)
    assert result.summary == "Do something."
    assert result.params == {}
    assert result.returns == "The result."


def test_extended_description():
    doc = """Short summary.

    This is an extended description that spans
    multiple lines.

    Parameters
    ----------
    x : int
        The value.
    """
    result = parse_numpy_docstring(doc)
    assert result.summary == "Short summary."
    assert "x" in result.params
    assert result.params["x"] == "The value."


def test_param_without_type():
    doc = """Summary.

    Parameters
    ----------
    myarg
        A parameter without a type annotation.
    """
    result = parse_numpy_docstring(doc)
    assert "myarg" in result.params
    assert result.params["myarg"] == "A parameter without a type annotation."


def test_empty_string_docstring():
    result = parse_numpy_docstring("")
    assert result.summary == ""
