"""Sample Click CLI for testing cli2mcp scrapers."""
import click


@click.group()
def cli():
    """Main CLI group."""


@cli.command()
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
        if loud:
            msg = msg.upper()
        click.echo(msg)


@cli.command()
@click.option("--input-file", "-i", required=True, type=click.Path(), help="Input file path.")
@click.option("--output-file", "-o", default="out.txt", help="Output file path.")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
def process(input_file: str, output_file: str, verbose: bool) -> None:
    """Process an input file and write results.

    Parameters
    ----------
    input_file : str
        Path to the input file to process.
    output_file : str
        Path to write the output.
    verbose : bool
        Enable verbose logging.

    Returns
    -------
    str
        Processing summary.
    """
    if verbose:
        click.echo(f"Processing {input_file} → {output_file}")


@click.command()
@click.argument("url")
@click.option("--timeout", type=float, default=30.0, help="Request timeout in seconds.")
def fetch(url: str, timeout: float) -> None:
    """Fetch content from a URL."""
    click.echo(f"Fetching {url} with timeout={timeout}")
