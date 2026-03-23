"""Sample Typer CLI for testing cli2mcp scrapers."""
import typer

app = typer.Typer()


@app.command()
def greet(
    name: str,
    count: int = typer.Option(1, help="Number of greetings."),
    loud: bool = typer.Option(False, help="Print in uppercase."),
) -> None:
    """Greet a user by name.

    Parameters
    ----------
    name : str
        The name of the person to greet.
    count : int
        How many times to repeat the greeting.
    loud : bool
        Whether to shout the greeting.
    """
    for _ in range(count):
        msg = f"Hello, {name}!"
        if loud:
            msg = msg.upper()
        typer.echo(msg)


@app.command()
def delete_user(
    user_id: int,
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt."),
) -> None:
    """Delete a user account by ID."""
    typer.echo(f"Deleted user {user_id}")


@app.command()
def list_users(
    active: bool = typer.Option(True, help="Show only active users."),
    limit: int = typer.Option(100, help="Maximum number of users to return."),
) -> None:
    """List all registered users."""
    typer.echo(f"Listing users (active={active}, limit={limit})")


@app.command(name="get-config")
def get_config(key: str = typer.Argument(..., help="Config key to retrieve.")) -> None:
    """Retrieve a configuration value."""
    typer.echo(f"Config[{key}]")
