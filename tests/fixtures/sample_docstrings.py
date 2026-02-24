"""Fixture for testing Google-style and Sphinx-style docstring parsing."""
from __future__ import annotations

import click


@click.group()
def cli():
    """CLI for docstring pattern tests."""


@cli.command()
@click.option("--input-file", required=True, help="Input file.")
@click.option("--output-file", default="out.txt", help="Output file.")
@click.option("--count", type=int, default=1, help="Count.")
def google_cmd(input_file, output_file, count):
    """Process an input file using Google-style docstring.

    Args:
        input_file: Path to the input file to process.
        output_file (str): Path to write processed output.
        count (int): Number of times to process.

    Returns:
        Processing result summary.
    """
    click.echo(f"Processing {input_file}")


@cli.command()
@click.option("--query", required=True, help="Search query.")
@click.option("--limit", type=int, default=10, help="Max results.")
def sphinx_cmd(query, limit):
    """Search the index using Sphinx-style docstring.

    :param query: The search query string.
    :type query: str
    :param limit: Maximum number of results to return.
    :type limit: int
    :returns: Matching records.
    :rtype: str
    """
    click.echo(f"Searching: {query}")
