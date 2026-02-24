"""Click fixture covering 1a/1b/1c/1d/1e patterns for cli2mcp tests."""
from __future__ import annotations

import functools
import click


# ---------------------------------------------------------------------------
# 1a: Custom decorator wrappers
# ---------------------------------------------------------------------------

def dataset_option(func):
    """Decorator factory that adds shared --dataset and --version options."""
    @click.option("--dataset", "-d", help="Dataset name to operate on.")
    @click.option("--version", type=int, default=1, help="Dataset version.")
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def output_options(func):
    """Decorator factory that adds --output-dir and --dry-run options."""
    @click.option("--output-dir", default="./out", help="Output directory.")
    @click.option("--dry-run", is_flag=True, default=False, help="Simulate without writing.")
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


@click.group()
def cli():
    """CLI group for pattern tests."""


@cli.command()
@dataset_option
@click.option("--verbose", is_flag=True, help="Verbose output.")
def train(dataset, version, verbose):
    """Train a model on the given dataset."""
    click.echo(f"Training on {dataset} v{version}")


@cli.command()
@dataset_option
@output_options
def export(dataset, version, output_dir, dry_run):
    """Export a trained model."""
    click.echo(f"Exporting {dataset}")


# ---------------------------------------------------------------------------
# 1b: @click.pass_context
# ---------------------------------------------------------------------------

@cli.command()
@click.pass_context
@click.option("--name", required=True, help="Name of the resource.")
def create(ctx, name):
    """Create a resource using the current context."""
    click.echo(f"Creating {name} in {ctx.obj}")


# ---------------------------------------------------------------------------
# 1c: async def commands
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--url", required=True, help="URL to fetch asynchronously.")
@click.option("--timeout", type=int, default=30, help="Request timeout.")
async def async_fetch(url, timeout):
    """Fetch a URL asynchronously."""
    click.echo(f"Async fetch: {url}")


# ---------------------------------------------------------------------------
# 1d: Nested Click groups
# ---------------------------------------------------------------------------

@cli.group()
def db():
    """Database management commands."""


@db.command()
@click.option("--target", default="latest", help="Migration target revision.")
def migrate(target):
    """Run database migrations."""
    click.echo(f"Migrating to {target}")


@db.command()
@click.option("--confirm", is_flag=True, required=True, help="Confirm the reset.")
def reset(confirm):
    """Reset the database to a clean state."""
    click.echo("Resetting database")


# ---------------------------------------------------------------------------
# 1e: Hidden options
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--name", required=True, help="Resource name.")
@click.option("--debug-token", hidden=True, help="Internal debug token.")
@click.option("--internal-flag", help=click.SUPPRESS)
def deploy(name, debug_token, internal_flag):
    """Deploy a resource. Hidden options are for internal use only."""
    click.echo(f"Deploying {name}")
