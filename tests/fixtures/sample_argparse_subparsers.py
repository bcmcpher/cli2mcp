"""Sample argparse CLI with subparsers for testing."""
import argparse


def run_app(args=None):
    """Multi-subcommand app.

    Returns
    -------
    str
        Result.
    """
    parser = argparse.ArgumentParser(prog="myapp", description="Multi-command app.")
    subparsers = parser.add_subparsers(dest="command")

    # subcommand: start
    start_parser = subparsers.add_parser("start", help="Start the service.")
    start_parser.add_argument("--port", type=int, default=8080, help="Port to listen on.")
    start_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to.")

    # subcommand: run-job (has a dash)
    run_job_parser = subparsers.add_parser("run-job", help="Run a background job.")
    run_job_parser.add_argument("name", help="Job name.")
    run_job_parser.add_argument("--workers", type=int, default=1, help="Worker count.")

    parsed = parser.parse_args(args)
    return str(parsed)
