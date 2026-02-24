"""Tests for argparse scraper enhancements: 1c/2a/2c/2d."""
from __future__ import annotations

import pytest
from pathlib import Path

from cli2mcp.scrapers.argparse_scraper import ArgparseScraper


def _write(tmp_path: Path, source: str) -> Path:
    p = tmp_path / "cli.py"
    p.write_text(source)
    return p


# ---------------------------------------------------------------------------
# 1c: async def argparse functions
# ---------------------------------------------------------------------------

class TestAsyncArgparse:
    def test_async_function_scraped(self, tmp_path):
        source = """\
import argparse

async def async_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="Resource name.")
    parser.parse_args()
"""
        tools = ArgparseScraper().scrape_file(_write(tmp_path, source))
        names = [t.name for t in tools]
        assert "async_tool" in names

    def test_async_function_params(self, tmp_path):
        source = """\
import argparse

async def async_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Resource name.")
    parser.parse_args()
"""
        tools = ArgparseScraper().scrape_file(_write(tmp_path, source))
        assert tools
        params = {p.name: p for p in tools[0].parameters}
        assert "name" in params
        assert params["name"].required is True


# ---------------------------------------------------------------------------
# 2a: Mutually exclusive groups
# ---------------------------------------------------------------------------

class TestMutuallyExclusiveGroups:
    SOURCE = """\
import argparse

def my_tool():
    parser = argparse.ArgumentParser()
    mutex = parser.add_mutually_exclusive_group()
    mutex.add_argument("--verbose", action="store_true", help="Verbose output.")
    mutex.add_argument("--quiet", action="store_true", help="Quiet output.")
    parser.add_argument("--output", default="stdout", help="Output target.")
    parser.parse_args()
"""

    def test_mutex_params_have_group(self, tmp_path):
        tools = ArgparseScraper().scrape_file(_write(tmp_path, self.SOURCE))
        assert tools
        params = {p.name: p for p in tools[0].parameters}
        assert params["verbose"].mutually_exclusive_group is not None
        assert params["quiet"].mutually_exclusive_group is not None

    def test_mutex_params_same_group(self, tmp_path):
        tools = ArgparseScraper().scrape_file(_write(tmp_path, self.SOURCE))
        params = {p.name: p for p in tools[0].parameters}
        # Both mutex params belong to the same group
        assert params["verbose"].mutually_exclusive_group == params["quiet"].mutually_exclusive_group

    def test_regular_param_no_group(self, tmp_path):
        tools = ArgparseScraper().scrape_file(_write(tmp_path, self.SOURCE))
        params = {p.name: p for p in tools[0].parameters}
        assert params["output"].mutually_exclusive_group is None


# ---------------------------------------------------------------------------
# 2c: Extended action types
# ---------------------------------------------------------------------------

class TestExtendedActions:
    def test_count_action(self, tmp_path):
        """action='count' → type int (increments per flag)."""
        source = """\
import argparse

def my_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="count", help="Verbosity level.")
    parser.parse_args()
"""
        tools = ArgparseScraper().scrape_file(_write(tmp_path, source))
        assert tools
        params = {p.name: p for p in tools[0].parameters}
        assert "verbose" in params
        assert params["verbose"].type_annotation == "int"

    def test_extend_action(self, tmp_path):
        """action='extend' → is_multiple."""
        source = """\
import argparse

def my_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", action="extend", nargs="+", help="Items.")
    parser.parse_args()
"""
        tools = ArgparseScraper().scrape_file(_write(tmp_path, source))
        assert tools
        params = {p.name: p for p in tools[0].parameters}
        assert params["items"].is_multiple is True

    def test_append_const_action(self, tmp_path):
        """action='append_const' → is_multiple."""
        source = """\
import argparse

def my_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--flag", action="append_const", const=1, help="Accumulate.")
    parser.parse_args()
"""
        tools = ArgparseScraper().scrape_file(_write(tmp_path, source))
        assert tools
        params = {p.name: p for p in tools[0].parameters}
        assert params["flag"].is_multiple is True

    def test_store_const_action(self, tmp_path):
        """action='store_const' → keeps str type."""
        source = """\
import argparse

def my_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", action="store_const", const="fast", help="Fast mode.")
    parser.parse_args()
"""
        tools = ArgparseScraper().scrape_file(_write(tmp_path, source))
        assert tools
        params = {p.name: p for p in tools[0].parameters}
        assert "mode" in params
        # store_const doesn't crash; type stays str
        assert params["mode"].type_annotation == "str"


# ---------------------------------------------------------------------------
# 2d: FileType and lambda types
# ---------------------------------------------------------------------------

class TestSpecialTypes:
    def test_filetype_maps_to_str(self, tmp_path):
        """argparse.FileType → str (CLI boundary: a path string)."""
        source = """\
import argparse

def my_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=argparse.FileType("r"), help="Input file.")
    parser.parse_args()
"""
        tools = ArgparseScraper().scrape_file(_write(tmp_path, source))
        assert tools
        params = {p.name: p for p in tools[0].parameters}
        assert params["file"].type_annotation == "str"

    def test_lambda_type_maps_to_str(self, tmp_path):
        """lambda type callable → str (evaluated at runtime, not statically known)."""
        source = """\
import argparse

def my_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hex", type=lambda s: int(s, 16), help="Hex integer.")
    parser.parse_args()
"""
        tools = ArgparseScraper().scrape_file(_write(tmp_path, source))
        assert tools
        params = {p.name: p for p in tools[0].parameters}
        assert params["hex"].type_annotation == "str"
