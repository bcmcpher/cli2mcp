# Installation

## Requirements

- Python **3.11 or later** (uses `tomllib` from the standard library; older versions need `tomli`)
- `click >= 8.0` (installed automatically as a dependency)

## Install from PyPI

```bash
pip install cli2mcp
```

## Install in development mode

Clone the repository and install with the `dev` extras:

```bash
git clone https://github.com/bcmcpher/cli2mcp.git
cd cli2mcp
pip install -e ".[dev]"
```

The `dev` extras add `pytest` and `pytest-cov` for running the test suite.

## Generated server dependency

`mcp` (FastMCP) is **not** a dependency of `cli2mcp` itself — it is a dependency of the *generated* server. Install it in the environment where `mcp_server.py` will run:

```bash
pip install mcp
```

## Verify the install

```bash
cli2mcp --help
```

You should see the top-level help listing the `init`, `generate`, `list`, and `validate` subcommands.

## Python < 3.11

On Python 3.10 or earlier, install `tomli` as well:

```bash
pip install cli2mcp tomli
```

`cli2mcp` will automatically fall back to `tomli` when `tomllib` is not in the standard library.
