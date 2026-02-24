"""Sample Click CLI with advanced features for testing (Choice, multiple, nargs, dashes)."""
import click


@click.group()
def cli():
    """Advanced CLI group."""


@cli.command(name="run-job")
@click.argument("name")
@click.option("--format", type=click.Choice(["json", "csv", "xml"]), default="json",
               help="Output format.")
@click.option("--tags", multiple=True, help="Tags to apply.")
def run_job(name: str, format: str, tags: tuple) -> None:
    """Run a named job.

    Returns
    -------
    str
        Job result.
    """
    click.echo(f"Running {name}")


@cli.command()
@click.argument("files", nargs=-1)
@click.option("--output", default="out.txt", help="Output file.")
def merge(files: tuple, output: str) -> None:
    """Merge multiple files."""
    click.echo(f"Merging {len(files)} files")
