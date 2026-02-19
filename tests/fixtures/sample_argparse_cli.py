"""Sample argparse CLI for testing cli2mcp scrapers."""
import argparse


def run_convert(args=None):
    """Convert files between formats.

    Parameters
    ----------
    args : list, optional
        Command line arguments (for testing).

    Returns
    -------
    str
        Conversion result summary.
    """
    parser = argparse.ArgumentParser(prog="convert", description="Convert files between formats.")
    parser.add_argument("input", type=str, help="Input file path.")
    parser.add_argument("output", type=str, help="Output file path.")
    parser.add_argument("--format", "-f", type=str, default="json", help="Output format.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output.")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker threads.")
    parsed = parser.parse_args(args)
    return f"Converting {parsed.input} to {parsed.output}"


def run_search(args=None):
    """Search for patterns in files.

    Parameters
    ----------
    args : list, optional
        Arguments for testing.

    Returns
    -------
    str
        Search results.
    """
    parser = argparse.ArgumentParser(prog="search")
    parser.add_argument("pattern", help="Search pattern.")
    parser.add_argument("--path", default=".", help="Directory to search.")
    parser.add_argument("--recursive", "-r", action="store_true", help="Search recursively.")
    parser.add_argument("--max-results", type=int, default=100, help="Max results to return.")
    parsed = parser.parse_args(args)
    return f"Searching for {parsed.pattern}"
