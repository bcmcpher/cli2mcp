# Writing CLI Code for cli2mcp

`cli2mcp` works by analysing your source files with Python's `ast` module — it never imports them. This page explains the patterns it recognises and how to get the best results.

## Click

### Basic command

```python
import click

@click.command()
@click.argument("name")
@click.option("--count", "-c", type=int, default=1, help="Number of greetings.")
@click.option("--loud", is_flag=True, default=False, help="Print in uppercase.")
def greet(name: str, count: int, loud: bool) -> None:
    """Greet a user by name.

    Parameters
    ----------
    name : str
        The name of the person to greet.
    count : int
        How many times to repeat the greeting.
    loud : bool
        Whether to shout the greeting.

    Returns
    -------
    str
        The greeting message(s).
    """
    for _ in range(count):
        msg = f"Hello, {name}!"
        click.echo(msg.upper() if loud else msg)
```

### Command groups

```python
@click.group()
def cli():
    """Main CLI group."""

@cli.command()
@click.argument("src")
@click.argument("dst")
def copy(src: str, dst: str) -> None:
    """Copy a file."""
    ...
```

Each `@cli.command()` decorated function becomes a separate MCP tool.

### Supported decorators

| Decorator | MCP mapping |
|-----------|-------------|
| `@click.argument(name)` | Required positional parameter |
| `@click.option("--flag", is_flag=True)` | `bool` parameter, only passed when `True` |
| `@click.option("--opt", type=int)` | Typed optional parameter |
| `@click.option("--opt", multiple=True)` | `list[T]` parameter |
| `@click.option("--opt", type=click.Choice([...]))` | Parameter with `choices` |

### Type mapping

| Click type | Python annotation |
|------------|------------------|
| `str` / default | `str` |
| `int` | `int` |
| `float` | `float` |
| `bool` | `bool` |
| `click.Path()` | `str` |
| `click.Choice(["a","b"])` | `str` (choices listed in docstring) |

---

## argparse

### Basic function

```python
import argparse

def run_convert(args=None):
    """Convert files between formats.

    Parameters
    ----------
    input : str
        Input file path.
    output : str
        Output file path.

    Returns
    -------
    str
        Conversion result summary.
    """
    parser = argparse.ArgumentParser(prog="convert")
    parser.add_argument("input", help="Input file path.")
    parser.add_argument("output", help="Output file path.")
    parser.add_argument("--format", "-f", default="json", help="Output format.")
    parser.add_argument("--verbose", "-v", action="store_true")
    parsed = parser.parse_args(args)
    ...
```

!!! note
    The `prog=` argument on `ArgumentParser` is used as the CLI subcommand name. If omitted, the function name is used.

### Subparsers

```python
def run_app(args=None):
    parser = argparse.ArgumentParser(prog="myapp")
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--port", type=int, default=8080)

    stop_parser = subparsers.add_parser("stop")
    stop_parser.add_argument("--timeout", type=int, default=5)

    parser.parse_args(args)
```

Each `add_parser()` call becomes a separate MCP tool (`start`, `stop`). Dashes in subcommand names are sanitised to underscores in the Python function name but preserved in the CLI invocation.

### Supported `add_argument` patterns

| Pattern | MCP mapping |
|---------|-------------|
| `add_argument("name")` | Required positional |
| `add_argument("--opt")` | Optional `str` |
| `add_argument("--opt", type=int)` | Typed optional |
| `add_argument("--flag", action="store_true")` | `bool` flag |
| `add_argument("--items", action="append")` | `list[str]` |
| `add_argument("--files", nargs="+")` | `list[str]` |
| `add_argument("--fmt", choices=["a","b"])` | `str` with choices |
| `add_argument("--opt", required=True)` | Explicit required |

---

## NumPy docstrings

`cli2mcp` parses NumPy-style docstrings and uses them to populate tool descriptions and per-parameter help. The `help=` text in decorators serves as the fallback when no docstring is present.

```python
"""One-line summary used as the tool description.

Parameters
----------
name : str
    Description merged into the generated tool's parameter docstring.
count : int
    Overrides the help= string from the decorator.

Returns
-------
str
    Description used in the Returns section of the generated docstring.
"""
```

!!! tip
    The `Parameters` section in the docstring takes priority over `help=` strings. Write docstrings for the richest output.
